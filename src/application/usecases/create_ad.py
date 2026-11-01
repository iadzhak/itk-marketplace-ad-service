import logging

from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import CreateAdPort
from src.domain.entities import Ad

logger = logging.getLogger(__name__)


class CreateAd(CreateAdPort):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        user_id: int,
        title: str,
        description: str,
        price: int,
        category: str,
        city: str,
    ) -> Ad:
        async with self._uow:
            ad = await self._uow.ads.create(
                user_id=user_id,
                title=title,
                description=description,
                price=price,
                category=category,
                city=city,
            )
            await self._uow.outbox.add("ad.created", {"ad_id": ad.id})
            await self._uow.commit()
        logger.info("ad created: ad_id=%s user_id=%s", ad.id, user_id)
        return ad
