import os
import psycopg2
from datetime import timedelta, datetime
import logging
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# ⏬ Завантаження .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

# 🔔 Логування
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("notificator.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("notificator")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def render_email_template(company_id, trend, change_percent, time, news_items):
    trend_color = "green" if trend == "up" else "red" if trend == "down" else "gray"

    news_html = ""
    if news_items:
        news_html += "<h3>📰 Related News:</h3><ul>"
        for item in news_items:
            news_html += f"<li><a href='{item['url']}' target='_blank'>{item['news_text']}</a></li>"
        news_html += "</ul>"

    return f"""
    <html>
  <body style="margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: #e6ecf0;">
    <div style="
      max-width: 600px;
      margin: 40px auto;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 0 10px rgba(0,0,0,0.15);
      background-color: white;
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
    ">
      <div style="padding: 30px;">
        <h2 style="color: {trend_color};">📈 Alert: {company_id}</h2>
        <p><strong>Trend:</strong> {trend.title()}</p>
        <p><strong>Change:</strong> {change_percent:.2f}%</p>
        <p><strong>Time:</strong> {time}</p>
        {news_html}
      </div>
      <div style="
        background-color: #333;
        color: white;
        text-align: center;
        font-size: 0.7em;
        padding: 8px 12px;
        border-top: 1px solid #222;
      ">
        You are receiving this alert because you're tracking <strong>{company_id}</strong>. Stay sharp. Stay informed. ⚡
      </div>
    </div>
  </body>
</html>
    """



def send_email(to_email, subject, html_body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg.set_content("Your email client does not support HTML.")
        msg.add_alternative(html_body, subtype='html')

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"📤 Email sent to {to_email}")
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {e}")

def check_and_notify():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                p.id, p.company_id, p.time, p.trend, p.change_percent,
                a.user_id, u.email, p.news_related
            FROM prices p
            JOIN campaigns c ON c.company_id = p.company_id
            JOIN alerts a ON a.campaign_id = c.id AND a.is_active = TRUE
            JOIN users u ON a.user_id = u.id
            WHERE p.is_trend_change = TRUE
              AND c.is_active = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM notifications n WHERE n.price_id = p.id AND n.user_id = a.user_id
              )
                       AND (
            a.alert_condition = 'all'
            OR (a.alert_condition = 'up' AND p.trend = 'up')
            OR (a.alert_condition = 'down' AND p.trend = 'down')
        and p.news_related = True
)
        """)

        results = cursor.fetchall()

        for row in results:
            price_id, company_id, time, trend, change_percent, user_id, email, news_related = row

            logger.info(f"🔔 Alert: {company_id} trend → {trend} ({change_percent:.2f}%)")
            logger.info(f"👤 Notify user: {email}")

            news_rows = []
            if news_related:
                query = """
                    SELECT url, news_text
                    FROM news_data
                    WHERE company_id = %s AND time BETWEEN %s AND %s
                    ORDER BY time DESC
                """

                time_from = (time - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
                time_to = (time + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute(query, (company_id, time_from, time_to))
                news_rows = cursor.fetchall()


            html_body = render_email_template(
                company_id=company_id,
                trend=trend,
                change_percent=change_percent,
                time=time.strftime("%Y-%m-%d %H:%M"),
                news_items=[{"news_text": t, "url": u} for u, t in news_rows] if news_rows else []
            )
            print(html_body)
            send_email(email, f"📈 Stock Alert: {company_id} → {trend.upper()}", html_body)

            cursor.execute("""
                INSERT INTO notifications (price_id, user_id)
                VALUES (%s, %s)
            """, (price_id, user_id))

        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"✅ Sent {len(results)} notification(s)")

    except Exception as e:
        logger.error(f"❌ Error in notificator: {e}")

if __name__ == "__main__":
    logger.info("🚀 Notificator started")
    check_and_notify()
