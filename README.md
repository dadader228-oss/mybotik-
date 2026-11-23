# BOT STORE — Telegram-бот магазин разработки ботов

Полноценный Telegram-бот для продажи услуг по созданию Telegram-ботов на заказ.

Оплата **только через Telegram Stars (XTR)**. Бонусный баланс — информационный.

## Возможности

- Каталог услуг с категориями (управление из админ-панели)
- Индивидуальные заказы (пошаговая форма + вложения)
- Оплата Telegram Stars (счета, pre_checkout, successful_payment, refund)
- Внутренний бонусный баланс + история транзакций
- Реферальная система
- Промокоды (начисление бонусов)
- Портфолио
- Отзывы с модерацией
- Система поддержки (тикеты, медиа)
- Админ-панель полностью внутри Telegram
- Статистика, рассылка, управление заказами/статусами
- SQLite, aiogram 3, без Docker/Redis/PostgreSQL

## Требования

- Python 3.11+
- Windows / Linux / macOS

## Установка

1. Распакуйте архив.
2. Скопируйте `.env.example` → `.env`.
3. Заполните:
   - `BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
   - `ADMIN_IDS` — ваш Telegram ID (можно узнать у [@userinfobot](https://t.me/userinfobot))
4. Установите зависимости и запустите:

```bash
pip install -r requirements.txt
python main.py
```

Или на Windows дважды щёлкните `start.bat`.

## Получение токена бота

1. Откройте [@BotFather](https://t.me/BotFather)
2. `/newbot` → укажите имя и username
3. Скопируйте выданный токен в `.env` как `BOT_TOKEN=...`
4. Рекомендуется включить платежи Stars: в BotFather → Bot Settings → Payments (если доступно)

## Настройка администратора

В `.env`:

```
ADMIN_IDS=123456789
```

Можно несколько через запятую. Только эти ID имеют доступ к `/admin` и кнопке «Админ-панель».

## Запуск

```bash
python main.py
```

Бот работает в режиме long polling. База `bot_store.db` создаётся автоматически.

## Команды

| Команда       | Описание                          |
|---------------|-----------------------------------|
| /start        | Запуск / регистрация              |
| /admin        | Админ-панель                      |
| /profile      | Профиль                           |
| /orders       | Мои заказы                        |
| /support      | Поддержка                         |
| /paysupport   | Вопросы по оплате и возвратам     |
| /terms        | Условия                           |
| /cancel       | Отмена текущего действия          |

## Структура проекта (все .py в корне)

```
BOT_STORE/
├── main.py              # точка входа
├── config.py
├── models.py            # SQLAlchemy модели
├── db.py                # подключение и init БД
├── routers.py           # сборка роутеров
├── states.py            # FSM состояния
├── helpers.py
├── main_kb.py / catalog_kb.py / admin_kb.py
├── *_service.py         # бизнес-логика
├── start.py / catalog.py / orders.py / ...  # хендлеры
├── requirements.txt
├── .env.example
├── start.bat
└── README.md
```
BOT_STORE/
├── main.py
├── config.py
├── requirements.txt
├── .env.example
├── start.bat
├── README.md
├── database/
│   ├── models.py
│   └── db.py
├── handlers/
│   ├── start.py
│   ├── catalog.py
│   ├── orders.py
│   ├── balance.py
│   ├── custom_order.py
│   ├── support.py
│   ├── portfolio.py
│   └── admin.py
├── keyboards/
├── services/
├── utils/
└── media/
```

## Важно

- Все цифровые услуги продаются **только за Stars**.
- Бонусный баланс нельзя использовать для оплаты.
- Возврат Stars: через админ-панель (кнопка возврата) → `refundStarPayment`.
- Для теста платежей Stars используйте тестовую среду Telegram / реальные Stars в небольших суммах.

## Лицензия

Проект предоставляется «как есть» для использования владельцем бота.
