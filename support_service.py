import secrets
import string
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import SupportTicket, SupportMessage, User


def generate_ticket_number() -> str:
    return "TKT-" + "".join(secrets.choice(string.digits) for _ in range(6))


async def create_ticket(
    session: AsyncSession,
    user: User,
    text: str,
    subject: Optional[str] = None,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
) -> SupportTicket:
    number = generate_ticket_number()
    while True:
        check = await session.execute(select(SupportTicket).where(SupportTicket.ticket_number == number))
        if not check.scalar_one_or_none():
            break
        number = generate_ticket_number()

    ticket = SupportTicket(
        ticket_number=number,
        user_id=user.id,
        subject=subject or "Обращение",
        status="open",
    )
    session.add(ticket)
    await session.flush()

    msg = SupportMessage(
        ticket_id=ticket.id,
        sender_telegram_id=user.telegram_id,
        is_admin=False,
        text=text,
        media_type=media_type,
        media_file_id=media_file_id,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def add_message(
    session: AsyncSession,
    ticket: SupportTicket,
    sender_telegram_id: int,
    is_admin: bool,
    text: Optional[str] = None,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
) -> SupportMessage:
    msg = SupportMessage(
        ticket_id=ticket.id,
        sender_telegram_id=sender_telegram_id,
        is_admin=is_admin,
        text=text,
        media_type=media_type,
        media_file_id=media_file_id,
    )
    session.add(msg)
    ticket.status = "answered" if is_admin else "open"
    ticket.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(msg)
    return msg


async def get_ticket_by_number(session: AsyncSession, number: str) -> Optional[SupportTicket]:
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages), selectinload(SupportTicket.user))
        .where(SupportTicket.ticket_number == number)
    )
    return result.scalar_one_or_none()


async def get_ticket_by_id(session: AsyncSession, ticket_id: int) -> Optional[SupportTicket]:
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages), selectinload(SupportTicket.user))
        .where(SupportTicket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def get_user_tickets(session: AsyncSession, user_id: int) -> List[SupportTicket]:
    result = await session.execute(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.created_at.desc())
    )
    return list(result.scalars().all())


async def get_open_tickets(session: AsyncSession) -> List[SupportTicket]:
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.user))
        .where(SupportTicket.status.in_(["open", "answered"]))
        .order_by(SupportTicket.updated_at.desc())
    )
    return list(result.scalars().all())


async def close_ticket(session: AsyncSession, ticket: SupportTicket) -> SupportTicket:
    ticket.status = "closed"
    ticket.closed_at = datetime.utcnow()
    await session.commit()
    await session.refresh(ticket)
    return ticket
