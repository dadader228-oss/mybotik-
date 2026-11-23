from typing import Optional, List
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PortfolioItem


async def get_portfolio(session: AsyncSession, active_only: bool = True) -> List[PortfolioItem]:
    q = select(PortfolioItem).order_by(PortfolioItem.sort_order, PortfolioItem.id)
    if active_only:
        q = q.where(PortfolioItem.is_active == True)
    result = await session.execute(q)
    return list(result.scalars().all())


async def get_portfolio_item(session: AsyncSession, item_id: int) -> Optional[PortfolioItem]:
    result = await session.execute(select(PortfolioItem).where(PortfolioItem.id == item_id))
    return result.scalar_one_or_none()


async def create_portfolio_item(session: AsyncSession, **kwargs) -> PortfolioItem:
    item = PortfolioItem(**kwargs)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_portfolio_item(session: AsyncSession, item: PortfolioItem, **kwargs) -> PortfolioItem:
    for k, v in kwargs.items():
        if hasattr(item, k):
            setattr(item, k, v)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_portfolio_item(session: AsyncSession, item: PortfolioItem) -> None:
    await session.delete(item)
    await session.commit()


def parse_photos(photo_file_ids: Optional[str]) -> List[str]:
    if not photo_file_ids:
        return []
    try:
        return json.loads(photo_file_ids)
    except Exception:
        return [photo_file_ids] if photo_file_ids else []
