import requests
import sqlite3
import os
import logging
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

def fetch_news():
    logging.info("正在抓取新闻...")
    articles = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = "https://finance.sina.com.cn/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and '.shtml' in href:
                if href.startswith('/'):
                    full_link = 'https://finance.sina.com.cn' + href
                else:
                    full_link = href
                articles.append({
                    "title": title[:100],
                    "link": full_link,
                    "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": "来源: 新浪财经"
                })
                if len(articles) >= 10:
                    break
        logging.info(f"抓取到 {len(articles)} 条新闻")
    except Exception as e:
        logging.error(f"抓取失败: {e}")
    return articles

def save_to_db(articles):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT, link TEXT, published TEXT, 
                  summary TEXT, ai_summary TEXT, created_at TEXT)''')
    new_count = 0
    for art in articles:
        try:
            c.execute("SELECT id FROM news WHERE title=?", (art["title"],))
            if c.fetchone():
                continue
            c.execute("INSERT INTO news (title, link, published, summary, created_at) VALUES (?,?,?,?,?)",
                      (art["title"], art["link"], art["published"], art["summary"], datetime.now().isoformat()))
            new_count += 1
        except Exception as e:
            logging.error(f"入库出错: {e}")
    conn.commit()
    conn.close()
    logging.info(f"新增 {new_count} 条新闻")

if __name__ == "__main__":
    logging.info("开始执行...")
    articles = fetch_news()
    if articles:
        save_to_db(articles)
        logging.info(f"成功抓取 {len(articles)} 条新闻")
    else:
        logging.info("未抓取到新闻")
    logging.info("执行完成")
