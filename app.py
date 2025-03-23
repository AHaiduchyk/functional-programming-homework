from flask import Flask, request, jsonify
import os
import psycopg2
from models import init_tables
import hashlib
import base64
from functools import wraps
import collector
import threading
import time
import re
import notificator

app = Flask(__name__)

# Load DB connection string from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Regex to validate emails
EMAIL_REGEX = r"^[^@]+@[^@]+\.[^@]+$"


def is_valid_email(email):
    return re.match(EMAIL_REGEX, email) is not None


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


# Authentication decorator for protected routes
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"message": "Authorization token is required"}), 401

        try:
            decoded_token = base64.b64decode(token.split(" ")[1]).decode("utf-8")
            username, password = decoded_token.split(":")
        except Exception:
            return jsonify({"message": "Invalid token"}), 401

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            if not user:
                return jsonify({"message": "Invalid token"}), 401
        except Exception as e:
            return jsonify({"message": f"Token check failed: {str(e)}"}), 500

        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def hello():
    try:
        get_db_connection()
        return "Connected to PostgreSQL!"
    except Exception as e:
        return f"Database connection failed: {str(e)}"


@app.route("/test")
def test():
    return "This is a test route!"


@app.route("/tables")
@token_required
def get_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        )
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return {"tables": tables}
    except Exception as e:
        return f"Failed to get tables: {str(e)}"


def create_tables():
    try:
        conn = get_db_connection()
        print(init_tables(conn))
    except Exception as e:
        print(f"Table initialization failed: {str(e)}")


# Run collector and notificator every 30 minutes in background
def start_background_loop():
    def run_collect_and_notify():
        while True:
            try:
                print("[BG] ▶️ Running collector...")
                collector.main()
                print("[BG] ✅ Collector done")

                print("[BG] ▶️ Sending notifications...")
                notificator.check_and_notify()
                print("[BG] ✅ Notifications sent")
            except Exception as e:
                print(f"[BG] ❌ Error: {e}")
            time.sleep(1800)

    thread = threading.Thread(target=run_collect_and_notify, daemon=True)
    thread.start()


