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

# ===== 邮箱、网站配置（从GitHub密钥读取） =====
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
API_SECRET = os.getenv("API_SECRET")  # 接口密钥，和线上app一致
SITE_URL = "https://ppy.pythonanywhere.com"  # 你的网站地址

def get_online_subscribers():
    """实时访问网站接口，读取所有网页订阅用户，不再读取本地txt"""
    try:
        # 拼接带密钥的接口地址
        api_url = f"{SITE_URL}/api/subscribers?secret={API_SECRET}"
        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        email_list = [item["email"] for item in data]
        logging.info(f"✅ 从线上网站获取订阅用户共 {len(email_list)} 人")
        return email_list
    except Exception as e:
        logging.error(f"❌ 拉取订阅邮箱失败：{str(e)}")
        # 读取失败直接返回空列表，不发送邮件
        return []

def fetch_article_summary(url, headers):
    try:
        response = requests.get(url, headers=headers, timeout=8)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        article_body = soup.find('div', {'class': 'article'}) or soup.find('div', {'id': 'article'})
        if article_body:
            paragraphs = article_body.find_all('p')
            text_parts = []
            for p in paragraphs[:3]:
                text = p.get_text().strip()
                if len(text) > 20:
                    text_parts.append(text)
            if text_parts:
                return ' '.join(text_parts)[:200]
        texts = soup.find_all('p')
        for p in texts[:5]:
            text = p.get_text().strip()
            if len(text) > 30:
                return text[:200]
        return ""
    except:
        return ""

