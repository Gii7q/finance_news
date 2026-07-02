import requests
import sqlite3
import smtplib
import os
import logging
import re
from datetime import datetime
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

# 1. 获取订阅用户（按时间分组）
def get_subscribers_by_time():
    """从 API 获取订阅者，按 send_time 分组"""
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

# 2. 从文章页面提取摘要
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

# 3. 新浪财经抓取
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

# 4. 东方财富抓取
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

# 5. 腾讯财经抓取
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

# 6. 网易财经抓取
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

# 7. 主抓取函数
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
                if art['link'] not in seen_urls and art['title'] not in seen_titles:
                    seen_urls.add(art['link'])
                    seen_titles.add(art['title'])
                    all_articles.append(art)
        except Exception as e:
            logger.error("来源抓取出错: " + str(e))
    if len(all_articles) < 3:
        logger.info("抓取数量不足，使用备用数据")
        all_articles = [
            {"title": "A股三大指数震荡整理，沪指微涨", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "市场整体平稳，成交量有所萎缩", "source": "新浪财经"},
            {"title": "央行开展逆回购操作维护流动性", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "公开市场操作保持合理充裕", "source": "新浪财经"},
        ]
    logger.info("总共抓取到 " + str(len(all_articles)) + " 条新闻")
    return all_articles

# 8. 推送新闻到 PythonAnywhere
def push_news_to_api(articles):
    try:
        api_url = f"https://ppy.pythonanywhere.com/api/news?secret={API_SECRET}"
        response = requests.post(api_url, json={"news": articles}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ 推送新闻到网站成功，新增 {result.get('new_count', 0)} 条")
            return True
        else:
            logger.error(f"推送新闻失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"推送新闻异常: {e}")
        return False

# 9. 生成邮件内容
def generate_email_content(articles):
    if not articles:
        return "<h3>今日暂无财经新闻</h3>"
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
            html += '<small style="color:#888;">🕐 ' + art['published'] + ' | 🔗 <a href="' + art['link'] + '" style="color:#2980b9;">查看原文</a></small>'
            html += '</div><hr>'
        html += "<p style='color:gray;'>⚠️ 本简报仅供参考，不构成投资建议。</p>"
        html += "<p style='color:#888; font-size:12px;'>📧 如需取消订阅，请访问网站操作</p>"
        return html
    except Exception as e:
        logger.error("生成邮件内容失败: " + str(e))
        return "<h3>生成邮件内容失败</h3>"

# 10. 发送邮件
def send_email(to_email, content):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("发件人邮箱/授权码未配置")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = Header("📈 金融新闻简报 " + datetime.now().strftime("%Y-%m-%d"), 'utf-8')
        msg.attach(MIMEText(content, 'html', 'utf-8'))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        logger.info(f"✅ 发送到 {to_email} 成功")
        return True
    except Exception as e:
        logger.error(f"❌ 发送到 {to_email} 失败：{str(e)}")
        return False

# 11. 主函数（按时间分组发送）
def main():
    logger.info("开始执行...")
    
    # 抓取新闻
    articles = fetch_news()
    if not articles:
        logger.warning("未抓取到新闻")
        return
    
    # 推送到网站
    push_news_to_api(articles)
    
    # 生成邮件内容（所有用户共用）
    email_content = generate_email_content(articles)
    if not email_content:
        logger.error("生成邮件内容失败")
        return
    
    # 按时间分组获取订阅者
    groups = get_subscribers_by_time()
    if not groups:
        logger.warning("无订阅用户，跳过发送")
        return
    
    # 获取当前时间（UTC）
    now = datetime.now().strftime("%H:%M")
    logger.info(f"⏰ 当前时间 (UTC): {now}")
    
    # 发送匹配当前时间段的用户（允许前后10分钟误差）
    total_sent = 0
    total_failed = 0
    now_minutes = int(now.replace(':', ''))
    
    for send_time, emails in groups.items():
        send_minutes = int(send_time.replace(':', ''))
        # 检查当前时间是否匹配该时段（允许前后10分钟误差）
        if abs(now_minutes - send_minutes) <= 10:
            logger.info(f"⏰ 发送给 {send_time} 时段的 {len(emails)} 个订阅者")
            for email in emails:
                if send_email(email, email_content):
                    total_sent += 1
                else:
                    total_failed += 1
    
    logger.info(f"📧 发送完成！成功 {total_sent} 人，失败 {total_failed} 人")
    logger.info("执行完成")

if __name__ == "__main__":
    main()
