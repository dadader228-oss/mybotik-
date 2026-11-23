from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Review, Order


async def create_review(
    session: AsyncSession,
    order: Order,
    user_id: int,
    rating: int,
    comment: Optional[str] = None,
) -> tuple[Optional[Review], str]:
    if rating < 1 or rating > 5:
        return None, "Оценка должна быть от 1 до 5."

    existing = await session.execute(
        select(Review).where(Review.order_id == order.id, Review.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        return None, "Вы уже оставили отзыв на этот заказ."

    if order.status != "ready":
        return None, "Отзыв можно оставить только после завершения заказа."

    review = Review(
        order_id=order.id,
        user_id=user_id,
        rating=rating,
        comment=comment,
        is_published=False,
        is_moderated=False,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review, "Спасибо за отзыв! Он будет опубликован после модерации."


async def get_published_reviews(session: AsyncSession, limit: int = 20) -> List[Review]:
    result = await session.execute(
        select(Review)
        .where(Review.is_published == True)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_pending_reviews(session: AsyncSession) -> List[Review]:
    result = await session.execute(
        select(Review)
        .where(Review.is_moderated == False)
        .order_by(Review.created_at.desc())
    )
    return list(result.scalars().all())


async def moderate_review(
    session: AsyncSession,
    review: Review,
    publish: bool,
) -> Review:
    review.is_moderated = True
    review.is_published = publish
    await session.commit()
    await session.refresh(review)
    return review
