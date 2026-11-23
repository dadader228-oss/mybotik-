from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Category, Service


async def get_categories(session: AsyncSession, active_only: bool = True) -> List[Category]:
    q = select(Category).order_by(Category.sort_order, Category.id)
    if active_only:
        q = q.where(Category.is_active == True)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_category(session: AsyncSession, category_id: int) -> Optional[Category]:
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    return result.scalar_one_or_none()


async def get_services_by_category(
    session: AsyncSession,
    category_id: int,
    available_only: bool = True,
) -> List[Service]:
    q = (
        select(Service)
        .where(Service.category_id == category_id)
        .order_by(Service.sort_order, Service.id)
    )
    if available_only:
        q = q.where(Service.is_available == True)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_service(session: AsyncSession, service_id: int) -> Optional[Service]:
    result = await session.execute(
        select(Service)
        .options(selectinload(Service.category))
        .where(Service.id == service_id)
    )
    return result.scalar_one_or_none()


async def get_all_services(session: AsyncSession, available_only: bool = False) -> List[Service]:
    q = select(Service).options(selectinload(Service.category)).order_by(Service.sort_order, Service.id)
    if available_only:
        q = q.where(Service.is_available == True)
    result = await session.execute(q)
    return list(result.scalars().all())


async def create_service(session: AsyncSession, **kwargs) -> Service:
    service = Service(**kwargs)
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service


async def update_service(session: AsyncSession, service: Service, **kwargs) -> Service:
    for k, v in kwargs.items():
        if hasattr(service, k):
            setattr(service, k, v)
    await session.commit()
    await session.refresh(service)
    return service


async def delete_service(session: AsyncSession, service: Service) -> None:
    await session.delete(service)
    await session.commit()
