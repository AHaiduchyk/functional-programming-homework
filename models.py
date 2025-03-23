def init_tables(conn):
    cursor = conn.cursor()

    print("[DB]  Creating 'users' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE
        );
    """)

    print("[DB]  Creating 'campaigns' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id SERIAL PRIMARY KEY,
            created_by TEXT NOT NULL REFERENCES users(username),
            company_id VARCHAR(10) NOT NULL,
            date_created TIMESTAMPTZ DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        );
    """)

    print("[DB]  Creating 'prices' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            price FLOAT,
            time TIMESTAMPTZ,
            previous_close FLOAT,
            open_price FLOAT,
            day_low FLOAT,
            day_high FLOAT,
            change_percent FLOAT,
            volume BIGINT,
            trend TEXT,
            is_trend_change BOOLEAN,
            news_related BOOLEAN
        );
    """)

    print("[DB]  Creating 'news_data' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_data (
            id TEXT PRIMARY KEY,
            company_id VARCHAR(10) NOT NULL,
            news_text TEXT,
            time TIMESTAMPTZ,
            url TEXT,
            summary TEXT,
            provider TEXT
        );
    """)

    print("[DB]  Creating 'alerts' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            alert_type TEXT DEFAULT 'trend_change',
            alert_condition TEXT DEFAULT 'all',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    print("[DB]  Creating 'notifications' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            price_id INTEGER NOT NULL REFERENCES prices(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            sent_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    conn.commit()
    cursor.close()

    return "[DB]  Tables initialized"
