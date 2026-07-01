def get_subscribers():
    """获取所有订阅邮箱"""
    try:
        conn = sqlite3.connect('finance.db')
        c = conn.cursor()
        c.execute("SELECT email FROM subscribers")
        rows = c.fetchall()
        conn.close()
        return [row[0] for row in rows]
    except:
        return []

def send_email(articles):
    if not articles:
        logging.info("没有新新闻，跳过邮件发送")
        return
    
    subscribers = get_subscribers()
    if not subscribers:
        logging.info("没有订阅者，跳过邮件发送")
        return
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        html = "<h2>📈 今日金融新闻简报 - " + today + "</h2>"
        html += "<p>共 " + str(len(articles)) + " 条新闻</p ><hr>"
        
        for idx, art in enumerate(articles[:15], 1):
            source_tag = art.get("source", "未知来源")
            html += '<div style="margin-bottom:15px; padding:10px; border-left: 3px solid #2980b9;">'
            html += '<h3 style="margin:0 0 5px 0;">' + str(idx) + '. <a href="' + art['link'] + '" style="color:#2980b9;">' + art['title'] + '</a ></h3>'
            html += '<span style="font-size:12px; color:#2980b9; background:#e8f0fe; padding:2px 10px; border-radius:12px;">📰 ' + source_tag + '</span>'
            if art['summary'] and len(art['summary']) > 5:
                html += '<p style="color:#555; margin:8px 0; font-size:14px;">📌 ' + art['summary'] + '</p >'
            html += '<small style="color:#888;">🕐 ' + art['published'] + ' | 🔗 <a href="' + art['link'] + '" style="color:#2980b9;">查看原文</a ></small>'
            html += '</div><hr>'
        
        html += "<p style='color:gray;'>⚠️ 本简报仅供参考，不构成投资建议。</p >"
        html += "<p style='color:#888; font-size:12px;'>📧 如需取消订阅，请访问网站操作</p >"
        
        # 发送给所有订阅者
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['Subject'] = "📈 金融新闻简报 " + today
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        success_count = 0
        for subscriber in subscribers:
            try:
                msg['To'] = subscriber
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                    server.login(SENDER_EMAIL, SENDER_PASSWORD)
                    server.sendmail(SENDER_EMAIL, subscriber, msg.as_string())
                success_count += 1
                logging.info("已发送到: " + subscriber)
            except Exception as e:
                logging.error("发送到 " + subscriber + " 失败: " + str(e))
        
        logging.info("邮件发送完成！成功 " + str(success_count) + " 个订阅者")
    except Exception as e:
        logging.error("邮件发送失败: " + str(e))
