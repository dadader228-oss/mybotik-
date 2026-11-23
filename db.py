import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

from config import DATABASE_URL
from models import Base, Category, Setting

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create tables and seed default data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

    async with async_session() as session:
        # Seed default categories if empty
        result = await session.execute(select(Category))
        if not result.scalars().first():
            defaults = [
                Category(name="Telegram-магазины", description="Боты для продажи товаров и услуг", emoji="🛒", sort_order=1),
                Category(name="Игровые боты", description="Развлекательные и игровые боты", emoji="🎮", sort_order=2),
                Category(name="Боты для сообществ", description="Модерация, активности, уведомления", emoji="👥", sort_order=3),
                Category(name="Бизнес-боты", description="Автоматизация бизнес-процессов", emoji="💼", sort_order=4),
                Category(name="Индивидуальная разработка", description="Полностью кастомные решения", emoji="✨", sort_order=5),
            ]
            session.add_all(defaults)
            await session.commit()
            logger.info("Default categories seeded")

        # Seed default settings
        result = await session.execute(select(Setting).where(Setting.key == "referral_bonus"))
        if not result.scalars().first():
            session.add(Setting(key="referral_bonus", value="100"))
            session.add(Setting(key="referral_enabled", value="true"))
            session.add(Setting(key="shop_name", value="BOT STORE"))
            await session.commit()
            logger.info("Default settings seeded")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def backup_db(backup_path: str = "bot_store_backup.db"):
    """Simple SQLite backup via SQL."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"VACUUM INTO '{backup_path}'"))
        logger.info(f"Database backed up to {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False
