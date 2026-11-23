import secrets
import string
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Order, Payment, Service, User


def generate_order_number() -> str:
    return "ORD-" + "".join(secrets.choice(string.digits) for _ in range(8))


async def create_order_from_service(
    session: AsyncSession,
    user: User,
    service: Service,
) -> Order:
    order_number = generate_order_number()
    while True:
        check = await session.execute(select(Order).where(Order.order_number == order_number))
        if not check.scalar_one_or_none():
            break
        order_number = generate_order_number()

    order = Order(
        order_number=order_number,
        user_id=user.id,
        service_id=service.id,
        is_custom=False,
        title=service.name,
        description=service.description,
        features=service.features,
        price_stars=service.price_stars,
        status="pending_payment",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def create_custom_order(
    session: AsyncSession,
    user: User,
    title: str,
    description: str,
    features: Optional[str] = None,
    budget: Optional[str] = None,
    desired_deadline: Optional[str] = None,
    extra_info: Optional[str] = None,
    attachments: Optional[str] = None,
) -> Order:
    order_number = generate_order_number()
    while True:
        check = await session.execute(select(Order).where(Order.order_number == order_number))
        if not check.scalar_one_or_none():
            break
        order_number = generate_order_number()

    order = Order(
        order_number=order_number,
        user_id=user.id,
        service_id=None,
        is_custom=True,
        title=title,
        description=description,
        features=features,
        budget=budget,
        desired_deadline=desired_deadline,
        extra_info=extra_info,
        attachments=attachments,
        status="pending_payment",  # Will stay until admin sets price and user accepts
        price_stars=None,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order_by_number(session: AsyncSession, order_number: str) -> Optional[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.service))
        .where(Order.order_number == order_number)
    )
    return result.scalar_one_or_none()


async def get_order_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.service))
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_user_orders(session: AsyncSession, user_id: int, limit: int = 50) -> List[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_order_status(
    session: AsyncSession,
    order: Order,
    new_status: str,
    admin_comment: Optional[str] = None,
) -> Order:
    order.status = new_status
    if admin_comment:
        order.admin_comment = admin_comment
    if new_status == "paid":
        order.paid_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(order)
    return order


async def set_custom_order_price(
    session: AsyncSession,
    order: Order,
    price_stars: int,
    deadline_days: Optional[int] = None,
) -> Order:
    order.price_stars = price_stars
    if deadline_days:
        order.desired_deadline = f"{deadline_days} дн."
    order.status = "pending_payment"
    await session.commit()
    await session.refresh(order)
    return order


STATUS_LABELS = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid": "✅ Оплачен",
    "accepted": "📋 Принят в работу",
    "in_progress": "🔧 В разработке",
    "testing": "🧪 Тестирование",
    "ready": "🎉 Готов",
    "cancelled": "❌ Отменён",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
