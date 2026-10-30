from src.application.exceptions import AdNotFoundError, ForbiddenError
from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import DeleteAdPort
from src.domain.entities import AdStatus


class DeleteAd(DeleteAdPort):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, ad_id: int, user_id: int) -> None:
        async with self._uow:
            ad = await self._uow.ads.get_by_id(ad_id)
            if ad is None or ad.status == AdStatus.ARCHIVED:
                raise AdNotFoundError
            if ad.user_id != user_id:
                raise ForbiddenError
            ad.archive()
            await self._uow.ads.save(ad)
            await self._uow.outbox.add("ad.deleted", {"ad_id": ad.id})
            await self._uow.commit()
