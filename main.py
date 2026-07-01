import requests
import sqlite3
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

# 从环境变量读取邮箱配置（GitHub Secrets）
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

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
    return new_count

def send_email(articles):
    """发送邮件简报"""
    if not articles:
        logging.info("没有新新闻，跳过邮件发送")
        return
    
    try:
        # 构建邮件内容
        today = datetime.now().strftime("%Y-%m-%d")
        html = f"<h2>📈 今日金融新闻简报 - {today}</h2><p>共 {len(articles)} 条新新闻</p ><hr>"
        
        for idx, art in enumerate(articles[:10], 1):
            html += f"""
            <div style="margin-bottom:15px; padding:10px; border-left: 3px solid #2980b9;">
                <h3 style="margin:0 0 5px 0;">{idx}. <a href=" 'link']}" style="color:#2980b9;">{art['title']}</a ></h3>
                <p style="color:#555; margin:5px 0;">{art['summary']}</p >
                <small style="color:#888;">{art['published']}</small>
            </div>
            <hr>
            """
        html += "<p style='color:gray;'>⚠️ 本简报由AI自动生成，仅供参考，不构成投资建议。</p >"
        
        # 发送邮件
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"📈 金融新闻简报 {today}"
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        logging.info(f"✅ 邮件发送成功！共 {len(articles)} 条新闻")
    except Exception as e:
        logging.error(f"邮件发送失败: {e}")

if __name__ == "__main__":
    logging.info("开始执行...")
    articles = fetch_news()
    if articles:
        new_count = save_to_db(articles)
        if new_count > 0:
            send_email(articles)
        else:
            logging.info("没有新新闻，不发送邮件")
    else:
        logging.info("未抓取到新闻")
    logging.info("执行完成")
