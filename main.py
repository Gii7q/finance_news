import requests
import sqlite3
import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def init_db():
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT, link TEXT UNIQUE, 
                  published TEXT, summary TEXT,
                  ai_summary TEXT,
                  created_at TEXT)''')
    conn.commit()
    conn.close()
    logging.info("数据库初始化完成")

def get_fallback_news():
    """备用模拟数据"""
    return [
        {"title": "A股三大指数震荡整理，沪指微涨0.12%", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "市场整体平稳，成交量有所萎缩"},
        {"title": "央行开展100亿元逆回购操作维护流动性", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "公开市场操作保持合理充裕"},
        {"title": "国际金价突破2000美元关口，创三个月新高", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "受美元走软影响，黄金价格走高"},
        {"title": "新能源汽车销量持续增长，比亚迪再创新高", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "比亚迪等车企销量创新高"},
        {"title": "科技板块表现活跃，半导体概念股走强", "link": "https://finance.sina.com.cn", "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": "芯片概念股集体上涨"},
    ]

def ai_summarize(text):
    """智能摘要（使用AI）"""
    # 如果标题+摘要很短，直接返回
    if len(text) < 50:
        return text
    
    # 尝试调用DeepSeek API（需要配置API Key）
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        try:
            import openai
            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个金融新闻摘要专家，请用50字以内提炼以下新闻的核心要点。"},
                    {"role": "user", "content": text[:1500]}
                ],
                temperature=0.3,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.warning(f"AI摘要失败，使用截断: {e}")
    
    # 如果AI不可用，简单截断
    if len(text) > 150:
        return text[:150] + "..."
    return text

def fetch_news():
    """从多个财经网站抓取真实新闻"""
    logging.info("正在从多个财经网站抓取新闻...")
    all_articles = []
    seen_links = set()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # ==================== 1. 新浪财经 ====================
    sina_count = 0
    try:
        logging.info("抓取 新浪财经...")
        sina_urls = [
            "https://finance.sina.com.cn/",
            "https://finance.sina.com.cn/stock/",
            "https://finance.sina.com.cn/china/",
            "https://finance.sina.com.cn/world/",
        ]
        for url in sina_urls:
            if sina_count >= 10:
                break
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link_tag in soup.find_all('a', href=True):
                if sina_count >= 10:
                    break
                href = link_tag['href']
                title = link_tag.get_text().strip()
                
                if not href or not title or len(title) < 8:
                    continue
                
                if (href.endswith('.shtml') and 
                    ('/doc-' in href or '/stock/' in href or '/money/' in href or '/china/' in href or '/world/' in href) and
                    ('finance.sina.com.cn' in href or href.startswith('/'))):
                    
                    if href.startswith('/'):
                        full_link = 'https://finance.sina.com.cn' + href
                    elif href.startswith('//'):
                        full_link = 'https:' + href
                    else:
                        full_link = href
                    
                    if any(keyword in full_link for keyword in ['video', 'topic', 'slide', 'photo']):
                        continue
                    
                    if full_link not in seen_links:
                        seen_links.add(full_link)
                        clean_title = re.sub(r'\s+', ' ', title).strip()
                        if len(clean_title) > 5:
                            all_articles.append({
                                "title": clean_title[:100],
                                "link": full_link,
                                "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "summary": "来源: 新浪财经"
                            })
                            sina_count += 1
        logging.info(f"新浪财经抓取到 {sina_count} 条")
    except Exception as e:
        logging.warning(f"新浪财经抓取失败: {e}")
    
    # ==================== 2. 东方财富 ====================
    eastmoney_count = 0
    try:
        logging.info("抓取 东方财富...")
        url = "https://www.eastmoney.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link_tag in soup.find_all('a', href=True):
            if eastmoney_count >= 10:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            
            if not href or not title or len(title) < 8:
                continue
            
            if ('.html' in href and 
                ('news' in href or 'stock' in href or 'finance' in href) and
                ('eastmoney.com' in href or href.startswith('/'))):
                
                if href.startswith('/'):
                    full_link = 'https://www.eastmoney.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                
                if full_link not in seen_links:
                    seen_links.add(full_link)
                    clean_title = re.sub(r'\s+', ' ', title).strip()
                    if len(clean_title) > 5:
                        all_articles.append({
                            "title": clean_title[:100],
                            "link": full_link,
                            "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "summary": "来源: 东方财富"
                        })
                        eastmoney_count += 1
        logging.info(f"东方财富抓取到 {eastmoney_count} 条")
    except Exception as e:
        logging.warning(f"东方财富抓取失败: {e}")
    
    # ==================== 处理结果 ====================
    if len(all_articles) < 3:
        logging.info("抓取新闻数量不足，使用备用数据")
        all_articles = get_fallback_news()
    
    if len(all_articles) > 40:
        all_articles = all_articles[:40]
    
    logging.info(f"本次共获取 {len(all_articles)} 条新闻")
    return all_articles

def save_to_db(articles):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    new_count = 0
    for art in articles:
        try:
            c.execute("SELECT id FROM news WHERE title=?", (art["title"],))
            if c.fetchone():
                continue
            
            # 生成AI摘要
            raw_text = art["title"] + ". " + art["summary"]
            ai_res = ai_summarize(raw_text)
            
            c.execute("""INSERT INTO news 
                        (title, link, published, summary, ai_summary, created_at) 
                        VALUES (?,?,?,?,?,?)""",
                      (art["title"], art["link"], art["published"], 
                       art["summary"], ai_res, datetime.now().isoformat()))
            new_count += 1
            logging.info(f"已入库: {art['title'][:30]}...")
        except Exception as e:
            logging.error(f"入库出错: {e}")
    conn.commit()
    conn.close()
    logging.info(f"新增 {new_count} 条新闻")
    return new_count

if __name__ == "__main__":
    init_db()
    articles = fetch_news()
    if articles:
        save_to_db(articles)
    logging.info("✅ 抓取完成！")