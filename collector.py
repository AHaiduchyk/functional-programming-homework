import yfinance as yf
import psycopg2
import os
import hashlib
from datetime import datetime, timedelta
import logging
from dateutil import parser
import pytz
from datetime import time
import requests

# --- Logging config ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("collector.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("collector")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mydatabase")


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def parse_pub_date(pub_date_str: str) -> str:
    """
    Parses an ISO 8601 UTC date string and returns a local timezone-aware datetime as string.
    """
    try:
        dt = parser.isoparse(pub_date_str)
        
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        else:
            dt = dt.astimezone(pytz.UTC)

        local_dt = dt.astimezone()  # Convert to local timezone
        return local_dt.isoformat()

    except Exception:
        return datetime.now().astimezone().isoformat()


def fetch_campaigns():
    """
    Fetches a list of active campaigns from the database.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT company_id FROM campaigns 
            WHERE is_active = TRUE
        """)
        rows = cursor.fetchall()
        conn.close()
        return [{"ticker": row[0]} for row in rows]
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        return []



def fetch_stock_price(company):
    """
    Fetches stock price info for a given company from Yahoo Finance.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    try:
        stock = yf.Ticker(company["ticker"], session=session)
        info = stock.info
        return {
            "company_id": company["ticker"],
            "price": float(info.get("currentPrice")), #погратись із цим, на вихідних ринки не працюють
            "time": datetime.utcnow(),
            "previous_close": info.get("previousClose"),
            "open_price": info.get("open"),
            "day_low": info.get("dayLow"),
            "day_high": info.get("dayHigh"),
            "change_percent": info.get("regularMarketChangePercent"),
            "volume": info.get("volume")
        }
    except Exception as e:
        logger.error(f"Error fetching stock price for {company['ticker']}: {e}")
        return None


def store_price(data):
    """
    Stores the current stock price and determines trend change.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT price, trend FROM prices 
            WHERE company_id = %s 
            ORDER BY time DESC 
            LIMIT 1
        """, (data["company_id"],))
        prev = cursor.fetchone()

        change_percent = None
        trend = None
        is_trend_change = None

        if prev:
            prev_price, prev_trend = prev
            if prev_price and prev_price != 0:
                prev_price = float(prev_price)
                change_percent = ((data["price"] - prev_price) / prev_price) * 100
                trend = "up" if change_percent > 0 else "down" if change_percent < 0 else "flat"
                is_trend_change = trend != prev_trend
            else:
                trend = "flat"
                is_trend_change = False
        else:
            trend = "flat"
            is_trend_change = False

        # Check if related news exists around the same time
        cursor.execute("""
            SELECT 1 FROM news_data 
            WHERE company_id = %s 
              AND time BETWEEN %s AND %s
            LIMIT 1
        """, (
            data["company_id"],
            data["time"] - timedelta(minutes=30),
            data["time"] + timedelta(minutes=30)
        ))
        news_nearby = bool(cursor.fetchone())

        # Insert price record
        cursor.execute("""
            INSERT INTO prices (
                company_id, price, time,
                previous_close, open_price, day_low, day_high,
                change_percent, volume,
                trend, is_trend_change, news_related
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["company_id"],
            data["price"],
            data["time"],
            data["previous_close"],
            data["open_price"],
            data["day_low"],
            data["day_high"],
            data.get("change_percent", change_percent),
            data["volume"],
            trend,
            is_trend_change,
            news_nearby
        ))

        conn.commit()
        cursor.close()
        conn.close()

        if change_percent is not None:
            logger.info(f"{data['company_id']} → {data['price']} | Trend: {trend} | Δ {change_percent:.2f}%")
        else:
            logger.info(f"{data['company_id']} → {data['price']} | Trend: {trend}")

    except Exception as e:
        logger.error(f"Error storing price: {e}")


def fetch_news(company):
    """
    Fetches news articles for a given company from Yahoo Finance.
    """
    try:
        stock = yf.Ticker(company["ticker"])
        news_list = stock.get_news()
        formatted_news = []

        for news in news_list:
            content = news.get('content', {})
            formatted_news.append({
                "company_id": company["ticker"],
                "news_text": content.get("title", "No title"),
                "time": parse_pub_date(content.get("pubDate", "")),
                "url": content.get("canonicalUrl", {}).get("url", ""),
                "summary": content.get("summary", ""),
                "provider": content.get("provider", {}).get("displayName", "Unknown")
            })
        return formatted_news
    except Exception as e:
        logger.error(f"Error fetching news for {company['ticker']}: {e}")
        return []


def store_news(news_items):
    """
    Stores unique news items to the database using hashed URLs to avoid duplication.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        inserted_count = 0

        for news in news_items:
            url_hash = hashlib.md5(news["url"].encode()).hexdigest()
            cursor.execute("SELECT 1 FROM news_data WHERE id = %s LIMIT 1", (url_hash,))
            if cursor.fetchone():
                logger.debug(f"Skipped duplicate: {news['url']}")
                continue

            cursor.execute("""
                INSERT INTO news_data (id, company_id, news_text, time, url, summary, provider)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                url_hash,
                news["company_id"],
                news["news_text"],
                news["time"],
                news["url"],
                news["summary"],
                news["provider"]
            ))
            inserted_count += 1

        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Inserted {inserted_count} new news items.")
    except Exception as e:
        logger.error(f"Error storing news: {e}")


def main():
    """
    Entry point: Fetch campaigns, collect price & news, and store them.
    """
    companies = fetch_campaigns()
    logger.info(f"Found campaigns: {companies}")

    for company in companies:
        price = fetch_stock_price(company)
        logger.info(f"Price for {company['ticker']}: {price}")
        if price:
            store_price(price)
        news_list = fetch_news(company)
        logger.info(f"Found {len(news_list)} news items for {company['ticker']}")
        if news_list:
            store_news(news_list)
        


if __name__ == "__main__":
    main()