@app.route("/user/email", methods=["POST"])
@token_required
def update_email():
    try:
        data = request.json
        new_email = data.get("email")

        if not new_email or not is_valid_email(new_email):
            return jsonify({"message": "Invalid or missing email"}), 400

        token = request.headers.get("Authorization")
        decoded_token = base64.b64decode(token.split(" ")[1]).decode("utf-8")
        username, _ = decoded_token.split(":")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM users WHERE email = %s", (new_email,))
        if cursor.fetchone():
            return jsonify({"message": "Email is already in use"}), 400

        cursor.execute(
            "UPDATE users SET email = %s WHERE username = %s",
            (new_email, username),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Email updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")

        if not username or not password or not email:
            return jsonify({"message": "Username, password, and email required"}), 400

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = %s OR email = %s",
            (username, email),
        )
        if cursor.fetchone():
            return jsonify({"message": "User or email already exists"}), 400

        cursor.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s)",
            (username, hashed_password, email),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User registered"}), 201
    except Exception as e:
        return jsonify({"message": f"Registration failed: {str(e)}"}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            return jsonify({"message": "Missing username or password"}), 400

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND password_hash = %s",
            (username, hashed_password),
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            token = base64.b64encode(f"{username}:{password}".encode()).decode("utf-8")
            return jsonify({"message": "Login successful", "token": token}), 200
        return jsonify({"message": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"message": f"Login failed: {str(e)}"}), 500

@app.route("/collect", methods=["POST"])
@token_required
def run_collector():
    try:
        collector.main()
        return jsonify({"message": "Data collection complete"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/trends/<ticker>", methods=["GET"])
@token_required
def get_latest_trend(ticker):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT price, time, trend, change_percent, is_trend_change, news_related
            FROM prices
            WHERE company_id = %s
            ORDER BY time DESC
            LIMIT 1
        """, (ticker.upper(),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return jsonify({
                "company_id": ticker.upper(),
                "price": float(row[0]),
                "time": row[1].isoformat(),
                "trend": row[2],
                "change_percent": float(row[3]) if row[3] is not None else None,
                "is_trend_change": row[4],
                "news_related": row[5]
            })
        return jsonify({"message": "No data found for this ticker"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/campaigns", methods=["POST"])
@token_required
def create_campaign():
    try:
        data = request.json
        company_id = data.get("company_id")
        alert_condition = data.get("alert_condition", "all").lower()

        if not company_id:
            return jsonify({"message": "Missing company_id"}), 400

        if alert_condition not in ["all", "up", "down"]:
            return jsonify({"message": "Invalid alert_condition"}), 400

        # Get user from token
        token = request.headers.get("Authorization")
        decoded_token = base64.b64decode(token.split(" ")[1]).decode("utf-8")
        username, _ = decoded_token.split(":")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Avoid creating duplicate campaign
        cursor.execute("""
            SELECT id FROM campaigns 
            WHERE company_id = %s AND created_by = %s AND is_active = TRUE
        """, (company_id.upper(), username))
        if cursor.fetchone():
            return jsonify({"message": "Campaign already exists"}), 400

        # Create campaign
        cursor.execute("""
            INSERT INTO campaigns (company_id, created_by, date_created)
            VALUES (%s, %s, NOW()) RETURNING id
        """, (company_id.upper(), username))
        campaign_id = cursor.fetchone()[0]

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_id = cursor.fetchone()[0]

        # Create alert
        cursor.execute("""
            INSERT INTO alerts (campaign_id, user_id, alert_type, alert_condition)
            VALUES (%s, %s, 'trend_change', %s)
        """, (campaign_id, user_id, alert_condition))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": f"Started tracking {company_id.upper()} with alert condition: {alert_condition}"
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/campaigns/<int:campaign_id>/archive", methods=["POST"])
@token_required
def archive_campaign(campaign_id):
    try:
        token = request.headers.get("Authorization")
        decoded_token = base64.b64decode(token.split(" ")[1]).decode("utf-8")
        username, _ = decoded_token.split(":")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure user owns this campaign
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND created_by = %s
        """, (campaign_id, username))
        if not cursor.fetchone():
            return jsonify({"message": "Not found or not your campaign"}), 403

        # Archive it
        cursor.execute("""
            UPDATE campaigns SET is_active = FALSE WHERE id = %s
        """, (campaign_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Campaign archived successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/alerts/<int:alert_id>", methods=["PATCH"])
@token_required
def update_alert_condition(alert_id):
    """
    Allows user to update the condition of their alert (e.g. all, up, down).
    """
    try:
        data = request.json
        new_condition = data.get("alert_condition", "").lower()

        if new_condition not in ["all", "up", "down"]:
            return jsonify({
                "message": "Invalid alert_condition. Must be one of: all, up, down"
            }), 400

        # Verify ownership of the alert
        token = request.headers.get("Authorization")
        decoded_token = base64.b64decode(token.split(" ")[1]).decode("utf-8")
        username, _ = decoded_token.split(":")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s AND u.username = %s
        """, (alert_id, username))
        alert = cursor.fetchone()

        if not alert:
            return jsonify({"message": "Alert not found or access denied"}), 403

        # Update condition
        cursor.execute("""
            UPDATE alerts SET alert_condition = %s WHERE id = %s
        """, (new_condition, alert_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": f"Alert condition updated to '{new_condition}'"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/alerts", methods=["GET"])
@token_required
def get_user_alerts():
    """
    Returns a list of alerts created by the current user.
    """
    try:
        token = request.headers.get("Authorization")
        decoded_token = base64.b64decode(token.split(" ")[1]).decode("utf-8")
        username, _ = decoded_token.split(":")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.alert_type, a.alert_condition, a.is_active,
                   c.company_id, c.is_active AS campaign_active,
                   a.created_at
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            JOIN campaigns c ON a.campaign_id = c.id
            WHERE u.username = %s
            ORDER BY a.created_at DESC
        """, (username,))
        alerts = cursor.fetchall()
        cursor.close()
        conn.close()

        result = []
        for row in alerts:
            result.append({
                "alert_id": row[0],
                "alert_type": row[1],
                "alert_condition": row[2],
                "is_active": row[3],
                "company_id": row[4],
                "campaign_active": row[5],
                "created_at": row[6].isoformat()
            })

        return jsonify({"alerts": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/mock_test", methods=["POST"])
def mock_test_data():
    """
    Inserts mock data into the system (user, campaign, alert, prices, news).
    Useful for testing notification system.
    """
    try:
        data = request.json
        company_id = data.get("company_id", "MOCK").upper()
        trend = data.get("trend", "up").lower()
        change_percent = float(data.get("change_percent", 2.5))
        email = data.get("email", "mockuser@example.com")
        news_list = data.get("news", [])

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Create user if doesn't exist
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            username = email.split("@")[0]
            password_hash = hashlib.sha256("testpass".encode()).hexdigest()
            cursor.execute("""
                INSERT INTO users (username, password_hash, email)
                VALUES (%s, %s, %s) RETURNING id
            """, (username, password_hash, email))
            user_id = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT id, username FROM users WHERE email = %s", (email,))
            user_id, username = cursor.fetchone()

        # 2. Create campaign if not exists
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE company_id = %s AND created_by = %s AND is_active = TRUE
        """, (company_id, username))
        campaign = cursor.fetchone()
        if not campaign:
            cursor.execute("""
                INSERT INTO campaigns (company_id, created_by)
                VALUES (%s, %s) RETURNING id
            """, (company_id, username))
            campaign_id = cursor.fetchone()[0]
        else:
            campaign_id = campaign[0]

        # 3. Create alert if not exists
        cursor.execute("""
            SELECT id FROM alerts WHERE campaign_id = %s AND user_id = %s
        """, (campaign_id, user_id))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO alerts (campaign_id, user_id)
                VALUES (%s, %s)
            """, (campaign_id, user_id))

        # 4. Add price record
        cursor.execute("""
            INSERT INTO prices (company_id, price, time, trend, change_percent, is_trend_change, news_related)
            VALUES (%s, %s, NOW(), %s, %s, TRUE, %s)
            RETURNING id, time
        """, (company_id, 100.0, trend, change_percent, bool(news_list)))
        price_id, price_time = cursor.fetchone()

        # 5. Add news (if any)
        for i, news in enumerate(news_list):
            cursor.execute("""
                INSERT INTO news_data (id, company_id, news_text, time, url, provider)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                f"{company_id}_MOCK_{i}_{price_id}",
                company_id,
                news.get("text", "Sample news..."),
                price_time,
                news.get("url", ""),
                "MockNews"
            ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "✅ Mock data inserted successfully",
            "company_id": company_id,
            "trend": trend,
            "email": email,
            "news_count": len(news_list)
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Start the server
if __name__ == "__main__":
    create_tables()
    start_background_loop()
    app.run(debug=True, host="0.0.0.0", port=5001)
