
# Функція для створення таблиці
def init_tables(conn):
    try:
        # Підключення до бази даних
        cursor = conn.cursor()

        # Запит для створення таблиці news_data
        create_news_data_table_query = '''
        CREATE TABLE IF NOT EXISTS news_data (
            id SERIAL PRIMARY KEY,
            company_id VARCHAR(4) NOT NULL,
            news_text TEXT,
            time TIMESTAMPTZ ,
            url TEXT ,
            summary TEXT,
            provider TEXT 
        );
        '''
        cursor.execute(create_news_data_table_query)

        # Запит для створення таблиці prices
        create_prices_table_query = '''
        CREATE TABLE IF NOT EXISTS prices (
            id SERIAL PRIMARY KEY,
            company_id TEXT NOT NULL,
            price DECIMAL NOT NULL,
            time TIMESTAMPTZ NOT NULL
        );
        '''
        cursor.execute(create_prices_table_query)

        # Запит для створення таблиці campaigns
        create_campaigns_table_query = '''
        CREATE TABLE IF NOT EXISTS campaigns (
            id SERIAL PRIMARY KEY,
            created_by TEXT NOT NULL,
            company_id TEXT NOT NULL,
            date_created TIMESTAMPTZ NOT NULL
        );
        '''
        cursor.execute(create_campaigns_table_query)

        # Запит для створення таблиці analytics
        create_analytics_table_query = '''
        CREATE TABLE IF NOT EXISTS analytics (
            id SERIAL PRIMARY KEY,
            company_id TEXT NOT NULL,
            value TEXT NOT NULL
        );
        '''
        cursor.execute(create_analytics_table_query)

        create_users_query = '''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        '''
        cursor.execute(create_users_query)

        conn.commit()
        cursor.close()
        conn.close()
        return "Tables created or already exist."
    except Exception as e:
        return f"Error creating tables: {str(e)}"
    