def fetch_sina_news(headers):
    articles = []
    try:
        logging.info("抓取 新浪财经...")
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
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                if any(keyword in full_link for keyword in ['video', 'topic', 'slide']):
                    continue
                summary = fetch_article_summary(full_link, headers)
                if not summary:
                    summary = "来源: 新浪财经"
                articles.append({
                    "title": title[:100],
                    "link": full_link,
                    "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": summary,
                    "source": "新浪财经"
                })
                if len(articles) >= 6:
                    break
        logging.info("新浪财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logging.error("新浪财经抓取失败: " + str(e))
    return articles

def fetch_eastmoney_news(headers):
    articles = []
    try:
        logging.info("抓取 东方财富...")
        url = "https://www.eastmoney.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and '.html' in href:
                if href.startswith('/'):
                    full_link = 'https://www.eastmoney.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                if 'news' in full_link or 'stock' in full_link:
                    summary = fetch_article_summary(full_link, headers)
                    if not summary:
                        summary = "来源: 东方财富"
                    articles.append({
                        "title": title[:100],
                        "link": full_link,
                        "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "summary": summary,
                        "source": "东方财富"
                    })
                    if len(articles) >= 6:
                        break
        logging.info("东方财富抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logging.error("东方财富抓取失败: " + str(e))
    return articles

def fetch_tencent_news(headers):
    articles = []
    try:
        logging.info("抓取 腾讯财经...")
        url = "https://finance.qq.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and '.html' in href:
                if href.startswith('/'):
                    full_link = 'https://finance.qq.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                if 'video' not in full_link:
                    summary = fetch_article_summary(full_link, headers)
                    if not summary:
                        summary = "来源: 腾讯财经"
                    articles.append({
                        "title": title[:100],
                        "link": full_link,
                        "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "summary": summary,
                        "source": "腾讯财经"
                    })
                    if len(articles) >= 6:
                        break
        logging.info("腾讯财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logging.error("腾讯财经抓取失败: " + str(e))
    return articles

def fetch_163_news(headers):
    articles = []
    try:
        logging.info("抓取 网易财经...")
        url = "https://money.163.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and ('.html' in href or '.shtml' in href):
                if href.startswith('/'):
                    full_link = 'https://money.163.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                if 'video' not in full_link:
                    summary = fetch_article_summary(full_link, headers)
                    if not summary:
                        summary = "来源: 网易财经"
                    articles.append({
                        "title": title[:100],
                        "link": full_link,
                        "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "summary": summary,
                        "source": "网易财经"
                    })
                    if len(articles) >= 6:
                        break
        logging.info("网易财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logging.error("网易财经抓取失败: " + str(e))
    return articles

def fetch_news():
    logging.info("正在从多个财经网站抓取新闻...")
    all_articles = []
    seen_titles = set()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    sources = [fetch_sina_news, fetch_eastmoney_news, fetch_tencent_news, fetch_163_news]
    for fetch_func in sources:
        try:
            articles = fetch_func(headers)
            for art in articles:
                if art['title'] not in seen_titles:
                    seen_titles.add(art['title'])
                    all_articles.append(art)
        except Exception as e:
            logging.error("来源抓取出错: " + str(e))
    if len(all_articles) < 3:
        logging.info("抓取数量不足，使用备用数据")
        all_articles = [
            {"title": "A股三大指数震荡整理，沪指微涨", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "市场整体平稳，成交量有所萎缩", "source": "新浪财经"},
            {"title": "央行开展逆回购操作维护流动性", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "公开市场操作保持合理充裕", "source": "新浪财经"},
        ]
    logging.info("总共抓取到 " + str(len(all_articles)) + " 条新闻")
    return all_articles

def save_to_db(articles):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(news)")
    columns = [col[1] for col in c.fetchall()]
    if 'source' not in columns:
        logging.info("检测到旧表结构，正在重建...")
        c.execute("DROP TABLE IF EXISTS news")
        c.execute('''CREATE TABLE news
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      title TEXT, link TEXT, published TEXT, 
                      summary TEXT, source TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscribers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE,
                  subscribed_at TEXT)''')
    new_count = 0
    for art in articles:
        try:
            c.execute("SELECT id FROM news WHERE title=?", (art["title"],))
            if c.fetchone():
                continue
            c.execute("INSERT INTO news (title, link, published, summary, source, created_at) VALUES (?,?,?,?,?,?)",
                      (art["title"], art["link"], art["published"], art["summary"], art.get("source", "未知来源"), datetime.now().isoformat()))
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
    # 核心改动：调用线上接口读取订阅，废弃txt文件
    subscribers = get_online_subscribers()
    if not subscribers:
        logging.info("无任何订阅用户，跳过邮件发送")
        return
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        html = "<h2>📈 今日金融新闻简报 - " + today + "</h2>"
        html += "<p>共 " + str(len(articles)) + " 条新闻</p><hr>"
        for idx, art in enumerate(articles[:15], 1):
            source_tag = art.get("source", "未知来源")
            html += '<div style="margin-bottom:15px; padding:10px; border-left: 3px solid #2980b9;">'
            html += '<h3 style="margin:0 0 5px 0;">' + str(idx) + '. <a href="' + art['link'] + '" style="color:#2980b9;">' + art['title'] + '</a></h3>'
            html += '<span style="font-size:12px; color:#2980b9; background:#e8f0fe; padding:2px 10px; border-radius:12px;">📰 ' + source_tag + '</span>'
            if art['summary'] and len(art['summary']) > 5:
                html += '<p style="color:#555; margin:8px 0; font-size:14px;">📌 ' + art['summary'] + '</p>'
            html += '<small style="color:#888;">🕐 ' + art['published'] + ' | 🔗 <a href="' + art['link'] + '" target="_blank">查看原文</a></small>'
            html += '</div><hr>'
        html += "<p style='color:gray;'>⚠️ 本简报仅供参考，不构成投资建议。</p>"
        html += "<p style='color:#888; font-size:12px;'>📧 如需取消订阅，请访问网站操作</p>"
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['Subject'] = "📈 金融新闻简报 " + today
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        success_count = 0
        for subscriber in subscribers:
            try:
                msg['To'] = subscriber
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.sendmail(SENDER_EMAIL, msg.as_string())
                success_count += 1
                logging.info("已发送到: " + subscriber)
            except Exception as e:
                logging.error("发送到 " + subscriber + " 失败: " + str(e))
        logging.info("邮件发送完成！成功 " + str(success_count) + " 个订阅者")
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
