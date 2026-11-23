from aiogram import Router

from start import router as start_router
from catalog import router as catalog_router
from orders import router as orders_router
from balance import router as balance_router
from custom_order import router as custom_order_router
from support import router as support_router
from portfolio import router as portfolio_router
from admin import router as admin_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(start_router)
    root.include_router(catalog_router)
    root.include_router(orders_router)
    root.include_router(balance_router)
    root.include_router(custom_order_router)
    root.include_router(support_router)
    root.include_router(portfolio_router)
    root.include_router(admin_router)
    return root
