from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import PromoCode, PromoActivation, User
from user_service import change_balance


async def get_promo_by_code(session: AsyncSession, code: str) -> Optional[PromoCode]:
    result = await session.execute(
        select(PromoCode).where(PromoCode.code == code.upper())
    )
    return result.scalar_one_or_none()


async def activate_promo(
    session: AsyncSession,
    user: User,
    code: str,
) -> tuple[bool, str]:
    promo = await get_promo_by_code(session, code)
    if not promo:
        return False, "Промокод не найден."

    if not promo.is_active:
        return False, "Промокод отключён."

    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return False, "Срок действия промокода истёк."

    if promo.current_activations >= promo.max_activations:
        return False, "Лимит активаций промокода исчерпан."

    # Check per-user limit
    count_result = await session.execute(
        select(func.count(PromoActivation.id)).where(
            PromoActivation.promo_id == promo.id,
            PromoActivation.user_telegram_id == user.telegram_id,
        )
    )
    user_activations = count_result.scalar() or 0
    if user_activations >= promo.max_per_user:
        return False, "Вы уже активировали этот промокод."

    # Activate
    activation = PromoActivation(
        promo_id=promo.id,
        user_telegram_id=user.telegram_id,
    )
    session.add(activation)
    promo.current_activations += 1

    await change_balance(
        session,
        user,
        promo.bonus_amount,
        "promo",
        f"Бонус по промокоду {promo.code}",
        related_id=promo.id,
    )
    await session.commit()
    return True, f"Промокод активирован! Начислено {promo.bonus_amount:.0f} ₽ бонусов."


async def create_promo(session: AsyncSession, **kwargs) -> PromoCode:
    if "code" in kwargs:
        kwargs["code"] = kwargs["code"].upper()
    promo = PromoCode(**kwargs)
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return promo


async def get_all_promos(session: AsyncSession) -> list:
    result = await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
    return list(result.scalars().all())
