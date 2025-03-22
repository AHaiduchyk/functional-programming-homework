import yfinance as yf
import psycopg2
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def fetch_campaigns():
    """Fetch tracked companies from campaigns table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT company_id FROM campaigns")
        rows = cursor.fetchall()
        conn.close()
        return [{"ticker": row[0]} for row in rows]
    except Exception as e:
        print(f"Error fetching campaigns: {e}")
        return []

def fetch_stock_price(company):
    try:
        stock = yf.Ticker(company["ticker"])
        price = stock.history(period="1d").iloc[-1]["Close"]
        return {
            "company_id": company["ticker"],
            "price": price,
            "time": datetime.utcnow()
        }
    except Exception as e:
        print(f"Error fetching stock price for {company['ticker']}: {e}")
        return None

def store_price(data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prices (company_id, price, time)
            VALUES (%s, %s, %s)
        """, (data["company_id"], data["price"], data["time"]))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error storing price: {e}")

def fetch_news(company):
    try:
        stock = yf.Ticker(company["ticker"])
        news_list = stock.get_news()
        formatted_news = []

        for news in news_list:
            content = news.get('content', {})
            formatted_news.append({
                "company_id": company["ticker"],
                "news_text": content.get("title", "No title"),
                "time": content.get("pubDate", datetime.utcnow()),
                "url": content.get("clickThroughUrl", {}).get("url", ""),
                "summary": content.get("summary", ""),
                "provider": content.get("provider", {}).get("displayName", "Unknown")
            })
        return formatted_news
    except Exception as e:
        print(f"Error fetching news for {company['ticker']}: {e}")
        return []

def store_news(news_items):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for news in news_items:
            cursor.execute("""
                INSERT INTO news_data (company_id, news_text, time, url, summary, provider)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                news["company_id"],
                news["news_text"],
                news["time"],
                news["url"],
                news["summary"],
                news["provider"]
            ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error storing news: {e}")

def main():
    companies = fetch_campaigns()

    for company in companies:
        price = fetch_stock_price(company)
        if price:
            store_price(price)

        news_list = fetch_news(company)
        if news_list:
            store_news(news_list)

if __name__ == "__main__":
    main()
