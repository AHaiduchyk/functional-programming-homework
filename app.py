from flask import Flask, request, jsonify
import os
import psycopg2
from models import init_tables  # Імпортуємо функцію для ініціалізації таблиць
import hashlib
import base64
from functools import wraps

# Створюємо додаток
app = Flask(__name__)

# Підключення до бази даних
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)  # Використовуємо DATABASE_URL, що заданий в оточенні
    return conn

# Декоратор для перевірки токена
def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({"message": "Authorization token is required"}), 401

        try:
            # Перевірка правильності формату токену
            decoded_token = base64.b64decode(token.split(" ")[1]).decode('utf-8')
            username, password = decoded_token.split(":")
        except Exception as e:
            return jsonify({"message": "Invalid token"}), 401

        # Перевіряємо, чи є користувач в базі даних
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
            return jsonify({"message": f"Error checking token: {str(e)}"}), 500

        return f(*args, **kwargs)

    return decorated_function

@app.route("/")
def hello():
    try:
        conn = get_db_connection()
        return "Connected to PostgreSQL!"
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route("/test")
def test():
    return "This is a test route!"

@app.route("/tables")
@token_required  # Захищаємо маршрут
def get_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Запит для отримання списку таблиць
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        
        # Отримуємо всі результати
        tables = cursor.fetchall()
        
        # Перетворюємо їх у список
        table_list = [table[0] for table in tables]
        
        cursor.close()
        conn.close()
        
        return {"tables": table_list}
    except Exception as e:
        return f"Error retrieving tables: {str(e)}"

@app.before_request
def create_tables():
    try:
        # Видаляємо цей обробник після першого запиту
        app.before_request_funcs[None].remove(create_tables)
        
        # Ініціалізація таблиць
        conn = get_db_connection()
        result = init_tables(conn)  # Викликаємо функцію для створення таблиць

        print(result)  # Виводимо результат в консоль
    except Exception as e:
        print(f"Error initializing tables: {str(e)}")

# Маршрут для реєстрації користувача
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400
        
        # Хешуємо пароль
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Перевіряємо, чи є такий користувач в базі
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            return jsonify({"message": "User already exists"}), 400
        
        # Додаємо нового користувача в базу
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed_password))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"message": f"Error during registration: {str(e)}"}), 500

# Маршрут для логіну з токеном
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400
        
        # Хешуємо пароль
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Перевіряємо, чи є такий користувач у базі
        cursor.execute("SELECT * FROM users WHERE username = %s AND password_hash = %s", (username, hashed_password))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user:
            # Генеруємо токен для авторизації (можна замінити на JWT для більшої безпеки)
            token = base64.b64encode(f"{username}:{password}".encode()).decode('utf-8')
            return jsonify({"message": "Login successful", "token": token}), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"message": f"Error during login: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
