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

# ===== 获取北京时间 =====
def get_beijing_time():
    """获取当前北京时间"""
    return datetime.utcnow() + timedelta(hours=8)

# ===== AI 概述生成（仅在每日汇总时调用） =====
def generate_ai_summary(rows):
    """调用 AI 生成新闻概述（仅用于每日汇总）"""
    try:
        import openai
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            logger.warning("DEEPSEEK_API_KEY 未配置，跳过 AI 概述")
            return None
        
        titles = [row[0] for row in rows[:30]]
        titles_text = "\n".join(titles)
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个金融新闻编辑，请用200字以内概括以下新闻的整体趋势和重点。"},
                {"role": "user", "content": "请概括以下新闻：\n" + titles_text}
            ],
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"AI 概述生成失败: {e}")
        return None

# ===== 获取开启每日汇总的订阅者 =====
def get_subscribers_by_time_with_summary():
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

# ===== 生成每日汇总（含 AI 概述） =====
def generate_daily_summary():
    """生成前一天的新闻汇总（目录 + AI 概述 + 详细列表）"""
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
        # 使用北京时间计算昨天
        beijing_now = get_beijing_time()
        yesterday = (beijing_now - timedelta(days=1)).strftime('%Y-%m-%d')
        c.execute("SELECT title, link, published, summary FROM news WHERE substr(created_at, 1, 10) = ? ORDER BY id DESC", (yesterday,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        today_str = (beijing_now - timedelta(days=1)).strftime("%Y年%m月%d日")
        html = "<h2>📋 " + today_str + " 整日汇总</h2>"
        html += "<p>共 " + str(len(rows)) + " 条新闻</p><hr>"
        html += '<p style="color:#888; font-size:12px;">📧 如需取消订阅，请访问 <a href="https://ppy.pythonanywhere.com" style="color:#2980b9; text-decoration:none;">ppy.pythonanywhere.com</a></p>'
        
        # ===== AI 概述（仅在每日汇总时调用） =====
        ai_summary = generate_ai_summary(rows)
        if ai_summary:
            html += "<h3>🤖 AI 概述</h3>"
            html += '<div style="background:#f0f7ff; padding:15px; border-radius:8px; border-left:4px solid #2980b9;">'
            html += "<p style='line-height:1.8;'>" + ai_summary + "</p>"
            html += "</div><hr>"
        
        # ===== 目录 =====
        html += "<h3>📑 目录</h3><ul>"
        for idx, row in enumerate(rows, 1):
            html += '<li><a href="' + row[1] + '" style="color:#2980b9;">' + row[0] + '</a> <small style="color:#888;">(' + row[2] + ')</small></li>'
        html += "</ul><hr>"
        
        # ===== 详细新闻 =====
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
                if len(articles) >= 10:
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
                    if len(articles) >= 10:
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
                    if len(articles) >= 10:
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
                    if len(articles) >= 10:
                        break
        logger.info("网易财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("网易财经抓取失败: " + str(e))
    return articles

# ===== 和讯网 =====
def fetch_hexun_news(headers):
    articles = []
    try:
        logger.info("抓取 和讯网...")
        url = "https://www.hexun.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 8:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and 'hexun.com' in str(href):
                if href.startswith('/'):
                    full_link = 'https://www.hexun.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                summary = fetch_article_summary(full_link, headers)
                if not summary:
                    summary = "来源: 和讯网"
                articles.append({
                    "title": title[:100],
                    "link": full_link,
                    "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": summary,
                    "source": "和讯网"
                })
        logger.info("和讯网抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("和讯网抓取失败: " + str(e))
    return articles

# ===== 财新网 =====
def fetch_caixin_news(headers):
    articles = []
    try:
        logger.info("抓取 财新网...")
        url = "https://www.caixin.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 8:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and 'caixin.com' in str(href):
                if href.startswith('/'):
                    full_link = 'https://www.caixin.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                summary = fetch_article_summary(full_link, headers)
                if not summary:
                    summary = "来源: 财新网"
                articles.append({
                    "title": title[:100],
                    "link": full_link,
                    "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": summary,
                    "source": "财新网"
                })
        logger.info("财新网抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("财新网抓取失败: " + str(e))
    return articles

# ===== 金融界 =====
def fetch_jrj_news(headers):
    articles = []
    try:
        logger.info("抓取 金融界...")
        urls = [
            "https://www.jrj.com.cn/",
            "https://stock.jrj.com.cn/"
        ]
        for url in urls:
            if len(articles) >= 8:
                break
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            for link_tag in soup.find_all('a', href=True):
                if len(articles) >= 8:
                    break
                href = link_tag['href']
                title = link_tag.get_text().strip()
                if title and len(title) > 10 and href and 'jrj.com.cn' in str(href):
                    if href.startswith('/'):
                        full_link = 'https://www.jrj.com.cn' + href
                    elif href.startswith('//'):
                        full_link = 'https:' + href
                    else:
                        full_link = href
                    summary = fetch_article_summary(full_link, headers)
                    if not summary:
                        summary = "来源: 金融界"
                    articles.append({
                        "title": title[:100],
                        "link": full_link,
                        "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "summary": summary,
                        "source": "金融界"
                    })
        logger.info("金融界抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("金融界抓取失败: " + str(e))
    return articles

# ===== 华尔街见闻 =====
def fetch_wallstreet_news(headers):
    articles = []
    try:
        logger.info("抓取 华尔街见闻...")
        url = "https://wallstreetcn.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 8:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if title and len(title) > 10 and href and 'wallstreetcn.com' in str(href):
                if href.startswith('/'):
                    full_link = 'https://wallstreetcn.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                summary = fetch_article_summary(full_link, headers)
                if not summary:
                    summary = "来源: 华尔街见闻"
                articles.append({
                    "title": title[:100],
                    "link": full_link,
                    "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": summary,
                    "source": "华尔街见闻"
                })
        logger.info("华尔街见闻抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("华尔街见闻抓取失败: " + str(e))
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
    sources = [
        fetch_sina_news,
        fetch_eastmoney_news,
        fetch_tencent_news,
        fetch_163_news,
        fetch_hexun_news,
        fetch_caixin_news,
        fetch_jrj_news,
        fetch_wallstreet_news
    ]
    # ... 后续代码不变
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

# ===== 推送新闻到 PythonAnywhere =====
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

# ===== 从数据库生成当天新闻 =====
def generate_email_content_from_db():
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
        # 使用北京时间
        beijing_now = get_beijing_time()
        today = beijing_now.strftime('%Y-%m-%d')
        c.execute("SELECT title, summary, published, link, source FROM news WHERE substr(created_at, 1, 10) = ? ORDER BY id DESC", (today,))
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return "<h3>今日暂无财经新闻</h3>"
        
        articles = [{"title": r[0], "summary": r[1], "published": r[2], "link": r[3], "source": r[4]} for r in rows]
        
        today_str = beijing_now.strftime("%Y-%m-%d")
        html = "<h2>📈 今日金融新闻简报 - " + today_str + "</h2>"
        html += "<p>共 " + str(len(articles)) + " 条新闻</p><hr>"
        
        for idx, art in enumerate(articles[:30], 1):
            source_tag = art.get("source", "未知来源")
            html += '<div style="margin-bottom:15px; padding:10px; border-left: 3px solid #2980b9;">'
            html += '<h3 style="margin:0 0 5px 0;">' + str(idx) + '. <a href="' + art['link'] + '" style="color:#2980b9;">' + art['title'] + '</a></h3>'
            html += '<span style="font-size:12px; color:#2980b9; background:#e8f0fe; padding:2px 10px; border-radius:12px;">📰 ' + source_tag + '</span>'
            if art['summary'] and len(art['summary']) > 5:
                html += '<p style="color:#555; margin:8px 0; font-size:14px;">📌 ' + art['summary'] + '</p>'
            html += '<small style="color:#888;">🕐 ' + art['published'] + ' | 🔗 <a href="' + art['link'] + '" style="color:#2980b9;">查看原文</a></small>'
            html += '</div><hr>'
        
        html += '<hr style="border: 1px solid #eee; margin-top:20px;">'
        html += '<p style="color:gray; font-size:12px;">⚠️ 本简报仅供参考，不构成投资建议。</p>'
        html += '<p style="color:#888; font-size:12px;">📧 如需取消订阅，请访问 <a href="https://ppy.pythonanywhere.com" style="color:#2980b9; text-decoration:none;">ppy.pythonanywhere.com</a></p>'
        return html
    except Exception as e:
        logger.error("从数据库生成邮件内容失败: " + str(e))
        return "<h3>生成邮件内容失败</h3>"

# ===== 发送邮件 =====
def send_email(to_email, content, is_summary=False):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("发件人邮箱/授权码未配置")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        if is_summary:
            beijing_now = get_beijing_time()
            subject = "📋 每日新闻汇总 " + (beijing_now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            subject = "📈 金融新闻简报 " + get_beijing_time().strftime("%Y-%m-%d")
        msg['Subject'] = Header(subject, 'utf-8')
        msg.attach(MIMEText(content, 'html', 'utf-8'))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        logger.info(f"✅ 发送到 {to_email} 成功")
        return True
    except Exception as e:
        logger.error(f"❌ 发送到 {to_email} 失败：{str(e)}")
        return False

# ===== 主函数 =====
def main():
    logger.info("开始执行...")
    
    beijing_now = get_beijing_time()
    now_str = beijing_now.strftime("%H:%M")
    now_minutes = int(now_str.replace(':', ''))
    
    # ===== 先抓取新闻 =====
    articles = fetch_news()
    if articles:
        push_news_to_api(articles)
        logger.info(f"✅ 抓取到 {len(articles)} 条新新闻并推送")
    else:
        logger.warning("⚠️ 本次未抓取到新新闻，将使用已有数据")
    
    # ===== 从数据库获取当天所有新闻 =====
    email_content = generate_email_content_from_db()
    if not email_content or "暂无" in email_content:
        logger.warning("⚠️ 今日无新闻，跳过发送")
        return
    
    # ===== 检查是否应该发送每日汇总 =====
    if abs(now_minutes - 0) <= 10:
        logger.info("📋 发送每日汇总时间已到...")
        subscribers = get_subscribers_by_time_with_summary()
        if subscribers:
            summary_content = generate_daily_summary()
            if summary_content:
                for email in subscribers:
                    send_email(email, summary_content, is_summary=True)
                logger.info(f"📋 每日汇总发送完成！共 {len(subscribers)} 人")
                return
            else:
                logger.warning("昨日无新闻，跳过汇总发送")
        else:
            logger.warning("无开启每日汇总的订阅者")
    
    # ===== 按时间分组获取订阅者 =====
    groups = get_subscribers_by_time()
    if not groups:
        logger.warning("无订阅用户，跳过发送")
        return
    
    # ===== 按时间匹配发送 =====
    total_sent = 0
    total_failed = 0
    
    for send_time, emails in groups.items():
        send_minutes = int(send_time.replace(':', ''))
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
