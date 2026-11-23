from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Order, Payment, Referral, SupportTicket, Review, Service


async def get_stats(session: AsyncSession, period: str = "all") -> dict:
    now = datetime.utcnow()
    if period == "day":
        since = now - timedelta(days=1)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    def apply_period(q, col):
        if since:
            return q.where(col >= since)
        return q

    # Users
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    new_users_q = select(func.count(User.id))
    if since:
        new_users_q = new_users_q.where(User.created_at >= since)
    new_users = (await session.execute(new_users_q)).scalar() or 0

    # Orders
    total_orders = (await session.execute(select(func.count(Order.id)))).scalar() or 0
    paid_orders_q = select(func.count(Order.id)).where(Order.status.in_(["paid", "accepted", "in_progress", "testing", "ready"]))
    if since:
        paid_orders_q = paid_orders_q.where(Order.paid_at >= since)
    paid_orders = (await session.execute(paid_orders_q)).scalar() or 0

    completed_q = select(func.count(Order.id)).where(Order.status == "ready")
    if since:
        completed_q = completed_q.where(Order.updated_at >= since)
    completed = (await session.execute(completed_q)).scalar() or 0

    active_q = select(func.count(Order.id)).where(
        Order.status.in_(["paid", "accepted", "in_progress", "testing"])
    )
    active_orders = (await session.execute(active_q)).scalar() or 0

    # Revenue in Stars
    revenue_q = select(func.coalesce(func.sum(Payment.amount_stars), 0)).where(Payment.status == "succeeded")
    if since:
        revenue_q = revenue_q.where(Payment.succeeded_at >= since)
    revenue = (await session.execute(revenue_q)).scalar() or 0

    avg_check = revenue / paid_orders if paid_orders else 0

    # Referrals
    total_refs = (await session.execute(select(func.count(Referral.id)))).scalar() or 0

    # Tickets
    tickets_q = select(func.count(SupportTicket.id))
    if since:
        tickets_q = tickets_q.where(SupportTicket.created_at >= since)
    tickets = (await session.execute(tickets_q)).scalar() or 0

    # Popular services
    popular = await session.execute(
        select(Service.name, func.count(Order.id).label("cnt"))
        .join(Order, Order.service_id == Service.id, isouter=True)
        .group_by(Service.id)
        .order_by(func.count(Order.id).desc())
        .limit(5)
    )
    popular_services = [(row[0], row[1]) for row in popular.all()]

    return {
        "total_users": total_users,
        "new_users": new_users,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "completed_orders": completed,
        "active_orders": active_orders,
        "revenue_stars": revenue,
        "avg_check": avg_check,
        "total_referrals": total_refs,
        "tickets": tickets,
        "popular_services": popular_services,
        "period": period,
    }
