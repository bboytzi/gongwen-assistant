-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS zhparser;

-- Create Chinese full-text search configuration
CREATE TEXT SEARCH CONFIGURATION chinese_zh (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION chinese_zh
    ADD MAPPING FOR n,v,a,i,e,l WITH simple;

-- Add search_tsv column to kb_documents (full-text search)
ALTER TABLE kb_documents
    ADD COLUMN IF NOT EXISTS search_tsv tsvector;

-- Create GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_kb_documents_search_tsv
    ON kb_documents USING GIN(search_tsv);

-- Create trigger to auto-update search_tsv
CREATE OR REPLACE FUNCTION update_kb_search_tsv() RETURNS trigger AS $$
BEGIN
    NEW.search_tsv := to_tsvector('chinese_zh', coalesce(NEW.title, '') || ' ' || coalesce(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kb_documents_search_tsv ON kb_documents;
CREATE TRIGGER trg_kb_documents_search_tsv
    BEFORE INSERT OR UPDATE ON kb_documents
    FOR EACH ROW EXECUTE FUNCTION update_kb_search_tsv();

-- Create IVFFlat index for vector similarity search (on document_chunks.embedding)
-- Note: embedding column is added as vector(1024) type via raw SQL since SQLAlchemy doesn't support pgvector natively
DO $$
BEGIN
    -- Check if embedding column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'document_chunks' AND column_name = 'embedding'
    ) THEN
        -- Add embedding column as vector type
        EXECUTE 'ALTER TABLE document_chunks ADD COLUMN embedding vector(1024)';
    END IF;
END $$;

-- Create vector index
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Add trigram similarity index for keyword fallback
CREATE INDEX IF NOT EXISTS idx_kb_documents_title_trgm
    ON kb_documents USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_kb_documents_content_trgm
    ON kb_documents USING GIN (content gin_trgm_ops);
