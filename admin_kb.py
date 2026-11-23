from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
        InlineKeyboardButton(text="📦 Заказы", callback_data="admin:orders"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
        InlineKeyboardButton(text="🛒 Каталог", callback_data="admin:catalog"),
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Портфолио", callback_data="admin:portfolio"),
        InlineKeyboardButton(text="🆘 Обращения", callback_data="admin:tickets"),
    )
    builder.row(
        InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:promos"),
        InlineKeyboardButton(text="👥 Рефералы", callback_data="admin:referrals"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Отзывы", callback_data="admin:reviews"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def stats_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="День", callback_data="admin:stats:day"),
        InlineKeyboardButton(text="Неделя", callback_data="admin:stats:week"),
        InlineKeyboardButton(text="Месяц", callback_data="admin:stats:month"),
    )
    builder.row(
        InlineKeyboardButton(text="Всё время", callback_data="admin:stats:all"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()


def order_status_kb(order_number: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    statuses = [
        ("paid", "✅ Оплачен"),
        ("accepted", "📋 Принят"),
        ("in_progress", "🔧 В работе"),
        ("testing", "🧪 Тест"),
        ("ready", "🎉 Готов"),
        ("cancelled", "❌ Отмена"),
    ]
    for status, label in statuses:
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"admin:set_status:{order_number}:{status}")
        )
    builder.row(InlineKeyboardButton(text="💬 Написать клиенту", callback_data=f"admin:msg_user:{order_number}"))
    builder.row(InlineKeyboardButton(text="💰 Назначить цену", callback_data=f"admin:set_price:{order_number}"))
    builder.row(InlineKeyboardButton(text="↩️ Возврат Stars", callback_data=f"admin:refund:{order_number}"))
    builder.row(InlineKeyboardButton(text="◀️ К заказам", callback_data="admin:orders"))
    return builder.as_markup()


def confirm_broadcast_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="admin:broadcast_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"),
    )
    return builder.as_markup()
