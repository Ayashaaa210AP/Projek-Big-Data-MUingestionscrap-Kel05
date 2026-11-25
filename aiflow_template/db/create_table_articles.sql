-- ==========================================
-- SETUP TABEL STAGING: bronze.articles
-- Aman dijalankan berulang kali (tidak menghapus data).
-- Jalankan script ini saat terhubung ke database "bronze" (port 5001).
-- ==========================================

CREATE TABLE IF NOT EXISTS articles (
    id            SERIAL PRIMARY KEY,
    article_id    VARCHAR(64) NOT NULL UNIQUE,   -- MD5 hash dari URL
    title         TEXT,
    publish_date  TIMESTAMP,
    source_name   VARCHAR(50),
    content_body  TEXT,
    author        VARCHAR(100),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Untuk database lama yang tabelnya dibuat sebelum kolom "author" ditambahkan.
-- ingestion.py melakukan INSERT ke kolom author, jadi kolom ini WAJIB ada.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS author VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_articles_article_id ON articles(article_id);
CREATE INDEX IF NOT EXISTS idx_articles_publish_date ON articles(publish_date);