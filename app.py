from flask import Flask, request, render_template_string, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

# HTML模板（带搜索功能）
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📈 金融新闻简报</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: #f0f2f5;
            padding: 20px;
            max-width: 1000px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 25px;
            text-align: center;
        }
        .header h1 { font-size: 28px; }
        .header p { opacity: 0.8; margin-top: 8px; font-size: 14px; }
        .header .badge {
            display: inline-block;
            background: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 2px 14px;
            border-radius: 20px;
            margin-top: 8px;
        }
        .toolbar {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            align-items: center;
        }
        .toolbar input {
            flex: 1;
            min-width: 200px;
            padding: 10px 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 15px;
        }
        .toolbar input:focus {
            outline: none;
            border-color: #2980b9;
        }
        .btn {
            padding: 10px 24px;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }
        .btn-primary {
            background: #2980b9;
            color: white;
        }
        .btn-primary:hover { background: #1a6b99; }
        .btn-success {
            background: #27ae60;
            color: white;
        }
        .btn-success:hover { background: #1e8449; }
        .stats {
            color: #666;
            font-size: 14px;
            margin-bottom: 15px;
        }
        .news-item {
            background: white;
            border-radius: 10px;
            padding: 18px 22px;
            margin-bottom: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid #2980b9;
            transition: transform 0.15s;
        }
        .news-item:hover { transform: translateX(4px); }
        .news-item .source {
            display: inline-block;
            font-size: 11px;
            padding: 2px 10px;
            border-radius: 12px;
            background: #e8f0fe;
            color: #2980b9;
            margin-bottom: 6px;
        }
        .news-item h3 {
            font-size: 17px;
            margin-bottom: 6px;
        }
        .news-item h3 a {
            color: #1a1a2e;
            text-decoration: none;
        }
        .news-item h3 a:hover { color: #2980b9; }
        .news-item .summary {
            color: #555;
            font-size: 14px;
            margin: 6px 0;
            line-height: 1.6;
        }
        .news-item .meta {
            color: #888;
            font-size: 12px;
            margin-top: 8px;
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }
        .news-item .meta a {
            color: #2980b9;
            text-decoration: none;
        }
        .news-item .meta a:hover { text-decoration: underline; }
        .footer {
            text-align: center;
            color: #999;
            font-size: 13px;
            margin-top: 30px;
            padding: 20px 0;
        }
        .empty {
            text-align: center;
            color: #888;
            padding: 60px 20px;
        }
        @media (max-width: 600px) {
            body { padding: 12px; }
            .header h1 { font-size: 22px; }
            .news-item { padding: 14px 16px; }
            .toolbar input { min-width: 150px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📈 金融新闻简报</h1>
        <p>共 {{ news_count }} 条新闻 · 数据来源：新浪财经、东方财富</p>
        <span class="badge">📊 每日自动更新</span>
    </div>

    <div class="toolbar">
        <form method="GET" style="flex:1;display:flex;gap:10px;flex-wrap:wrap;">
            <input type="text" name="search" placeholder="🔍 搜索新闻..." value="{{ search_query }}">
            <button type="submit" class="btn btn-primary">搜索</button>
            <a href="/" class="btn btn-success">清除</a>
        </form>
        <a href="/fetch" class="btn btn-primary">🔄 更新新闻</a>
    </div>

    <div class="stats">
        {% if search_query %}
            搜索结果：{{ news|length }} 条匹配 "{{ search_query }}"
        {% else %}
            显示最新 {{ news|length }} 条新闻
        {% endif %}
    </div>

    {% if news %}
        {% for item in news %}
        <div class="news-item">
            <span class="source">{{ item[4] }}</span>
            <h3>
                <a href="{{ item[3] }}" target="_blank">{{ item[0] }}</a>
            </h3>
            <div class="summary">{{ item[1] }}</div>
            <div class="meta">
                <span>🕐 {{ item[2] }}</span>
                <span>🔗 <a href="{{ item[3] }}" target="_blank">查看原文</a></span>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            <p>📭 暂无新闻</p>
            <p style="font-size:14px;margin-top:8px;">点击「更新新闻」抓取最新资讯</p>
        </div>
    {% endif %}

    <div class="footer">
        ⚠️ 本简报仅供参考，不构成投资建议。
        <br>
        最后更新：{{ update_time }}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """首页 - 显示新闻列表（支持搜索）"""
    search_query = request.args.get('search', '').strip()
    
    conn = sqlite3.connect('/home/ppy/mysite/finance.db')
    c = conn.cursor()
    
    if search_query:
        c.execute("""SELECT title, summary, published, link, source 
                     FROM news 
                     WHERE title LIKE ? OR summary LIKE ? OR source LIKE ?
                     ORDER BY id DESC LIMIT 50""", 
                  ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%'))
    else:
        c.execute("SELECT title, summary, published, link, source FROM news ORDER BY id DESC LIMIT 50")
    
    news = c.fetchall()
    conn.close()
    
    return render_template_string(
        HTML_TEMPLATE,
        news=news,
        news_count=len(news),
        search_query=search_query,
        update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route('/fetch')
def fetch_news():
    """手动触发抓取（调用 main.py）"""
    try:
        import subprocess
        result = subprocess.run(['python3', '/home/ppy/mysite/main.py'], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return '<html><body style="font-family:sans-serif;text-align:center;padding:50px;"><h2>✅ 抓取完成！</h2><p>最新新闻已更新</p><a href="/" style="color:#2980b9;">← 返回首页</a></body></html>'
        else:
            return '<html><body style="font-family:sans-serif;text-align:center;padding:50px;"><h2>❌ 抓取出错</h2><p>' + result.stderr + '</p><a href="/" style="color:#2980b9;">← 返回首页</a></body></html>'
    except Exception as e:
        return '<html><body style="font-family:sans-serif;text-align:center;padding:50px;"><h2>❌ 抓取出错</h2><p>' + str(e) + '</p><a href="/" style="color:#2980b9;">← 返回首页</a></body></html>'

@app.route('/api/news')
def api_news():
    """JSON API - 供其他程序调用"""
    conn = sqlite3.connect('/home/ppy/mysite/finance.db')
    c = conn.cursor()
    c.execute("SELECT title, summary, published, link, source FROM news ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    
    return jsonify([
        {"title": r[0], "summary": r[1], "time": r[2], "link": r[3], "source": r[4]}
        for r in rows
    ])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
