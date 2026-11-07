import hashlib
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# ==========================================
# KONFIGURASI DATABASE STAGING (bronze)
# ==========================================
DB_CONFIG = {
    "dbname":   os.getenv("DB_NAME", "bronze"),
    "user":     os.getenv("DB_USER", "l1"),
    "password": os.getenv("DB_PASSWORD", "l1admin"),
    "host":     os.getenv("DB_HOST", "host.docker.internal"),
    "port":     os.getenv("DB_PORT", "5001"),
}


def generate_article_id(url: str) -> str:
    """MD5 hash dari URL → article_id (sesuai arsitektur)."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def parse_publish_date(date_str):
    """String tanggal → datetime. Return None jika tidak valid."""
    if not date_str or date_str == "Tidak ada tanggal":
        return None
    try:
        iso_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_str)
    except (ValueError, AttributeError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d %B %Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    print(f"[!] Format tanggal tidak dikenali: {date_str}")
    return None


def insert_staging(data: dict) -> bool:
    """
    Insert satu artikel ke bronze.articles.
    Return True jika insert, False jika duplikat/gagal.
    """
    article_id = generate_article_id(data["url"])
    publish_date = parse_publish_date(data.get("publish_date"))

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Deduplikasi MD5
        cursor.execute(
            "SELECT 1 FROM articles WHERE article_id = %s LIMIT 1",
            (article_id,),
        )
        if cursor.fetchone() is not None:
            print(f"   [=] Duplikat, skip: {data['title'][:60]}...")
            cursor.close()
            conn.close()
            return False

        cursor.execute(
            """
            INSERT INTO articles
                (article_id, title, publish_date, source_name, content_body, author)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                article_id,
                data.get("title"),
                publish_date,
                data.get("source_name", "ANTARA News"),
                data.get("content"),
                data.get("author"),
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"   [+] Inserted: {data['title'][:60]}...")
        return True

    except Exception as e:
        print(f"   [!] Gagal insert: {e}")
        return False


def select_staging(limit: int = 5):
    """Utility verifikasi: tampilkan baris terakhir staging."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT article_id, title, publish_date, source_name "
            "FROM articles ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        for row in cursor.fetchall():
            print({
                "article_id": row["article_id"][:8] + "...",
                "title": row["title"][:60],
                "publish_date": row["publish_date"],
                "source_name": row["source_name"],
            })
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[!] Gagal select: {e}")