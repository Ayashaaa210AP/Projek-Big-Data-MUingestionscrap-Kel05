DROP TABLE IF EXISTS articles;

CREATE TABLE articles (
    id            SERIAL PRIMARY KEY,
    article_id    VARCHAR(64) NOT NULL UNIQUE,   -- MD5 hash URL
    title         TEXT,
    publish_date  TIMESTAMP,
    source_name   VARCHAR(50),
    content_body  TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_articles_article_id ON articles(article_id);
CREATE INDEX idx_articles_publish_date ON articles(publish_date);