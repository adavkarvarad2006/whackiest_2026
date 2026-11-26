-- ArthaLens PostgreSQL + pgvector Schema
-- Enables pgvector extension and creates all normalized tables with strict user-level isolation.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(80) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_status VARCHAR(40) NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    CONSTRAINT uq_documents_user_hash UNIQUE (user_id, file_hash)
);

CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS ix_documents_user_type ON documents(user_id, document_type);

CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_chunks_user_id ON document_chunks(user_id);
CREATE INDEX IF NOT EXISTS ix_chunks_user_doc ON document_chunks(user_id, document_id);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_chunks_text_gin
    ON document_chunks USING gin (to_tsvector('english', chunk_text));

CREATE TABLE IF NOT EXISTS financial_assets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_type VARCHAR(60) NOT NULL,
    institution VARCHAR(200) NOT NULL,
    account_reference VARCHAR(120),
    amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
    nominee_status VARCHAR(60) NOT NULL DEFAULT 'UNKNOWN',
    maturity_date DATE,
    source_document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL DEFAULT 1,
    extracted_text TEXT,
    confidence VARCHAR(40) NOT NULL DEFAULT 'MEDIUM',
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_assets_user_id ON financial_assets(user_id);
CREATE INDEX IF NOT EXISTS ix_assets_user_type ON financial_assets(user_id, asset_type);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    transaction_date DATE NOT NULL,
    description VARCHAR(500) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    category VARCHAR(80) NOT NULL DEFAULT 'OTHER',
    reference_no VARCHAR(100),
    page_number INTEGER NOT NULL DEFAULT 1,
    confidence VARCHAR(40) NOT NULL DEFAULT 'HIGH'
);

CREATE INDEX IF NOT EXISTS ix_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS ix_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX IF NOT EXISTS ix_transactions_user_cat ON transactions(user_id, category);

CREATE TABLE IF NOT EXISTS findings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    finding_type VARCHAR(80) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence VARCHAR(40) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(40) NOT NULL DEFAULT 'OPEN',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_findings_user_id ON findings(user_id);
CREATE INDEX IF NOT EXISTS ix_findings_user_severity ON findings(user_id, severity);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'Ask ArthaLens Session',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations(user_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    confidence VARCHAR(40),
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieval_mode VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_conv_user ON chat_messages(conversation_id, user_id);
