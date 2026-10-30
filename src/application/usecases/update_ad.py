from src.application.exceptions import AdNotFoundError, ForbiddenError
from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import UpdateAdPort
from src.domain.entities import Ad, AdStatus


class UpdateAd(UpdateAdPort):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        ad_id: int,
        user_id: int,
        title: str | None,
        description: str | None,
        price: int | None,
        category: str | None,
        city: str | None,
    ) -> Ad:
        async with self._uow:
            ad = await self._uow.ads.get_by_id(ad_id)
            if ad is None or ad.status == AdStatus.ARCHIVED:
                raise AdNotFoundError
            if ad.user_id != user_id:
                raise ForbiddenError
            ad.edit(
                title=title if title is not None else ad.title,
                description=description if description is not None else ad.description,
                price=price if price is not None else ad.price,
                category=category if category is not None else ad.category,
                city=city if city is not None else ad.city,
            )
            await self._uow.ads.save(ad)
            await self._uow.outbox.add("ad.updated", {"ad_id": ad.id})
            await self._uow.commit()
        return ad
