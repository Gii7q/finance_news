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

# 2. 抓取新闻（极简版）
def fetch_news():
    news_list = []
    # 新浪财经
    sina_news = [{"title": "新浪财经测试1", "summary": "测试摘要1", "published": datetime.now().strftime("%Y-%m-%d"), "link": "https://finance.sina.com.cn", "source": "新浪财经"},
                 {"title": "新浪财经测试2", "summary": "测试摘要2", "published": datetime.now().strftime("%Y-%m-%d"), "link": "https://finance.sina.com.cn", "source": "新浪财经"}]
    # 东方财富
    east_news = [{"title": "东方财富测试1", "summary": "测试摘要1", "published": datetime.now().strftime("%Y-%m-%d"), "link": "https://eastmoney.com", "source": "东方财富"},
                 {"title": "东方财富测试2", "summary": "测试摘要2", "published": datetime.now().strftime("%Y-%m-%d"), "link": "https://eastmoney.com", "source": "东方财富"}]
    # 网易财经
    netease_news = [{"title": "网易财经测试1", "summary": "测试摘要1", "published": datetime.now().strftime("%Y-%m-%d"), "link": "https://money.163.com", "source": "网易财经"},
                    {"title": "网易财经测试2", "summary": "测试摘要2", "published": datetime.now().strftime("%Y-%m-%d"), "link": "https://money.163.com", "source": "网易财经"}]
    news_list = sina_news + east_news + netease_news
    logger.info(f"总共抓取到 {len(news_list)} 条新闻")
    return news_list

# 3. 生成纯文本邮件内容（彻底去掉HTML格式化）
def generate_email_content(news_list):
    if not news_list:
        return "今日暂无财经新闻"
    
    # 纯文本格式，无任何{}格式化冲突
    content = f"📈 每日金融新闻简报 {datetime.now().strftime('%Y-%m-%d')}\n\n"
    for idx, news in enumerate(news_list, 1):
        content += f"{idx}. {news['title']}\n"
        content += f"   摘要：{news['summary']}\n"
        content += f"   来源：{news['source']} | 发布时间：{news['published']}\n"
        content += f"   链接：{news['link']}\n\n"
    content += "⚠️ 本简报仅供参考，不构成投资建议"
    return content

# 4. 发送邮件（修复SMTP参数）
def send_email(to_email, content):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error("发件人信息未配置")
        return False
    
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = Header(f"金融新闻简报<{SENDER_EMAIL}>", 'utf-8')
        msg['To'] = Header(to_email, 'utf-8')
        msg['Subject'] = Header(f"【{datetime.now().strftime('%Y-%m-%d')}】金融新闻简报", 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())  # 3个参数完整
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
    # 生成邮件内容
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
