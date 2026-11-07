import json
import requests
import hashlib
from bs4 import BeautifulSoup
from preprocessing import clean_content
from ingestion import insert_data, select_data


def main():
    index = get_index()
    
    articles = []
    for url in index:
        page = get_page(url)
        insert_data(page, page['urlhash'])

        # articles.append(page)
    
    print(articles)
    
    # with open("result.json", "w", encoding="utf-8") as f:
    #     json.dump(articles, f, indent=4)
    
def get_index():
    base_url = "https://gizmologi.id"
    max_page = 2
    
    links = []
    for i in range(max_page):
        url = f"{base_url}/blog/page/{i}/?s=+"
        soup = request(url)

        for link in soup.select("a.p-url"):
            links.append(link.get("href"))
            
    return links 

def get_page(url):
    soup = request(url)
    
    paragraph = [text.get_text() for text 
                    in soup.select("p.wp-block-paragraph")]

    # add urlhash, tag 
    temp = {
        "urlhash" : hashlib.md5(url.encode("utf-8")).hexdigest(),
        "url": 
            url,
        "title": 
            soup.select_one("title").get_text(),
        "published_date": 
            "" if soup.select_one("meta[property='article:published_time']") is None
                else soup.select_one("meta[property='article:published_time']").get("content"),
        "content": clean_content(".".join(paragraph)),
        "tag": ", ".join([tag.get_text() for tag in soup.select("a[rel='tag']")]),
        "author": soup.select_one("a.meta-author-url").get_text()
                if soup.select_one("a.meta-author-url") is not None 
                else soup.select_one("a.meta-author-url").get('content')
    }
    
    return temp
    
def request(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text)
    return soup    


def clean_content(content):
    content_list = []
    exclude = [
        "Berlangganan untuk dapatkan pos terbaru lewat email."
        "Langganan sekarang agar bisa terus membaca dan mendapatkan akses ke semua arsip."
        ".Lanjutkan membaca"
        "baca juga-"
    ]
    
    for kalimat in content.split("."):
        text = content.replace("\u201d", "")
        text = content.replace("Baca Juga", "")
        text = text.replace("\u201c", "")

    for excl in exclude:
        if excl.lower() not in text.lower():
            content_list.append(text)

    return " ".join(content_list)

import psycopg2
from psycopg2.extras import RealDictCursor

def insert_data(data, urlhash):
    connect = psycopg2.connect("dbname=bronze user=l1 password=l1admin host=host.docker.internal port=5001")
    cursor = connect.cursor()

    query_select = "SELECT * FROM articles WHERE urlhash = %s"
    cursor.execute(query_select, (urlhash,))

    if cursor.fetchone is  None:
        
        query = """INSERT INTO articles
                (urlhash, urls, title,content, tag, published_date)
                VALUES
                (%s, %s, %s, %s, %s, %s)
                """
        cursor.execute(query, (
            data['urlhash'], data['url'], data['title'], 
            data['content'], data['tag'], data['published_date']

        ))
        connect.commit()


def select_data():
    connect = psycopg2.connect("dbname=bronze user=l1 password=l1admin host=localhost port=5001")
    cursor = connect.cursor(cursor_factory=RealDictCursor)

    query = "SELECT*FROM articles LIMIT 5"
    cursor.execute(query)

    for item in cursor.fetchall():
        print({
            'hash' : item['urlhash'],
            'title' : item['title'],
        })

        
if __name__ == '__main__':
    main()
    # select_data()