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

# ==================== 统一URL过滤模块 ====================
class NewsURLFilter:
    """财经新闻URL过滤器"""
    
    # 核心财经关键词白名单
    FINANCE_KEYWORDS = [
        'stock', 'market', 'finance', 'economy', 'invest', 'fund', 'bond', 
        'bank', 'insurance', 'estate', 'money', 'tax', 'trade', 'tariff',
        'policy', 'regulation', 'earnings', 'profit', 'revenue', 'debt',
        'equity', 'dividend', 'capital', 'liquidity', 'inflation', 'deflation',
        'fed', 'centralbank', 'treasury', 'yield', 'spread', 'index', 'etf',
        'ipo', 'merger', 'acquisition', 'privateequity', 'venturecapital',
        '中国股市', 'A股', '港股', '美股', '宏观经济', '货币政策', '财政政策', 
        '央行', '利率', '汇率', '黄金', '原油', '大宗商品', '财报', '估值',
        '涨停', '跌停', '创业板', '科创板', '北交所', '主板', '退市', '分红', '回购',
        '增持', '减持', '北向资金', '主力资金', '成交量', '大盘',
        '期货', '现货', '铁矿石', '铜', '铝', '锌',
        '房地产', '房贷', 'LPR', 'MLF', '逆回购', '公开市场',
        'CPI', 'PMI', 'GDP', '美联储', '加息', '降息', '缩表', '扩表'
    ]
    
    # 明确的无关内容关键词黑名单
    IRRELEVANT_KEYWORDS = [
        'photo', 'video', 'topic', 'special', 'download', 'desktopapp', 
        'advertisement', 'promotion', 'comment', 'tie', 'user', 'login', 
        'register', 'help', 'about', 'contact', 'recruit', 'event',
        'gallery', 'slide', 'bbs', 'forum', 'blog', 'share', 'subscribe',
        'sky', 'weather', 'sport', 'entertainment', 'celebrity', 'fashion',
        '婚庆', '旅游', '美食', '汽车测评', '手机测评', '娱乐', '体育',
        '皇帝', '太监', '扶弟', '皇上', '后宫', '娘娘', '妃子', 
        '古装', '宫廷', '驸马', '皇子', '公主', '宦官', '将军',
        '明星', '八卦', '综艺', '演员', '歌手', '导演',
        '枪战', '警匪', '黑帮', '黑社会', '婚外情', '小三', '离婚', '出轨'
    ]
    
    @classmethod
    def is_finance_news(cls, url, title='', summary=''):
        """
        判断一个URL是否为有效的财经新闻
        返回 (is_valid, reason)
        """
        url_lower = url.lower()
        title_lower = title.lower()
        text = url_lower + " " + title_lower + " " + summary.lower()
        
        # 1. 黑名单快速排除（任何匹配即拒绝）
        for keyword in cls.IRRELEVANT_KEYWORDS:
            if keyword in url_lower or keyword in title_lower:
                return False, f"命中黑名单关键词: {keyword}"
        
        # 2. 针对特定来源的频道白名单
        if 'caixin.com' in url_lower:
            allowed_caixin = ['/finance/', '/economics/', '/companies/', '/markets/', '/bank/', '/industry/', '/macro/']
            if not any(channel in url_lower for channel in allowed_caixin):
                return False, f"非财新财经频道: {url}"
            if 'photo' in url_lower or 'video' in url_lower:
                return False, "财新图片/视频频道"
        
        if 'sina.com.cn' in url_lower:
            if '/desktopapp/' in url_lower:
                return False, "新浪APP下载页"
            if '/photo/' in url_lower or '/video/' in url_lower:
                return False, "新浪图片/视频频道"
        
        if '163.com' in url_lower:
            if not any(channel in url_lower for channel in ['/money/', '/stock/', '/fund/', '/bank/', '/insurance/']):
                return False, f"非网易财经频道: {url}"
            if '/dy/' in url_lower or 'dy.163.com' in url_lower:
                return False, "网易自媒体"
            if 'comment.tie.163.com' in url_lower or '/tie/' in url_lower:
                return False, "网易评论页"
        
        if 'eastmoney.com' in url_lower:
            if '/photo/' in url_lower or '/video/' in url_lower:
                return False, "东方财富图片/视频"
        
        if 'hexun.com' in url_lower:
            if '/photo/' in url_lower or '/video/' in url_lower:
                return False, "和讯图片/视频"
            if '/special/' in url_lower or '/topic/' in url_lower:
                return False, "和讯专题页"
        
        # 3. 通用财经关键词检查
        has_finance_keyword = any(keyword.lower() in text for keyword in cls.FINANCE_KEYWORDS)
        if not has_finance_keyword:
            return False, "未命中任何财经关键词"
        
        # 4. URL格式检查
        if not any(ext in url_lower for ext in ['.html', '.shtml', '.php?id=', '/news/', '/article/']):
            return False, "非标准文章URL格式"
        
        return True, "通过验证"
    
    @classmethod
    def filter_articles(cls, articles):
        """批量过滤文章列表"""
        valid_articles = []
        for article in articles:
            url = article.get('link', '')
            title = article.get('title', '')
            summary = article.get('summary', '')
            is_valid, reason = cls.is_finance_news(url, title, summary)
            if is_valid:
                valid_articles.append(article)
            else:
                logger.debug(f"过滤: {title[:30]}... 原因: {reason}")
        return valid_articles

