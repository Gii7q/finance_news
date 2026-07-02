import requests
import sqlite3
import smtplib
import os
import logging
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 配置项 ====================
API_SECRET = os.getenv("API_SECRET", "FinanceNews20260702ABC123")
API_URL = f"https://ppy.pythonanywhere.com/api/subscribers?secret={API_SECRET}"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
# ===============================================

# ===== 获取开启每日汇总的订阅者 =====
def get_subscribers_by_time_with_summary():
    """获取开启了每日汇总的订阅者"""
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            subscribers = response.json()
            return [sub['email'] for sub in subscribers if sub.get('receive_daily_summary', 0) == 1]
        else:
            return []
    except Exception as e:
        logger.error(f"获取每日汇总订阅者失败: {e}")
        return []

# ===== 获取所有订阅者（按时间分组） =====
def get_subscribers_by_time():
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            subscribers = response.json()
            groups = {}
            for sub in subscribers:
                send_time = sub.get('send_time', '08:00')
                if send_time not in groups:
                    groups[send_time] = []
                groups[send_time].append(sub['email'])
            logger.info(f"✅ 从线上网站获取订阅用户共 {len(subscribers)} 人，分布在 {len(groups)} 个时间段")
            return groups
        else:
            logger.error(f"API返回错误：{response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"调用API失败：{str(e)}")
        return {}

# ===== 生成每日汇总 =====
def generate_daily_summary():
    """生成前一天的新闻汇总（目录 + 详细列表）"""
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        c.execute("SELECT title, link, published, summary FROM news WHERE date(created_at) = date(?) ORDER BY id DESC", (yesterday,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        today_str = (datetime.now() - timedelta(days=1)).strftime("%Y年%m月%d日")
        html = "<h2>📋 " + today_str + " 整日汇总</h2>"
        html += "<p>共 " + str(len(rows)) + " 条新闻</p><hr>"
        
        html += "<h3>📑 目录</h3><ul>"
        for idx, row in enumerate(rows, 1):
            html += '<li><a href="' + row[1] + '" style="color:#2980b9;">' + row[0] + '</a> <small style="color:#888;">(' + row[2] + ')</small></li>'
        html += "</ul><hr>"
        
        html += "<h3>📰 详细新闻</h3>"
        for idx, row in enumerate(rows[:20], 1):
            html += '<div style="margin-bottom:12px; padding:8px; border-left:2px solid #ddd;">'
            html += '<h4 style="margin:0 0 4px 0;">' + str(idx) + '. <a href="' + row[1] + '" style="color:#2980b9;">' + row[0] + '</a></h4>'
            if row[3]:
                html += '<p style="color:#555; font-size:13px; margin:4px 0;">' + row[3][:150] + '...</p>'
            html += '<small style="color:#888;">🕐 ' + row[2] + '</small>'
            html += '</div>'
        
        html += "<p style='color:gray;'>⚠️ 本简报仅供参考，不构成投资建议。</p>"
        return html
    except Exception as e:
        logger.error("生成每日汇总失败: " + str(e))
        return None

# ===== 从文章页面提取摘要 =====
def fetch_article_summary(url, headers):
    try:
        response = requests.get(url, headers=headers, timeout=8)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        article_body = soup.find('div', {'class': 'article'}) or soup.find('div', {'id': 'article'}) or soup.find('div', class_=re.compile(r'content|article|body'))
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
    except Exception:
        return ""

# ===== 新浪财经抓取 =====
def fetch_sina_news(headers):
    articles = []
    try:
        logger.info("抓取 新浪财经...")
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
        logger.info("新浪财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("新浪财经抓取失败: " + str(e))
    return articles

# ===== 东方财富抓取 =====
def fetch_eastmoney_news(headers):
    articles = []
    try:
        logger.info("抓取 东方财富...")
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
        logger.info("东方财富抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("东方财富抓取失败: " + str(e))
    return articles

# ===== 腾讯财经抓取 =====
def fetch_tencent_news(headers):
    articles = []
    try:
        logger.info("抓取 腾讯财经...")
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
        logger.info("腾讯财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("腾讯财经抓取失败: " + str(e))
    return articles

# ===== 网易财经抓取 =====
def fetch_163_news(headers):
    articles = []
    try:
        logger.info("抓取 网易财经...")
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
        logger.info("网易财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("网易财经抓取失败: " + str(e))
    return articles

# ===== 主抓取函数 =====
def fetch_news():
    logger.info("正在从多个财经网站抓取新闻...")
    all_articles = []
    seen_urls = set()
    seen_titles = set()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    sources = [fetch_sina_news, fetch_eastmoney_news, fetch_tencent_news, fetch_163_news]
    for fetch_func in sources:
        try:
            articles = fetch_func(headers)
            for art in articles:
                if art['link'] not in seen_urls and art['
