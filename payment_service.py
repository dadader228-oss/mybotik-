import secrets
import string
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Payment, Order
from order_service import update_order_status
from user_service import process_referral_bonus


def generate_payload() -> str:
    return "pay_" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))


async def create_payment(
    session: AsyncSession,
    order: Order,
    user_telegram_id: int,
    amount_stars: int,
) -> Payment:
    payload = generate_payload()
    payment = Payment(
        order_id=order.id,
        user_telegram_id=user_telegram_id,
        amount_stars=amount_stars,
        currency="XTR",
        status="pending",
        invoice_payload=payload,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment_by_payload(session: AsyncSession, payload: str) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.invoice_payload == payload)
    )
    return result.scalar_one_or_none()


async def get_payment_by_charge_id(session: AsyncSession, charge_id: str) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.telegram_payment_charge_id == charge_id)
    )
    return result.scalar_one_or_none()


async def process_successful_payment(
    session: AsyncSession,
    payment: Payment,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: Optional[str] = None,
) -> bool:
    """
    Process successful Stars payment.
    Returns True if processed, False if already processed (idempotent).
    """
    # Idempotency check
    if payment.status == "succeeded":
        return False

    existing = await get_payment_by_charge_id(session, telegram_payment_charge_id)
    if existing and existing.id != payment.id:
        return False

    payment.telegram_payment_charge_id = telegram_payment_charge_id
    payment.provider_payment_charge_id = provider_payment_charge_id
    payment.status = "succeeded"
    payment.succeeded_at = datetime.utcnow()

    order = await session.get(Order, payment.order_id)
    if order and order.status == "pending_payment":
        await update_order_status(session, order, "paid")
        # Process referral bonus
        if order.user:
            await process_referral_bonus(session, order.user.telegram_id)
        else:
            from user_service import get_user_by_id
            user = await get_user_by_id(session, order.user_id)
            if user:
                await process_referral_bonus(session, user.telegram_id)

    await session.commit()
    return True


async def mark_refunded(
    session: AsyncSession,
    payment: Payment,
) -> Payment:
    payment.status = "refunded"
    payment.refunded_at = datetime.utcnow()
    order = await session.get(Order, payment.order_id)
    if order:
        order.status = "cancelled"
    await session.commit()
    await session.refresh(payment)
    return payment
