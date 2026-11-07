import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

from ingestion import insert_staging, select_staging

# ==========================================
# KONFIGURASI
# ==========================================
BASE_URL = "https://www.antaranews.com/sepakbola/liga-inggris-premier"
SOURCE_NAME = "ANTARA News"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def request_url(url):
    """Ambil HTML → BeautifulSoup, atau None jika gagal."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"  [!] Gagal request ke {url}: {e}")
        return None


def get_index():
    """Ambil daftar URL artikel Liga Inggris dari halaman indeks."""
    print(f"[*] Mengakses halaman indeks: {BASE_URL}")
    soup = request_url(BASE_URL)
    if not soup:
        return []

    for garbage in soup.select(".pagination, nav, footer, .footer, aside, .sidebar"):
        garbage.decompose()

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title_text = a.get_text(strip=True)

        if "/berita/" in href:
            full_url = urljoin(BASE_URL, href)
            if len(title_text) > 20 and full_url not in links:
                if any(
                    x in title_text.lower()
                    for x in ["infografik", "foto", "video", "baca juga"]
                ):
                    continue
                links.append(full_url)

    print(f"  [+] Ditemukan {len(links)} artikel murni Liga Inggris.")
    return links


def get_page(url):
    """Ekstrak detail satu artikel. Return dict atau None."""
    soup = request_url(url)
    if not soup:
        return None

    # 1. JUDUL
    title = "Tanpa Judul"
    h1_tag = soup.find("h1")
    if h1_tag:
        title = h1_tag.get_text(strip=True)
    elif soup.title and soup.title.string:
        title = soup.title.string.split(" - ANTARA News")[0].strip()

    # 2. KATEGORI
    category = "Liga Inggris"
    meta_section = soup.select_one('meta[property="article:section"]')
    if meta_section and meta_section.get("content"):
        category = meta_section["content"]

    # 3. TANGGAL
    publish_date = "Tidak ada tanggal"
    meta_date = soup.select_one('meta[property="article:published_time"]')
    if meta_date and meta_date.get("content"):
        publish_date = meta_date["content"]
    else:
        date_elem = soup.select_one("span.article-date") or soup.select_one(
            "span.text-secondary"
        )
        if date_elem:
            publish_date = date_elem.get_text(strip=True)

    # 4. PENULIS
    author = "Redaksi ANTARA News"
    for p in soup.find_all("p"):
        p_text = p.get_text()
        if "Pewarta:" in p_text:
            author = p_text.split("Editor:")[0].replace("Pewarta:", "").strip()
            break

    # 5. KONTEN
    paragraphs = []
    content_area = (
        soup.select_one(".post-content")
        or soup.select_one(".wrap__article-detail-content")
        or soup.find("article")
    )

    if content_area:
        for p in content_area.find_all("p"):
            p_clean = p.get_text(strip=True)
            if (
                p_clean
                and not p_clean.lower().startswith("baca juga:")
                and not p_clean.startswith("Pewarta:")
                and not p_clean.startswith("Copyright ©")
            ):
                paragraphs.append(p_clean)
    else:
        for p in soup.find_all("p"):
            p_clean = p.get_text(strip=True)
            if (
                len(p_clean) > 40
                and not p_clean.lower().startswith("baca juga")
                and not p_clean.startswith("Pewarta:")
            ):
                paragraphs.append(p_clean)

    content_preview = " ".join(paragraphs) if paragraphs else "Konten tidak terbaca"

    return {
        "url": url,
        "title": title,
        "category": category,
        "publish_date": publish_date,
        "author": author,
        "content": content_preview,
        "source_name": SOURCE_NAME,   # ← ditambahkan agar ingestion tidak pakai default
    }


def main():
    """Alur DAG 1: scrape → filter → insert staging → simpan JSON (debug)."""
    print("=== DAG 1: MU News Ingestion (ANTARA) ===")
    index_links = get_index()
    if not index_links:
        print("[!] Tidak ada link. Proses dihentikan.")
        return

    print(f"\n[*] Memproses {len(index_links)} artikel...\n")

    articles = []
    inserted = 0
    skipped = 0

    for i, url in enumerate(index_links, 1):
        print(f"[{i}/{len(index_links)}] {url}")
        page_data = get_page(url)

        if not page_data:
            print("   ✗ Gagal ekstrak.")
            continue

        # Filter konten kosong → jangan masuk DB (ganggu VADER)
        if page_data["content"] == "Konten tidak terbaca":
            print("   ✗ Konten kosong, skip insert.")
            articles.append(page_data)  # tetap simpan ke JSON untuk audit
            continue

        articles.append(page_data)
        ok = insert_staging(page_data)
        inserted += 1 if ok else 0
        skipped += 0 if ok else 1

        print(f"   ✓ Judul : {page_data['title'][:60]}")
        print(f"   ✓ Tanggal: {page_data['publish_date']}")
        print(f"   ✓ Konten : {len(page_data['content'])} karakter")
        print("-" * 50)
        time.sleep(1)

    # Simpan JSON untuk debugging
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=4, ensure_ascii=False)

    print(f"\n[+] Selesai. Inserted: {inserted}, Skipped/Duplikat: {skipped}")
    print(f"[+] JSON debug: {output_path}")

    print("\n=== 5 Baris Terakhir di Staging ===")
    select_staging(limit=5)


if __name__ == "__main__":
    main()