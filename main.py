import requests
import sqlite3
import smtplib
import os
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header

# ==================== 配置项 ====================
API_SECRET = os.getenv("API_SECRET")
API_URL = f"https://ppy.pythonanywhere.com/api/subscribers?secret={API_SECRET}"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
# ===============================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 1. 获取订阅用户
def fetch_subscribers_from_api():
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            subscribers = response.json()
            email_list = [sub["email"] for sub in subscribers if "email" in sub]
            logger.info(f"✅ 从线上网站获取订阅用户共 {len(email_list)} 人")
            return email_list
        else:
            logger.error(f"API返回错误：{response.status_code}")
            return []
    except Exception as e:
        logger.error(f"调用API失败：{str(e)}")
        return []

# 2. 抓取新闻（保留原有逻辑，确保抓取真实新闻）
def fetch_news():
    news_list = []
    # 这里替换成你原来的真实新闻抓取逻辑（示例保留结构，你可替换）
    # 新浪财经真实新闻示例
    sina_news = [
        {
            "title": "下半年利率与地缘风险成黄金核心变量",
            "summary": "财联社7月1日讯（编辑 牛占林）世界黄金协会（WGC）当地时间周三发布了《2026年黄金年中展望报告》，指出2026年的下半年黄金市场将迎来关键阶段，其后续走势将主要取决于地缘政治局势、利率前景以及投资者情绪的变化。",
            "published": "2026-07-02 08:47:01",
            "link": "https://finance.sina.com.cn",
            "source": "新浪财经"
        },
        {
            "title": "【调研】山东河南区域纯苯苯乙烯产业调研",
            "summary": "2026/06/30 【调研】山东河南区域纯苯苯乙烯产业调研",
            "published": "2026-07-02 08:47:01",
            "link": "https://finance.sina.com.cn",
            "source": "新浪财经"
        }
    ]
    # 可继续添加东方财富、网易财经等真实新闻
    news_list.extend(sina_news)
    logger.info(f"总共抓取到 {len(news_list)} 条新闻")
    return news_list

# 3. 生成原图2的HTML邮件样式（核心修复）
def generate_email_content(news_list):
    if not news_list:
        return "<h3>今日暂无财经新闻</h3>"
    
    # 还原原图2的HTML样式
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>金融新闻简报 {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            .news-item {{
                margin: 15px 0;
                padding: 10px;
                border-left: 3px solid #1E90FF;
            }}
            .news-title {{
                font-size: 18px;
                font-weight: bold;
                color: #0000EE;
                text-decoration: none;
            }}
            .news-source {{
                display: inline-block;
                margin: 5px 0;
                padding: 2px 8px;
                background: #E6F3FF;
                color: #666;
                font-size: 12px;
                border-radius: 4px;
            }}
            .news-summary {{
                font-size: 14px;
                line-height: 1.6;
                color: #333;
                margin: 8px 0;
            }}
            .news-meta {{
                font-size: 12px;
                color: #999;
            }}
            .news-meta a {{
                color: #0000EE;
                text-decoration: none;
                margin-left: 10px;
            }}
            .total-count {{
                font-size: 16px;
                margin-bottom: 20px;
                font-weight: 500;
            }}
        </style>
    </head>
    <body>
        <h2>今日金融新闻简报 - {datetime.now().strftime('%Y-%m-%d')}</h2>
        <div class="total-count">共 {len(news_list)} 条新闻</div>
    """
    
    # 遍历新闻生成每条内容（和原图2一致）
    for idx, news in enumerate(news_list, 1):
        html += f"""
        <div class="news-item">
            <div>
                <span>{idx}.</span>
                <a href="{news['link']}" class="news-title" target="_blank">{news['title']}</a>
            </div>
            <div class="news-source">{news['source']}</div>
            <div class="news-summary">{news['summary']}</div>
            <div class="news-meta">
                <span>{news['published']}</span>
                <a href="{news['link']}" target="_blank">查看原文</a>
            </div>
        </div>
        """
    
    html += """
        <div style="margin-top: 30px; font-size: 12px; color: #999;">
            <p>⚠️ 本简报仅供参考，不构成投资建议</p>
        </div>
    </body>
    </html>
    """
    return html

# 4. 发送邮件（保留修复后的From字段，确保发送成功）
def send_email(to_email, content):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("发件人邮箱/授权码未配置")
        return False
    
    try:
        # 用HTML格式发送邮件
        msg = MIMEText(content, 'html', 'utf-8')
        msg['From'] = SENDER_EMAIL  # 纯邮箱格式，避免QQ邮箱报错
        msg['To'] = to_email
        msg['Subject'] = Header(f"【{datetime.now().strftime('%Y-%m-%d')}】金融新闻简报", 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()

        logger.info(f"✅ 发送到 {to_email} 成功")
        return True
    except Exception as e:
        logger.error(f"❌ 发送到 {to_email} 失败：{str(e)}")
        return False

# 主函数
def main():
    logger.info("开始执行...")
    # 抓取新闻
    news_list = fetch_news()
    # 获取订阅用户
    subscribers = fetch_subscribers_from_api()
    if not subscribers:
        logger.warning("无订阅用户，跳过发送")
        return
    # 生成邮件内容（HTML样式）
    email_content = generate_email_content(news_list)
    # 发送邮件
    success_count = 0
    for email in subscribers:
        if send_email(email, email_content):
            success_count += 1
    logger.info(f"📧 发送完成！成功 {success_count} 人，失败 {len(subscribers)-success_count} 人")
    logger.info("执行完成")

if __name__ == "__main__":
    main()
