import secrets
import string
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Transaction, Referral
from config import DEFAULT_REFERRAL_BONUS, REFERRAL_ENABLED


def generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    referral_code: Optional[str] = None,
) -> tuple[User, bool]:
    """Get existing user or create new one. Returns (user, created)."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        # Update name/username if changed
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
            await session.commit()
        return user, False

    # Create new user
    code = generate_referral_code()
    # Ensure unique
    while True:
        check = await session.execute(select(User).where(User.referral_code == code))
        if not check.scalar_one_or_none():
            break
        code = generate_referral_code()

    referred_by = None
    if referral_code and REFERRAL_ENABLED:
        ref_result = await session.execute(
            select(User).where(User.referral_code == referral_code.upper())
        )
        referrer = ref_result.scalar_one_or_none()
        if referrer and referrer.telegram_id != telegram_id:
            referred_by = referrer.telegram_id
            # Create referral record
            session.add(Referral(
                referrer_telegram_id=referrer.telegram_id,
                referred_telegram_id=telegram_id,
                bonus_paid=False,
                bonus_amount=DEFAULT_REFERRAL_BONUS,
            ))

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        balance=0.0,
        referral_code=code,
        referred_by=referred_by,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def change_balance(
    session: AsyncSession,
    user: User,
    amount: float,
    tx_type: str,
    description: str,
    related_id: Optional[int] = None,
) -> Transaction:
    """Atomically change user balance and create transaction. Amount can be negative."""
    new_balance = user.balance + amount
    if new_balance < 0:
        raise ValueError("Insufficient bonus balance")

    user.balance = new_balance
    tx = Transaction(
        user_id=user.id,
        amount=amount,
        balance_after=new_balance,
        type=tx_type,
        description=description,
        related_id=related_id,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def get_transactions(session: AsyncSession, user_id: int, limit: int = 20):
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def process_referral_bonus(session: AsyncSession, referred_telegram_id: int):
    """Pay referral bonus on first paid order of referred user."""
    if not REFERRAL_ENABLED:
        return

    result = await session.execute(
        select(Referral).where(
            Referral.referred_telegram_id == referred_telegram_id,
            Referral.bonus_paid == False,
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        return

    referrer = await get_user_by_telegram_id(session, ref.referrer_telegram_id)
    if not referrer:
        return

    amount = ref.bonus_amount or DEFAULT_REFERRAL_BONUS
    await change_balance(
        session,
        referrer,
        amount,
        "referral",
        f"Реферальный бонус за пользователя {referred_telegram_id}",
        related_id=ref.id,
    )
    ref.bonus_paid = True
    ref.paid_at = datetime.utcnow()
    await session.commit()


async def get_referral_stats(session: AsyncSession, telegram_id: int) -> dict:
    result = await session.execute(
        select(Referral).where(Referral.referrer_telegram_id == telegram_id)
    )
    refs = result.scalars().all()
    total = len(refs)
    paid = sum(1 for r in refs if r.bonus_paid)
    total_bonus = sum(r.bonus_amount for r in refs if r.bonus_paid)
    return {
        "total": total,
        "paid": paid,
        "pending": total - paid,
        "total_bonus": total_bonus,
        "referrals": refs,
    }
