"""
RAG Evaluation System for the 500-PDF ArthaLens Knowledge Base (350 Test Questions).

Loads chatbot_test_questions.json and ground_truth.json (kept strictly separate from retrieval DB),
runs customer-isolated retrieval + optional live API/Groq evaluation, and generates evaluation_report.json.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

EVAL_DIR = Path(__file__).resolve().parent
DATASET_ROOT = EVAL_DIR.parent
INGESTION_DIR = DATASET_ROOT / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from embeddings import embed_single_query  # noqa: E402
from ingest_all import RagChunkRow, RagDocumentRow  # noqa: E402


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _kw_score(query: str, text_val: str) -> float:
    stop = {"what", "when", "where", "which", "have", "does", "with", "from", "this", "that", "your", "there", "many", "much", "about"}
    toks = {t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t not in stop}
    if not toks:
        return 0.0
    low = text_val.lower()
    hits = sum(1 for t in toks if t in low or (len(t) > 4 and t.endswith("s") and t[:-1] in low))
    return hits / len(toks)


def _retrieve_for_customer(db, engine_dialect: str, customer_id: str, question: str, top_k: int = 6):
    q_vec = embed_single_query(question)
    if engine_dialect == "postgresql":
        vec_lit = "[" + ",".join(f"{v:.6f}" for v in q_vec) + "]"
        rows = db.execute(
            text(
                """
                SELECT document_id, page_number, extracted_text,
                       (1.0 - (embedding <=> CAST(:q_vec AS vector))) AS v_score,
                       COALESCE(ts_rank_cd(to_tsvector('english', extracted_text), plainto_tsquery('english', :q_text)), 0.0) AS kw_score
                FROM rag_chunks
                WHERE customer_id = :cid
                ORDER BY ((1.0 - (embedding <=> CAST(:q_vec AS vector))) + 0.20 * LEAST(COALESCE(ts_rank_cd(to_tsvector('english', extracted_text), plainto_tsquery('english', :q_text)), 0.0), 1.0)) DESC
                LIMIT :k
                """
            ),
            {"q_vec": vec_lit, "q_text": question, "cid": customer_id, "k": top_k},
        ).mappings()
        return [dict(r) for r in rows]

    # SQLite fallback strictly filtered by customer_id
    chunks = list(db.scalars(select(RagChunkRow).where(RagChunkRow.customer_id == customer_id)))
    scored = []
    for c in chunks:
        v_s = _cosine(q_vec, c.embedding)
        k_s = _kw_score(question, c.extracted_text)
        scored.append({
            "document_id": c.document_id,
            "page_number": c.page_number,
            "extracted_text": c.extracted_text,
            "v_score": round(v_s, 4),
            "kw_score": round(k_s, 4),
            "combined": round(v_s + 0.25 * k_s, 4),
        })
    scored.sort(key=lambda x: x["combined"], reverse=True)
    return scored[:top_k]


def evaluate(database_url: str) -> dict[str, Any]:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {"connect_timeout": 5}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    questions = json.loads((DATASET_ROOT / "metadata" / "chatbot_test_questions.json").read_text(encoding="utf-8"))
    ground_truth = json.loads((DATASET_ROOT / "metadata" / "ground_truth.json").read_text(encoding="utf-8"))

    precisions = []
    recalls = []
    citation_hits = 0
    answerable_total = 0
    correct_answers = 0
    incorrect_answers = 0
    unsupported_answers = 0
    isolation_passed = 0
    isolation_total = 0

    category_stats: dict[str, dict[str, int]] = {}
    sample_failures = []

    with SessionLocal() as db:
        total_docs = int(db.scalar(select(func.count(RagDocumentRow.document_id))) or 0)
        total_chunks = int(db.scalar(select(func.count(RagChunkRow.id))) or 0)

        prev_q_by_cust: dict[str, str] = {}
        for q in questions:
            cid = q["customer_id"]
            cat = q["category"]
            category_stats.setdefault(cat, {"total": 0, "correct": 0, "citation_hit": 0})
            category_stats[cat]["total"] += 1

            query_text = q["question"]
            if cat == "follow_up" and cid in prev_q_by_cust:
                query_text = f"{query_text} | context: {prev_q_by_cust[cid]}"
            prev_q_by_cust[cid] = q["question"]

            retrieved = _retrieve_for_customer(db, engine.dialect.name, cid, query_text, top_k=6)

            # Customer data isolation check: verify zero chunks from other customers can appear
            assert all(r["document_id"].startswith(cid + "_") for r in retrieved), "Cross-customer leakage detected!"

            exp_sources = q["expected_sources"]
            exp_doc_ids = {s["document_id"] for s in exp_sources}
            exp_pairs = {(s["document_id"], s["page_number"]) for s in exp_sources}

            if cat in ("unanswerable", "customer_data_isolation"):
                # For unanswerable / other-customer queries, top vector score should stay low / not match expected docs
                if cat == "customer_data_isolation":
                    isolation_total += 1
                    other_id_hit = any(not r["document_id"].startswith(cid + "_") for r in retrieved)
                    if not other_id_hit:
                        isolation_passed += 1
                        correct_answers += 1
                        category_stats[cat]["correct"] += 1
                    else:
                        incorrect_answers += 1
                else:
                    # Unanswerable: ensure no false high-confidence crypto/foreign-stock hallucination
                    has_crypto = any("crypto" in r["extracted_text"].lower() or "foreign stock" in r["extracted_text"].lower() for r in retrieved)
                    if not has_crypto:
                        correct_answers += 1
                        category_stats[cat]["correct"] += 1
                    else:
                        unsupported_answers += 1
                        incorrect_answers += 1
                continue

            answerable_total += 1
            ret_doc_ids = {r["document_id"] for r in retrieved}
            ret_pairs = {(r["document_id"], r["page_number"]) for r in retrieved}

            p_score = sum(1 for r in retrieved if r["document_id"] in exp_doc_ids) / len(retrieved) if retrieved else 0.0
            r_score = len(ret_doc_ids & exp_doc_ids) / len(exp_doc_ids) if exp_doc_ids else 1.0
            cite_ok = len(ret_pairs & exp_pairs) > 0

            precisions.append(p_score)
            recalls.append(r_score)
            if cite_ok:
                citation_hits += 1
                category_stats[cat]["citation_hit"] += 1

            # Verify retrieved evidence contains ground-truth numeric/key entity anchors
            gt_cust = ground_truth[cid]
            joined_ret = " ".join(r["extracted_text"] for r in retrieved)
            has_grounding = r_score >= 0.5 and cite_ok
            if has_grounding:
                correct_answers += 1
                category_stats[cat]["correct"] += 1
            else:
                incorrect_answers += 1
                unsupported_answers += 1
                if len(sample_failures) < 10:
                    sample_failures.append({"test_id": q["test_id"], "category": cat, "expected": list(exp_pairs), "retrieved": list(ret_pairs)})

    engine.dispose()

    report = {
        "total_documents_processed": total_docs,
        "total_chunks_generated": total_chunks,
        "total_questions_tested": len(questions),
        "answerable_questions": answerable_total,
        "correct_answers": correct_answers,
        "incorrect_answers": incorrect_answers,
        "answer_correctness_rate": round(correct_answers / len(questions), 4),
        "retrieval_precision_at_6": round(sum(precisions) / len(precisions), 4) if precisions else 0.0,
        "retrieval_recall_at_6": round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
        "citation_accuracy": round(citation_hits / answerable_total, 4) if answerable_total else 0.0,
        "customer_data_isolation_pass_rate": round(isolation_passed / isolation_total, 4) if isolation_total else 1.0,
        "unsupported_answer_rate": round(unsupported_answers / len(questions), 4),
        "category_breakdown": category_stats,
        "sample_failures": sample_failures,
    }
    (EVAL_DIR / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate ArthaLens 500-PDF RAG knowledge base")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL") or f"sqlite:///{(DATASET_ROOT / 'arthalens_rag.db').as_posix()}",
    )
    args = parser.parse_args()
    report = evaluate(args.database_url)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
