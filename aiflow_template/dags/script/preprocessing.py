import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import re

# --- KONFIGURASI DATABASE ---
DB_BRONZE = {
    "dbname": "bronze", "user": "l1", "password": "l1admin",
    "host": "host.docker.internal", "port": "5001",
}
DB_DW = {
    "dbname": "dw", "user": "l1", "password": "l1admin",
    "host": "host.docker.internal", "port": "5001", # Port host yang sama
}

analyzer = SentimentIntensityAnalyzer()

def get_or_create_dimension(cursor, table, id_col, name_col, value, extra_col=None, extra_val=None):
    """Fungsi bantu untuk insert atau ambil ID dari tabel dimensi"""
    cursor.execute(f"SELECT {id_col} FROM {table} WHERE {name_col} = %s", (value,))
    row = cursor.fetchone()
    
    # PERBAIKAN: row adalah Tuple, jadi akses pakai indeks [0], bukan [id_col]
    if row:
        return row[0] 
    
    if extra_col:
        query = f"INSERT INTO {table} ({name_col}, {extra_col}) VALUES (%s, %s) RETURNING {id_col}"
        cursor.execute(query, (value, extra_val))
    else:
        query = f"INSERT INTO {table} ({name_col}) VALUES (%s) RETURNING {id_col}"
        cursor.execute(query, (value,))
    
    # PERBAIKAN: Ambil nilai kembalian dari RETURNING id_col
    return cursor.fetchone()[0]

def clean_text(text):
    """Membersihkan teks dari karakter aneh dan peringatan ANTARA"""
    if not text: return ""
    # Hapus peringatan copyright
    text = re.sub(r'Dilarang keras mengambil konten.*', '', text, flags=re.IGNORECASE)
    # Hapus karakter non-alfanumerik (kecuali spasi dan tanda baca dasar)
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    return text.strip()

def determine_category(text):
    """Menentukan kategori berdasarkan keyword MU di PDF"""
    text_lower = text.lower()
    if "transfer" in text_lower or "rumor" in text_lower:
        return "Transfer"
    elif "cedera" in text_lower or "absen" in text_lower:
        return "Cedera"
    elif "carrick" in text_lower or "pelatih" in text_lower:
        return "Isu Manajer"
    elif "old trafford" in text_lower:
        return "Old Trafford"
    else:
        return "Match Report"

def process_data():
    print("=== Memulai Transformasi Data (DAG 2) ===")
    
    try:
        conn_bronze = psycopg2.connect(**DB_BRONZE)
        cur_bronze = conn_bronze.cursor(cursor_factory=RealDictCursor)
        
        conn_dw = psycopg2.connect(**DB_DW)
        cur_dw = conn_dw.cursor()
        
        # 1. Ambil data dari Bronze
        cur_bronze.execute("SELECT article_id, title, author, source_name, publish_date, content_body FROM articles")
        articles = cur_bronze.fetchall()
        print(f"[*] Memproses {len(articles)} artikel...")

        # 2. Siapkan Data Source & Waktu Dasar
        source_id = get_or_create_dimension(cur_dw, "dim_source", "source_id", "source_name", "ANTARA News", "domain_url", "antaranews.com")

        for art in articles:
            # Bersihkan teks
            clean_content = clean_text(art['content_body'])
            clean_title = clean_text(art['title'])
            
            # Hitung Sentimen (VADER)
            sentiment = analyzer.polarity_scores(clean_content)
            score = sentiment['compound'] # Skor -1 (negatif) sampai +1 (positif)
            word_count = len(clean_content.split())
            
            # Tentukan Kategori
            category_name = determine_category(clean_title + " " + clean_content)
            category_id = get_or_create_dimension(cur_dw, "dim_category", "category_id", "category_name", category_name)

            # Handle Waktu (Dim Date)
            pub_date = art['publish_date']
            if pub_date:
                full_date = pub_date.date()
                date_id = get_or_create_dimension(cur_dw, "dim_date", "date_id", "full_date", full_date)
            else:
                date_id = None

            # Handle Artikel (Dim Article)
            cur_dw.execute("SELECT article_sk FROM dim_article WHERE article_id = %s", (art['article_id'],))
            existing_art = cur_dw.fetchone()
            if existing_art:
                article_sk = existing_art[0] # <-- Pastikan ini [0], bukan ['article_sk']
            else:
                cur_dw.execute(
                    "INSERT INTO dim_article (article_id, title, author, url) VALUES (%s, %s, %s, %s) RETURNING article_sk",
                    (art['article_id'], art['title'], art['author'], f"https://antaranews.com/berita/{art['article_id']}")
                )
                article_sk = cur_dw.fetchone()[0]
                
            # Insert ke Fact Table
            cur_dw.execute("""
                INSERT INTO fact_news_sentiment (article_sk, date_id, source_id, category_id, sentiment_score, word_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (article_sk, date_id, source_id, category_id, score, word_count))
            
            print(f"   [+] {art['title'][:40]}... | Score: {score:.2f} | Kat: {category_name}")

        conn_dw.commit()
        print("[+] Transformasi Selesai dan berhasil masuk ke Data Warehouse!")
        
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        if 'cur_bronze' in locals(): cur_bronze.close()
        if 'conn_bronze' in locals(): conn_bronze.close()
        if 'cur_dw' in locals(): cur_dw.close()
        if 'conn_dw' in locals(): conn_dw.close()

if __name__ == "__main__":
    process_data()