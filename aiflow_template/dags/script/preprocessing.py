import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import re
from transformers import pipeline

# --- KONFIGURASI DATABASE ---
DB_BRONZE = {
    "dbname": "bronze", "user": "l1", "password": "l1admin",
    "host": "host.docker.internal", "port": "5001",
}
DB_DW = {
    "dbname": "dw", "user": "l1", "password": "l1admin",
    "host": "host.docker.internal", "port": "5001",
}

# Mapping label KHUSUS untuk model mdhugol
# Berdasarkan dokumentasi IndoNLU SmSA: 0=Positif, 1=Netral, 2=Negatif
LABEL_MAP = {
    'LABEL_0': 'Positif',
    'LABEL_1': 'Netral',
    'LABEL_2': 'Negatif'
}

# --- FUNGSI EKSTRAKSI KONTEKS MU ---
def extract_mu_context(text):
    pattern = r'\b(manchester united|mu|setan merah|carrick|old trafford|red devils|mufc)\b'
    sentences = re.split(r'(?<=[.!?])\s+', text)
    mu_sentences = [s for s in sentences if re.search(pattern, s, re.IGNORECASE)]
    return " ".join(mu_sentences)

# --- FUNGSI BANTU LAINNYA ---
def get_or_create_dimension(cursor, table, id_col, name_col, value, extra_col=None, extra_val=None):
    cursor.execute(f"SELECT {id_col} FROM {table} WHERE {name_col} = %s", (value,))
    row = cursor.fetchone()
    if row: return row[0]
    if extra_col:
        cursor.execute(f"INSERT INTO {table} ({name_col}, {extra_col}) VALUES (%s, %s) RETURNING {id_col}", (value, extra_val))
    else:
        cursor.execute(f"INSERT INTO {table} ({name_col}) VALUES (%s) RETURNING {id_col}", (value,))
    return cursor.fetchone()[0]

def clean_text(text):
    if not text: return ""
    text = re.sub(r'Dilarang keras mengambil konten.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    return text.strip()

def determine_category(text):
    text_lower = text.lower()
    if "transfer" in text_lower or "rumor" in text_lower: return "Transfer"
    elif "cedera" in text_lower or "absen" in text_lower: return "Cedera"
    elif "carrick" in text_lower or "pelatih" in text_lower: return "Isu Manajer"
    elif "old trafford" in text_lower: return "Old Trafford"
    else: return "Match Report"

# --- PROSES UTAMA ---
def process_data():
    print("=== Memulai Transformasi Data (DAG 2 - IndoBERT mdhugol) ===")
    
    # 1. Muat model DI DALAM fungsi agar tidak timeout saat import DAG
    model_name = "mdhugol/indonesia-bert-sentiment-classification"
    print(f"[*] Memuat model IndoBERT: {model_name}...")
    sentiment_pipeline = pipeline("sentiment-analysis", model=model_name, tokenizer=model_name)
    print("[+] Model IndoBERT berhasil dimuat.")

    try:
        conn_bronze = psycopg2.connect(**DB_BRONZE)
        cur_bronze = conn_bronze.cursor(cursor_factory=RealDictCursor)
        conn_dw = psycopg2.connect(**DB_DW)
        cur_dw = conn_dw.cursor()

        cur_bronze.execute("SELECT article_id, title, author, source_name, publish_date, content_body FROM articles")
        articles = cur_bronze.fetchall()
        print(f"[*] Memproses {len(articles)} artikel...")

        source_id = get_or_create_dimension(cur_dw, "dim_source", "source_id", "source_name", "ANTARA News", "domain_url", "antaranews.com")

        for art in articles:
            clean_content = clean_text(art['content_body'])
            clean_title = clean_text(art['title'])

            # Ekstrak kalimat yang membahas MU
            mu_content = extract_mu_context(clean_content)
            if not mu_content:
                pattern = r'\b(manchester united|mu|setan merah|carrick|old trafford|red devils|mufc)\b'
                if re.search(pattern, clean_title, re.IGNORECASE):
                    mu_content = clean_title

            if not mu_content:
                sentiment_label = "Netral"
            else:
                # Prediksi sentimen (batasi 512 token)
                result = sentiment_pipeline(mu_content[:512])[0]
                raw_label = result['label']
                sentiment_label = LABEL_MAP.get(raw_label, "Netral")
                
                # --- DEBUG PRINT: Hapus ini jika sudah yakin ---
                print(f"   [DEBUG] Teks: {mu_content[:50]}... | Raw Label: {raw_label} ({result['score']:.2f}) -> {sentiment_label}")
                # -----------------------------------------------

            word_count = len(clean_content.split())

            # Tentukan Kategori
            category_name = determine_category(clean_title + " " + clean_content)
            category_id = get_or_create_dimension(cur_dw, "dim_category", "category_id", "category_name", category_name)

            # Handle Waktu (Dim Date)
            pub_date = art['publish_date']
            if pub_date:
                date_id = get_or_create_dimension(cur_dw, "dim_date", "date_id", "full_date", pub_date.date())
            else:
                date_id = None

            # Handle Artikel (Dim Article)
            cur_dw.execute("SELECT article_sk FROM dim_article WHERE article_id = %s", (art['article_id'],))
            existing_art = cur_dw.fetchone()
            if existing_art:
                article_sk = existing_art[0]
            else:
                cur_dw.execute(
                    "INSERT INTO dim_article (article_id, title, author, url) VALUES (%s, %s, %s, %s) RETURNING article_sk",
                    (art['article_id'], art['title'], art['author'], f"https://antaranews.com/berita/{art['article_id']}")
                )
                article_sk = cur_dw.fetchone()[0]

            # Insert ke Fact Table (Anti-Duplikat)
            cur_dw.execute("SELECT 1 FROM fact_news_sentiment WHERE article_sk = %s", (article_sk,))
            if cur_dw.fetchone() is None:
                cur_dw.execute("""
                    INSERT INTO fact_news_sentiment (article_sk, date_id, source_id, category_id, sentiment_label, word_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (article_sk, date_id, source_id, category_id, sentiment_label, word_count))
                print(f"   [+] {art['title'][:40]}... | Sentimen: {sentiment_label} | Kat: {category_name}")
            else:
                print(f"   [=] Skip fact table (sudah ada): {art['title'][:40]}...")

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