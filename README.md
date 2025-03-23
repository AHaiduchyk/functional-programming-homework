# 📈 Trend Alert Service

Сервіс для відстеження новинного хайпу та змін цін на акції компаній. Створено з метою виявлення зв’язків між новинами та динамікою фондового ринку — як, наприклад, після твіту Ілона Маска.

---

## 🚀 Що вміє

- Збір поточних цін на акції з Yahoo Finance
- Отримання новин по компанії
- Визначення зміни тренду (up / down / flat)
- Нотифікації користувачів по email при зміні тренду
- Кастомізація алертів (умови: всі, тільки зростання, тільки падіння)
- API для взаємодії з системою (реєстрація, логін, кампанії, алерти)
- Тестові дані через `/mock_test`

---

## ⚙️ Технології

- **Python + Flask** – API сервер
- **PostgreSQL** – основна база
- **yfinance** – дані про ціни та новини
- **smtplib** – розсилка email-повідомлень
- **Docker-ready**
- **pytest** – для базового тестування

---

## 📦 Архітектура

- `app.py` — API, автентифікація, маршрути
- `collector.py` — збір цін і новин
- `notificator.py` — перевірка зміни тренду та розсилка
- `models.py` — створення таблиць
- `tests/` — базові тести REST API

---

## 📬 Як це працює

1. Користувач створює акаунт та логіниться.
2. Створює кампанію з відстеження компанії (наприклад, `TSLA`) з обраною умовою (`all`, `up`, `down`).
3. Collector кожні 30 хвилин збирає:
   - Поточну ціну акцій
   - Новини, пов’язані з компанією
4. Якщо відбувається зміна тренду (наприклад, з `up` → `down`):
   - Notificator перевіряє відповідні алерти
   - Якщо умова співпадає — надсилає email з деталями
5. Для тесту можна використовувати `/mock_test` — вставляє фейкову новину і тренд

## 🛠️ Приклади API

### 🔐 Реєстрація

```http
POST /register
Content-Type: application/json

{
  "username": "elon",
  "password": "mars123",
  "email": "elon@x.com"
}
```

---

### 🔓 Логін

```http
POST /login
Content-Type: application/json

{
  "username": "elon",
  "password": "mars123"
}
```

---

### 📈 Створення кампанії

```http
POST /campaigns
Authorization: Basic base64(elon:mars123)
Content-Type: application/json

{
  "company_id": "TSLA",
  "alert_condition": "up"
}
```

---

### 📬 Тестова вставка (мок-дані)

```http
POST /mock_test
Content-Type: application/json

{
  "company_id": "TSLA",
  "trend": "up",
  "change_percent": 5.5,
  "email": "elon@x.com",
  "news": [
    { "text": "TSLA hits new high!", "url": "https://example.com/tsla" }
  ]
}
```

---

### 📥 Отримання алертів

```http
GET /alerts
Authorization: Basic base64(elon:mars123)
```

---

### 🔄 Зміна умови алерта

```http
PATCH /alerts/7
Authorization: Basic base64(elon:mars123)
Content-Type: application/json

{
  "alert_condition": "down"
}
```

---

## 📄 Таблиці в базі даних

- **users** – користувачі  
- **campaigns** – кампанії по компаніях  
- **alerts** – алерти, прив'язані до тікерах  
- **prices** – історія цін акцій  
- **news_data** – новини, що стосуються компаній  
- **notifications** – лог надісланих алертів  