# ==================== 工具函数 ====================
def get_beijing_time():
    return datetime.utcnow() + timedelta(hours=8)

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
            logger.info(f"✅ 从线上网站获取订阅用户共 {len(subscribers)} 人")
            return groups
        else:
            return {}
    except Exception as e:
        logger.error(f"调用API失败: {str(e)}")
        return {}

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
        
# ==================== 清理旧新闻 ====================
def clean_old_news():
    """删除 7 天前的新闻"""
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        c.execute("DELETE FROM news WHERE date(created_at) < date(?)", (cutoff,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        logger.info(f"🧹 清理了 {deleted} 条旧新闻")
    except Exception as e:
        logger.error(f"清理旧新闻失败: {e}")

# ==================== 各来源抓取函数 ====================

# 新浪财经
def fetch_sina_news(headers):
    articles = []
    try:
        logger.info("抓取 新浪财经...")
        urls = [
            "https://finance.sina.com.cn/",
            "https://finance.sina.com.cn/stock/",
            "https://finance.sina.com.cn/china/",
            "https://finance.sina.com.cn/world/",
        ]
        for url in urls:
            if len(articles) >= 15:
                break
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            for link_tag in soup.find_all('a', href=True):
                if len(articles) >= 15:
                    break
                href = link_tag['href']
                title = link_tag.get_text().strip()
                if not href or not title or len(title) < 8:
                    continue
                # 过滤下载页、图片、视频
                if '/desktopapp/' in href or 'download' in href or '/photo/' in href or '/video/' in href:
                    continue
                if href and ('.shtml' in href or '.html' in href):
                    if href.startswith('/'):
                        full_link = 'https://finance.sina.com.cn' + href
                    elif href.startswith('//'):
                        full_link = 'https:' + href
                    else:
                        full_link = href
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
        logger.info("新浪财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("新浪财经抓取失败: " + str(e))
    return articles

# 东方财富
def fetch_eastmoney_news(headers):
    articles = []
    try:
        logger.info("抓取 东方财富...")
        urls = [
            "https://www.eastmoney.com/",
            "https://finance.eastmoney.com/",
        ]
        for url in urls:
            if len(articles) >= 15:
                break
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            for link_tag in soup.find_all('a', href=True):
                if len(articles) >= 15:
                    break
                href = link_tag['href']
                title = link_tag.get_text().strip()
                if not href or not title or len(title) < 8:
                    continue
                if '/photo/' in href or '/video/' in href:
                    continue
                if href and '.html' in href:
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
        logger.info("东方财富抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("东方财富抓取失败: " + str(e))
    return articles

# 腾讯财经
def fetch_tencent_news(headers):
    articles = []
    try:
        logger.info("抓取 腾讯财经...")
        url = "https://finance.qq.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 15:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if not href or not title or len(title) < 8:
                continue
            if 'video' in href or 'photo' in href:
                continue
            if href and '.html' in href:
                if href.startswith('/'):
                    full_link = 'https://finance.qq.com' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
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
        logger.info("腾讯财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("腾讯财经抓取失败: " + str(e))
    return articles

# 网易财经
def fetch_163_news(headers):
    articles = []
    try:
        logger.info("抓取 网易财经...")
        url = "https://money.163.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 15:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if not href or not title or len(title) < 8:
                continue
            # 过滤网易号、评论页
            if '/dy/' in href or 'dy.163.com' in href or 'comment.tie.163.com' in href or '/tie/' in href:
                continue
            if href and ('.html' in href or '.shtml' in href):
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
        logger.info("网易财经抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("网易财经抓取失败: " + str(e))
    return articles

# 和讯网
def fetch_hexun_news(headers):
    articles = []
    try:
        logger.info("抓取 和讯网...")
        url = "https://www.hexun.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 10:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if not href or not title or len(title) < 8:
                continue
            if '/photo/' in href or '/video/' in href or '/special/' in href or '/topic/' in href:
                continue
            if href and 'hexun.com' in href:
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

# 财新网
def fetch_caixin_news(headers):
    articles = []
    try:
        logger.info("抓取 财新网...")
        channels = ['/finance/', '/economics/', '/companies/', '/markets/', '/bank/', '/industry/']
        for channel in channels:
            if len(articles) >= 10:
                break
            url = f"https://www.caixin.com{channel}"
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            for link_tag in soup.find_all('a', href=True):
                if len(articles) >= 10:
                    break
                href = link_tag['href']
                title = link_tag.get_text().strip()
                if not href or not title or len(title) < 8:
                    continue
                # 只保留财新财经频道链接
                if 'caixin.com' in href:
                    if any(ch in href for ch in ['/finance/', '/economics/', '/companies/', '/markets/', '/bank/', '/industry/']):
                        if 'photo' not in href and 'video' not in href:
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

# 金融界
def fetch_jrj_news(headers):
    articles = []
    try:
        logger.info("抓取 金融界...")
        urls = ["https://www.jrj.com.cn/", "https://stock.jrj.com.cn/"]
        for url in urls:
            if len(articles) >= 10:
                break
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            for link_tag in soup.find_all('a', href=True):
                if len(articles) >= 10:
                    break
                href = link_tag['href']
                title = link_tag.get_text().strip()
                if not href or not title or len(title) < 8:
                    continue
                if 'jrj.com.cn' in href:
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

# 华尔街见闻
def fetch_wallstreet_news(headers):
    articles = []
    try:
        logger.info("抓取 华尔街见闻...")
        url = "https://wallstreetcn.com/"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 10:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if not href or not title or len(title) < 8:
                continue
            if 'wallstreetcn.com' in href:
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

# 财联社
def fetch_cls_news(headers):
    articles = []
    try:
        logger.info("抓取 财联社...")
        url = "https://www.cls.cn/telegraph"
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for link_tag in soup.find_all('a', href=True):
            if len(articles) >= 10:
                break
            href = link_tag['href']
            title = link_tag.get_text().strip()
            if not href or not title or len(title) < 8:
                continue
            if 'cls.cn' in href:
                if href.startswith('/'):
                    full_link = 'https://www.cls.cn' + href
                elif href.startswith('//'):
                    full_link = 'https:' + href
                else:
                    full_link = href
                if 'video' not in full_link and 'photo' not in full_link:
                    summary = fetch_article_summary(full_link, headers)
                    if not summary:
                        summary = "来源: 财联社"
                    articles.append({
                        "title": title[:100],
                        "link": full_link,
                        "published": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "summary": summary,
                        "source": "财联社"
                    })
        logger.info("财联社抓取到 " + str(len(articles)) + " 条")
    except Exception as e:
        logger.error("财联社抓取失败: " + str(e))
    return articles

# Yahoo Finance
def fetch_yahoo_news(headers):
    articles = []
    try:
        import yfinance as yf
        logger.info("抓取 Yahoo Finance 新闻...")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "VTI", "SPY"]
        for symbol in symbols[:10]:
            try:
                ticker = yf.Ticker(symbol)
                news = ticker.news
                if news:
                    for item in news[:3]:
                        title = item.get("title", "")
                        if not title or len(title) < 5:
                            continue
                        link = item.get("link", "")
                        pub_time = item.get("providerPublishTime", datetime.now().timestamp())
                        if isinstance(pub_time, (int, float)):
                            pub_time = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            pub_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        summary = item.get("summary", item.get("description", ""))
                        if not summary or len(summary) < 10:
                            summary = f"来源: Yahoo Finance ({symbol})"
                        articles.append({
                            "title": title[:100],
                            "link": link,
                            "published": pub_time,
                            "summary": summary[:200],
                            "source": f"Yahoo Finance ({symbol})"
                        })
                        if len(articles) >= 30:
                            break
                if len(articles) >= 30:
                    break
            except Exception as e:
                logger.warning(f"获取 {symbol} 新闻失败: {e}")
                continue
        logger.info(f"Yahoo Finance 抓取到 {len(articles)} 条")
    except ImportError:
        logger.warning("yfinance 未安装，跳过 Yahoo Finance")
    except Exception as e:
        logger.error(f"Yahoo Finance 抓取失败: {e}")
    return articles

# ==================== 主抓取函数 ====================
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
        fetch_wallstreet_news,
        fetch_cls_news,
        fetch_yahoo_news,
    ]
    for fetch_func in sources:
        try:
            articles = fetch_func(headers)
            # ===== 统一过滤 =====
            filtered = NewsURLFilter.filter_articles(articles)
            for art in filtered:
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

# ==================== 推送和邮件功能 ====================
def push_news_to_api(articles):
    try:
        api_url = f"https://ppy.pythonanywhere.com/api/news?secret={API_SECRET}"
        response = requests.post(api_url, json={"news": articles}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ 推送新闻到网站成功，新增 {result.get('new_count', 0)} 条")
            return True
        else:
            logger.error(f"推送新闻失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"推送新闻异常: {e}")
        return False

def generate_email_content_from_db():
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
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
        html += "<p style='color:gray;'>⚠️ 本简报仅供参考，不构成投资建议。</p>"
        html += '<p style="color:#888; font-size:12px;">📧 如需取消订阅，请访问 <a href="https://ppy.pythonanywhere.com" style="color:#2980b9; text-decoration:none;">ppy.pythonanywhere.com</a></p>'
        return html
    except Exception as e:
        logger.error("从数据库生成邮件内容失败: " + str(e))
        return "<h3>生成邮件内容失败</h3>"

def generate_daily_summary():
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
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
        # AI 概述（需要 DEEPSEEK_API_KEY）
        try:
            import openai
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if api_key:
                titles = [row[0] for row in rows[:30]]
                titles_text = "\n".join(titles)
                client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "请用150字以内概括以下新闻的整体趋势。"}, {"role": "user", "content": titles_text}],
                    temperature=0.5,
                    max_tokens=200
                )
                ai_summary = response.choices[0].message.content.strip()
                if ai_summary:
                    html += '<div style="background:#f0f7ff; padding:15px; border-radius:8px; border-left:4px solid #2980b9;">'
                    html += "<p style='line-height:1.8;'>🤖 <strong>AI 概述：</strong>" + ai_summary + "</p>"
                    html += "</div><hr>"
        except Exception as e:
            logger.warning(f"AI 概述生成失败: {e}")
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
        html += '<p style="color:#888; font-size:12px;">📧 如需取消订阅，请访问 <a href="https://ppy.pythonanywhere.com" style="color:#2980b9; text-decoration:none;">ppy.pythonanywhere.com</a></p>'
        return html
    except Exception as e:
        logger.error("生成每日汇总失败: " + str(e))
        return None

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

# ==================== 主函数 ====================
def main():
    logger.info("开始执行...")
    beijing_now = get_beijing_time()
    now_str = beijing_now.strftime("%H:%M")
    now_minutes = int(now_str.replace(':', ''))
    clean_old_news()  # 👈 先清理旧新闻
    # ... 后续抓取逻辑
    articles = fetch_news()
    if articles:
        push_news_to_api(articles)
        logger.info(f"✅ 抓取到 {len(articles)} 条新新闻并推送")
    else:
        logger.warning("⚠️ 本次未抓取到新新闻，将使用已有数据")
    
    email_content = generate_email_content_from_db()
    if not email_content or "暂无" in email_content:
        logger.warning("⚠️ 今日无新闻，跳过发送")
        return
    
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
    
    groups = get_subscribers_by_time()
    if not groups:
        logger.warning("无订阅用户，跳过发送")
        return
    
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
