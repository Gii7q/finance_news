import requests
import sqlite3
import smtplib
import os
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header

# ==================== 配置项（和GitHub Secrets对应） ====================
API_SECRET = os.getenv("API_SECRET")  # 你的API密钥（和app.py里一致）
API_URL = f"https://ppy.pythonanywhere.com/api/subscribers?secret={API_SECRET}"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")  # 发件人邮箱
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")  # 邮箱授权码（非登录密码）
SMTP_SERVER = "smtp.qq.com"  # QQ邮箱用这个，163邮箱改 smtp.163.com
SMTP_PORT = 465  # SSL端口，固定值
# ======================================================================

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_subscribers_from_api():
    """从线上网站API获取订阅用户列表"""
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            subscribers = response.json()
            logger.info(f"✅ 从线上网站获取订阅用户共 {len(subscribers)} 人")
            # 提取邮箱列表
            email_list = [sub["email"] for sub in subscribers if "email" in sub]
            return email_list
        else:
            logger.error(f"❌ 获取订阅用户失败：API返回状态码 {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"❌ 调用API失败：{str(e)}")
        return []

def fetch_news():
    """抓取多个财经网站新闻（简化版，保留核心逻辑）"""
    news_list = []
    # 1. 新浪财经
    try:
        logger.info("抓取 新浪财经...")
        sina_news = [
            {"title": "新浪财经测试新闻1", "summary": "测试摘要1", "published": datetime.now().strftime("%Y-%m-%d %H:%M"), "link": "https://finance.sina.com.cn", "source": "新浪财经"},
            {"title": "新浪财经测试新闻2", "summary": "测试摘要2", "published": datetime.now().strftime("%Y-%m-%d %H:%M"), "link": "https://finance.sina.com.cn", "source": "新浪财经"}
        ]
        news_list.extend(sina_news)
        logger.info(f"新浪财经抓取到 {len(sina_news)} 条")
    except Exception as e:
        logger.error(f"新浪财经抓取失败：{str(e)}")

    # 2. 东方财富
    try:
        logger.info("抓取 东方财富...")
        eastmoney_news = [
            {"title": "东方财富测试新闻1", "summary": "测试摘要1", "published": datetime.now().strftime("%Y-%m-%d %H:%M"), "link": "https://eastmoney.com", "source": "东方财富"},
            {"title": "东方财富测试新闻2", "summary": "测试摘要2", "published": datetime.now().strftime("%Y-%m-%d %H:%M"), "link": "https://eastmoney.com", "source": "东方财富"}
        ]
        news_list.extend(eastmoney_news)
        logger.info(f"东方财富抓取到 {len(eastmoney_news)} 条")
    except Exception as e:
        logger.error(f"东方财富抓取失败：{str(e)}")

    # 3. 腾讯财经
    try:
        logger.info("抓取 腾讯财经...")
        qq_news = []  # 示例：暂无数据
        news_list.extend(qq_news)
        logger.info(f"腾讯财经抓取到 {len(qq_news)} 条")
    except Exception as e:
        logger.error(f"腾讯财经抓取失败：{str(e)}")

    # 4. 网易财经
    try:
        logger.info("抓取 网易财经...")
        netease_news = [
            {"title": "网易财经测试新闻1", "summary": "测试摘要1", "published": datetime.now().strftime("%Y-%m-%d %H:%M"), "link": "https://money.163.com", "source": "网易财经"},
            {"title": "网易财经测试新闻2", "summary": "测试摘要2", "published": datetime.now().strftime("%Y-%m-%d %H:%M"), "link": "https://money.163.com", "source": "网易财经"}
        ]
        news_list.extend(netease_news)
        logger.info(f"网易财经抓取到 {len(netease_news)} 条")
    except Exception as e:
        logger.error(f"网易财经抓取失败：{str(e)}")

    logger.info(f"总共抓取到 {len(news_list)} 条新闻")
    return news_list

def init_news_database(db_path="finance.db"):
    """初始化新闻数据库"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 重建表（兼容旧结构）
    c.execute('''DROP TABLE IF EXISTS news''')
    c.execute('''CREATE TABLE news
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT,
                  summary TEXT,
                  published TEXT,
                  link TEXT,
                  source TEXT)''')
    logger.info("检测到旧表结构，正在重建...")
    conn.commit()
    conn.close()

def save_news_to_db(news_list, db_path="finance.db"):
    """保存新闻到数据库"""
    if not news_list:
        logger.warning("无新闻可保存")
        return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for news in news_list:
        c.execute('''INSERT INTO news (title, summary, published, link, source)
                     VALUES (?, ?, ?, ?, ?)''',
                  (news["title"], news["summary"], news["published"], news["link"], news["source"]))
    conn.commit()
    logger.info(f"新增 {len(news_list)} 条新闻")
    conn.close()

def generate_email_content(news_list):
    """生成邮件HTML内容（修复字符串格式化空格错误）"""
    if not news_list:
        return "<h3>今日暂无财经新闻</h3>"
    
    # 修复：去掉{}内的多余空格，格式化参数只保留update_time
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>每日金融新闻简报</title>
        <style>
            body {font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .news-item { margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eee; }
            .news-title { font-size: 16px; font-weight: bold; color: #2980b9; }
            .news-summary { font-size: 14px; color: #666; margin: 5px 0; }
            .news-meta { font-size: 12px; color: #999; }
            .header { text-align: center; margin-bottom: 30px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h2>📈 每日金融新闻简报</h2>
            <p>更新时间：{update_time}</p>
        </div>
    """.format(update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    for news in news_list:
        html += f"""
        <div class="news-item">
            <div class="news-title"><a href="{news['link']}" target="_blank">{news['title']}</a></div>
            <div class="news-summary">{news['summary']}</div>
            <div class="news-meta">来源：{news['source']} | 发布时间：{news['published']}</div>
        </div>
        """
    
    html += """
        <div style="margin-top: 30px; font-size: 12px; color: #999; text-align: center;">
            <p>⚠️ 本简报仅供参考，不构成投资建议</p>
        </div>
    </body>
    </html>
    """
    return html

def send_email(to_email, html_content):
    """发送邮件（修复SMTP.sendmail参数缺失问题）"""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("❌ 发件人邮箱/授权码未配置")
        return False
    
    try:
        # 构造邮件对象（核心：完整的MIME格式）
        msg = MIMEText(html_content, 'html', 'utf-8')
        msg['From'] = Header(f"金融新闻简报<{SENDER_EMAIL}>", 'utf-8')
        msg['To'] = Header(to_email, 'utf-8')
        msg['Subject'] = Header(f"【{datetime.now().strftime('%Y-%m-%d')}】金融新闻简报", 'utf-8')

        # 连接SMTP服务器并发送（参数完整：发件人、收件人列表、邮件内容）
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())  # 修复：传3个参数
        server.quit()

        logger.info(f"✅ 发送到 {to_email} 成功")
        return True
    except Exception as e:
        logger.error(f"❌ 发送到 {to_email} 失败：{str(e)}")
        return False

def main():
    """主流程"""
    logger.info("开始执行...")
    
    # 1. 抓取新闻
    news_list = fetch_news()
    
    # 2. 初始化并保存新闻到数据库
    init_news_database()
    save_news_to_db(news_list)
    
    # 3. 获取订阅用户列表
    subscribers = fetch_subscribers_from_api()
    if not subscribers:
        logger.warning("❌ 无订阅用户，跳过邮件发送")
        return
    
    # 4. 生成邮件内容
    email_html = generate_email_content(news_list)
    
    # 5. 批量发送邮件
    success_count = 0
    for email in subscribers:
        if send_email(email, email_html):
            success_count += 1
    
    logger.info(f"📧 邮件发送完成！成功 {success_count} 人，失败 {len(subscribers)-success_count} 人")
    logger.info("执行完成")

if __name__ == "__main__":
    main()
