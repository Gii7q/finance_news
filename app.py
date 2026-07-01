from flask import Flask, render_template_string, request, jsonify
import sqlite3
from datetime import datetime
import re

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📈 金融新闻简报</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; background: #f0f2f5; padding: 20px; max-width: 1000px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 30px; border-radius: 12px; margin-bottom: 25px; text-align: center; }
        .header h1 { font-size: 28px; }
        .header p { opacity: 0.8; margin-top: 8px; font-size: 14px; }
        .badge { display: inline-block; background: #e74c3c; color: white; font-size: 12px; padding: 2px 14px; border-radius: 20px; margin-top: 8px; }
        .update-time { color: #ddd; font-size: 13px; margin-top: 10px; }
        
        .toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; align-items: center; }
        .toolbar input[type="text"] { flex: 1; min-width: 200px; padding: 10px 16px; border: 2px solid #ddd; border-radius: 8px; font-size: 15px; }
        .toolbar input[type="text"]:focus { outline: none; border-color: #2980b9; }
        .toolbar input[type="email"] { flex: 1; min-width: 200px; padding: 10px 16px; border: 2px solid #ddd; border-radius: 8px; font-size: 15px; }
        .toolbar input[type="email"]:focus { outline: none; border-color: #27ae60; }
        .btn { padding: 10px 24px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn-primary { background: #2980b9; color: white; }
        .btn-primary:hover { background: #1a6b99; }
        .btn-success { background: #27ae60; color: white; }
        .btn-success:hover { background: #1e8449; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-danger:hover { background: #c0392b; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-warning:hover { background: #d68910; }
        
        .stats { color: #666; font-size: 14px; margin-bottom: 15px; }
        .news-item { background: white; border-radius: 10px; padding: 18px 22px; margin-bottom: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-left: 4px solid #2980b9; }
        .news-item .source { display: inline-block; font-size: 11px; padding: 2px 10px; border-radius: 12px; background: #e8f0fe; color: #2980b9; margin-bottom: 6px; }
        .news-item h3 { font-size: 17px; margin-bottom: 6px; }
        .news-item h3 a { color: #1a1a2e; text-decoration: none; }
        .news-item h3 a:hover { color: #2980b9; }
        .news-item .summary { color: #555; font-size: 14px; margin: 6px 0; }
        .news-item .meta { color: #888; font-size: 12px; margin-top: 8px; display: flex; gap: 16px; flex-wrap: wrap; }
        .news-item .meta a { color: #2980b9; text-decoration: none; }
        
        .subscribe-box { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-left: 4px solid #27ae60; }
        .subscribe-box h3 { margin-bottom: 10px; color: #1a1a2e; }
        .subscribe-box .form-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .subscribe-box .form-row input { flex: 1; min-width: 200px; padding: 10px 16px; border: 2px solid #ddd; border-radius: 8px; font-size: 15px; }
        .subscribe-box .form-row input:focus { outline: none; border-color: #27ae60; }
        .msg { padding: 10px 16px; border-radius: 8px; margin: 10px 0; display: none; }
        .msg-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .msg-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .msg-info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        
        .footer { text-align: center; color: #999; font-size: 13px; margin-top: 30px; padding: 20px 0; }
        .empty { text-align: center; color: #888; padding: 60px 20px; }
        @media (max-width: 600px) { body { padding: 12px; } .header h1 { font-size: 22px; } .news-item { padding: 14px 16px; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>📈 金融新闻简报</h1>
        <p>共 {{ news_count }} 条新闻</p >
        <span class="badge">🤖 每日自动更新</span>
        <div class="update-time">⏰ 最后更新：{{ update_time }}</div>
    </div>

    <!-- ===== 搜索栏 ===== -->
    <div class="toolbar">
        <form method="GET" style="flex:1;display:flex;gap:10px;flex-wrap:wrap;">
            <input type="text" name="search" placeholder="🔍 搜索新闻（标题/摘要）" value="{{ search_query }}">
            <button type="submit" class="btn btn-primary">搜索</button>
            <a href=" " class="btn btn-warning">清除</a >
        </form>
        <a href="/fetch" class="btn btn-success">🔄 更新新闻</a >
    </div>

    <!-- ===== 订阅/取消订阅 ===== -->
    <div class="subscribe-box">
        <h3>📧 邮件订阅</h3>
        <p style="color:#666; font-size:14px; margin-bottom:10px;">输入邮箱订阅每日新闻简报，或取消订阅</p >
        <div class="form-row">
            <input type="email" id="email_input" placeholder="请输入邮箱地址">
            <button class="btn btn-success" onclick="subscribe()">✅ 订阅</button>
            <button class="btn btn-danger" onclick="unsubscribe()">❌ 取消订阅</button>
        </div>
        <div id="subscribe_msg" class="msg"></div>
        <div style="margin-top:10px; font-size:13px; color:#888;">
            当前订阅人数：{{ subscriber_count }}
        </div>
    </div>

    <!-- ===== 统计信息 ===== -->
    <div class="stats">
        {% if search_query %}
            搜索结果：{{ news|length }} 条匹配 "{{ search_query }}"
        {% else %}
            显示最新 {{ news|length }} 条新闻
        {% endif %}
    </div>

    <!-- ===== 新闻列表 ===== -->
    {% if news %}
        {% for item in news %}
        <div class="news-item">
            <span class="source">{{ item[4] }}</span>
            <h3><a href="{{ item[3] }}" target="_blank">{{ item[0] }}</a ></h3>
            <div class="summary">{{ item[1] }}</div>
            <div class="meta">
                <span>🕐 {{ item[2] }}</span>
                <span>🔗 <a href="{{ item[3] }}" target="_blank">查看原文</a ></span>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty"><p>📭 暂无新闻</p ></div>
    {% endif %}

    <div class="footer">
        ⚠️ 本简报仅供参考，不构成投资建议。
    </div>

    <script>
        function showMsg(msg, type) {
            var el = document.getElementById('subscribe_msg');
            el.textContent = msg;
            el.className = 'msg msg-' + type;
            el.style.display = 'block';
            setTimeout(function() { el.style.display = 'none'; }, 5000);
        }

        function subscribe() {
            var email = document.getElementById('email_input').value.trim();
            if (!email) { showMsg('请输入邮箱地址', 'error'); return; }
            if (!email.includes('@') || !email.includes('.')) { showMsg('请输入有效邮箱', 'error'); return; }
            
            fetch('/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'email=' + encodeURIComponent(email)
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showMsg(data.message, 'success');
                    document.getElementById('email_input').value = '';
                    location.reload();
                } else {
                    showMsg(data.message, 'error');
                }
            })
            .catch(() => showMsg('请求失败，请重试', 'error'));
        }

        function unsubscribe() {
            var email = document.getElementById('email_input').value.trim();
            if (!email) { showMsg('请输入邮箱地址', 'error'); return; }
            if (!email.includes('@') || !email.includes('.')) { showMsg('请输入有效邮箱', 'error'); return; }
            
            if (!confirm('确认要取消订阅吗？')) return;
            
            fetch('/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'email=' + encodeURIComponent(email)
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showMsg(data.message, 'info');
                    document.getElementById('email_input').value = '';
                    location.reload();
                } else {
                    showMsg(data.message, 'error');
                }
            })
            .catch(() => showMsg('请求失败，请重试', 'error'));
        }
    </script>
</body>
</html>
"""

def init_subscribers_table():
    """初始化订阅者表"""
    conn = sqlite3.connect('/home/ppy/mysite/finance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS subscribers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE,
                  subscribed_at TEXT)''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    search_query = request.args.get('search', '').strip()
    
    conn = sqlite3.connect('/home/ppy/mysite/finance.db')
    c = conn.cursor()
    
    # 确保订阅表存在
    init_subscribers_table()
    
    # 查询订阅人数
    c.execute("SELECT COUNT(*) FROM subscribers")
    subscriber_count = c.fetchone()[0]
    
    # 查询新闻
    if search_query:
        c.execute("""SELECT title, summary, published, link, source 
                     FROM news 
                     WHERE title LIKE ? OR summary LIKE ?
                     ORDER BY id DESC LIMIT 50""", 
                  ('%' + search_query + '%', '%' + search_query + '%'))
    else:
        c.execute("SELECT title, summary, published, link, source FROM news ORDER BY id DESC LIMIT 50")
    
    news = c.fetchall()
    conn.close()
    
    return render_template_string(
        HTML_TEMPLATE,
        news=news,
        news_count=len(news),
        search_query=search_query,
        subscriber_count=subscriber_count,
        update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email', '').strip()
    
    # 验证邮箱格式
    if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({'success': False, 'message': '请输入有效邮箱地址'})
    
    try:
        conn = sqlite3.connect('/home/ppy/mysite/finance.db')
        c = conn.cursor()
        c.execute("INSERT INTO subscribers (email, subscribed_at) VALUES (?, ?)",
                  (email, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '✅ 订阅成功！每日将收到新闻简报'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '该邮箱已订阅'})
    except Exception as e:
        return jsonify({'success': False, 'message': '订阅失败，请重试'})

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    email = request.form.get('email', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': '请输入邮箱地址'})
    
    try:
        conn = sqlite3.connect('/home/ppy/mysite/finance.db')
        c = conn.cursor()
        c.execute("DELETE FROM subscribers WHERE email=?", (email,))
        conn.commit()
        deleted = c.rowcount
        conn.close()
        
        if deleted > 0:
            return jsonify({'success': True, 'message': '✅ 已取消订阅，不再发送邮件'})
        else:
            return jsonify({'success': False, 'message': '该邮箱未订阅'})
    except Exception as e:
        return jsonify({'success': False, 'message': '取消失败，请重试'})

@app.route('/fetch')
def fetch_news():
    try:
        import subprocess
        result = subprocess.run(['python3', '/home/ppy/mysite/main.py'], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return '<html><body style="text-align:center;padding:50px;font-family:system-ui;"><h2>✅ 抓取完成！</h2><p>最新新闻已更新</p ><a href="/">← 返回首页</a ></body></html>'
        else:
            return f'<html><body style="text-align:center;padding:50px;font-family:system-ui;"><h2>❌ 抓取出错</h2><p>{result.stderr}</p ><a href="/">← 返回首页</a ></body></html>'
    except Exception as e:
        return f'<html><body style="text-align:center;padding:50px;font-family:system-ui;"><h2>❌ 抓取出错</h2><p>{str(e)}</p ><a href="/">← 返回首页</a ></body></html>'

@app.route('/api/subscribers')
def api_subscribers():
    """获取订阅者列表（API）"""
    conn = sqlite3.connect('/home/ppy/mysite/finance.db')
    c = conn.cursor()
    c.execute("SELECT email, subscribed_at FROM subscribers ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"email": r[0], "subscribed_at": r[1]} for r in rows])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
