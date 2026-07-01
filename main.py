import requests
import sqlite3
import os
import logging
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

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
                
                # 获取文章摘要（抓取正文前几句）
                summary = fetch_article_summary(full_link, headers)
                if not summary:
                    summary = "来源: 新浪财经"
                
                articles.append({
                    "title": title[:100],
                    "link": full_link,
                    "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": summary
                })
                if len(articles) >= 10:
                    break
        logging.info("抓取到 " + str(len(articles)) + " 条新闻")
    except Exception as e:
        logging.error("抓取失败: " + str(e))
    return articles

def fetch_article_summary(url, headers):
    """从文章页面提取摘要（正文前几句）"""
    try:
        response = requests.get(url, headers=headers, timeout=8)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找文章正文
        article_body = soup.find('div', {'class': 'article'}) or soup.find('div', {'id': 'article'}) or soup.find('div', class_=re.compile(r'content|article|body'))
        
        if article_body:
            # 提取所有段落
            paragraphs = article_body.find_all('p')
            text_parts = []
            for p in paragraphs[:3]:  # 取前3段
                text = p.get_text().strip()
                if len(text) > 20:  # 过滤掉太短的
                    text_parts.append(text)
            
            if text_parts:
                summary = ' '.join(text_parts)[:200]  # 取前200字
                return summary
        
        # 备用方法：找所有文本
        texts = soup.find_all('p')
        for p in texts[:5]:
            text = p.get_text().strip()
            if len(text) > 30:
                return text[:200]
        
        return ""
    except Exception as e:
        logging.warning("获取文章摘要失败: " + str(e))
        return ""

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
            logging.error("入库出错: " + str(e))
    conn.commit()
    conn.close()
    logging.info("新增 " + str(new_count) + " 条新闻")
    return new_count

def send_email(articles):
    if not articles:
        logging.info("没有新新闻，跳过邮件发送")
        return
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        html = "<h2>📈 今日金融新闻简报 - " + today + "</h2>"
        html += "<p>共 " + str(len(articles)) + " 条新闻</p ><hr>"
        
        for idx, art in enumerate(articles[:15], 1):
            html += '<div style="margin-bottom:15px; padding:10px; border-left: 3px solid #2980b9;">'
            html += '<h3 style="margin:0 0 5px 0;">' + str(idx) + '. <a href="' + art['link'] + '" style="color:#2980b9;">' + art['title'] + '</a ></h3>'
            
            # 摘要部分
            summary = art['summary']
            if summary and len(summary) > 5:
                html += '<p style="color:#555; margin:5px 0; font-size:14px;">📌 ' + summary + '</p >'
            
            html += '<small style="color:#888;">🕐 ' + art['published'] + ' | 🔗 <a href="' + art['link'] + '" style="color:#2980b9;">查看原文</a ></small>'
            html += '</div><hr>'
        
        html += "<p style='color:gray;'>⚠️ 本简报仅供参考，不构成投资建议。</p >"
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = "📈 金融新闻简报 " + today
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        logging.info("邮件发送成功！共 " + str(len(articles)) + " 条新闻")
    except Exception as e:
        logging.error("邮件发送失败: " + str(e))

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
