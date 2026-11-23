from aiogram.fsm.state import State, StatesGroup


class CustomOrderStates(StatesGroup):
    title = State()
    description = State()
    features = State()
    budget = State()
    deadline = State()
    extra = State()
    attachments = State()
    confirm = State()


class SupportStates(StatesGroup):
    waiting_text = State()
    waiting_media = State()
    reply = State()


class PromoStates(StatesGroup):
    waiting_code = State()


class AdminStates(StatesGroup):
    # Catalog
    add_service_name = State()
    add_service_desc = State()
    add_service_price = State()
    add_service_days = State()
    add_service_features = State()
    add_service_category = State()
    add_service_photo = State()
    edit_service = State()

    # Portfolio
    add_portfolio_title = State()
    add_portfolio_desc = State()
    add_portfolio_features = State()
    add_portfolio_link = State()
    add_portfolio_photo = State()

    # Promo
    add_promo_code = State()
    add_promo_amount = State()
    add_promo_max = State()
    add_promo_expires = State()

    # Orders
    set_price = State()
    set_comment = State()
    message_user = State()
    search_order = State()

    # Broadcast
    broadcast_content = State()
    broadcast_confirm = State()

    # Users
    search_user = State()
    change_balance = State()

    # Settings
    set_referral_bonus = State()

    # Reviews
    moderate_review = State()

    # Support reply
    reply_ticket = State()
