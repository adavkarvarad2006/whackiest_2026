-- ArthaLens Large-Scale RAG Knowledge Base Schema (PostgreSQL + pgvector)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    age INTEGER NOT NULL,
    occupation VARCHAR(120) NOT NULL,
    employer VARCHAR(200) NOT NULL,
    city VARCHAR(120) NOT NULL,
    pan_masked VARCHAR(32) NOT NULL,
    profile_category VARCHAR(60) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag_documents (
    document_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(80) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    page_count INTEGER NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rag_doc_cust_hash UNIQUE (customer_id, file_hash)
);

CREATE INDEX IF NOT EXISTS ix_rag_docs_cust ON rag_documents(customer_id);
CREATE INDEX IF NOT EXISTS ix_rag_docs_type ON rag_documents(customer_id, document_type);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    document_id VARCHAR(64) NOT NULL REFERENCES rag_documents(document_id) ON DELETE CASCADE,
    document_type VARCHAR(80) NOT NULL,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    extracted_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rag_chunks_cust ON rag_chunks(customer_id);
CREATE INDEX IF NOT EXISTS ix_rag_chunks_cust_doc ON rag_chunks(customer_id, document_id);
CREATE INDEX IF NOT EXISTS ix_rag_chunks_hnsw ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_rag_chunks_gin ON rag_chunks USING gin (to_tsvector('english', extracted_text));

CREATE TABLE IF NOT EXISTS customer_financial_facts (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    fact_type VARCHAR(80) NOT NULL,
    institution VARCHAR(200) NOT NULL,
    account_reference VARCHAR(120),
    numeric_value NUMERIC(15, 2) NOT NULL DEFAULT 0,
    status VARCHAR(80) NOT NULL,
    maturity_date DATE,
    source_document_id VARCHAR(64) NOT NULL REFERENCES rag_documents(document_id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL DEFAULT 1,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_facts_cust_type ON customer_financial_facts(customer_id, fact_type);
