import threading
import queue
import time
import psycopg2
import logging

# Налаштовуємо логування
logging.basicConfig(level=logging.INFO)

# Черга для завдань
task_queue = queue.Queue()

# Мокана функція для отримання унікальних company_id з campaigns
def get_unique_company_ids():
    # Імітуємо дані з бази, де є три company_id: aaa, bbb, ccc
    return ["aaa", "bbb", "ccc"]

# Мокана функція для збору даних
def data_collection(company_id):
    try:
        # Імітуємо затримку на до 10 секунд
        time.sleep(5)  # Затримка для тестування
        logging.info(f"Збираємо дані для компанії: {company_id}")
        
        # Моканими даними ми будемо використовувати логи
        logging.info(f"Дані для {company_id} зібрані успішно.")
        
        # Тут можна додавати код для запису в БД, поки що цього не робимо
        # conn = get_db_connection()
        # cursor = conn.cursor()
        # cursor.execute("INSERT INTO news_data (company_id, news_text) VALUES (%s, %s)", (company_id, 'Mock news'))
        # conn.commit()
        # cursor.close()
        # conn.close()

    except Exception as e:
        logging.error(f"Помилка при зборі даних для компанії {company_id}: {str(e)}")


# Функція для обробки задач з черги
def process_queue():
    while True:
        # Блокуємося, поки не буде доступне завдання в черзі
        company_id = task_queue.get()
        if company_id is None:
            break  # Завершуємо потік, якщо завдання більше нема
        
        data_collection(company_id)
        
        # Позначаємо завдання як виконане
        task_queue.task_done()


# Функція для ініціалізації таблиць
def init_tables(conn):
    try:
        # Мокана реалізація створення таблиць
        logging.info("Ініціалізація таблиць (мокано)")

        # Симулюємо затримку для створення таблиць
        time.sleep(2)

        return "Таблиці створені або вже існують."
    except Exception as e:
        return f"Помилка при створенні таблиць: {str(e)}"


# Функція для запуску збору даних
def run_data_collection():
    company_ids = get_unique_company_ids()
    
    # Створюємо потоки для обробки завдань
    threads = []
    for i in range(3):  # Наприклад, 3 потоки для обробки
        t = threading.Thread(target=process_queue)
        t.start()
        threads.append(t)

    # Додаємо задачі в чергу
    for company_id in company_ids:
        task_queue.put(company_id)

    # Очікуємо, поки всі завдання не будуть виконані
    task_queue.join()

    # Завершуємо потоки
    for _ in range(3):  # Тому що ми створили 3 потоки
        task_queue.put(None)  # Завершення для кожного потоку
    for t in threads:
        t.join()  # Чекаємо завершення кожного потоку


# Симуляція з'єднання з базою даних
def get_db_connection():
    # Імітуємо підключення до бази
    logging.info("Підключення до бази даних (мокано)")
    return None

# Головна функція
if __name__ == "__main__":
    logging.info("Ініціалізація таблиць...")
    conn = get_db_connection()
    result = init_tables(conn)
    logging.info(result)
    
    logging.info("Запуск збору даних...")
    run_data_collection()
