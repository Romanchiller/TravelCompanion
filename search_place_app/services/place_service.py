import asyncio
from typing import Optional
from httpx import AsyncClient
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from operator import itemgetter
from ..config import settings
from ..database import SessionLocal
from ..models import Category, Place, UserPlace, UserCategory
from sqlalchemy.exc import IntegrityError


class PlaceService:
    def __init__(self, db: AsyncSession, client: AsyncClient, cache):
        self.db = db
        self.client = client
        self.cache = cache
        self.cache_enabled = settings.CACHE_ENABLED


    async def fetch_places(self, url: str, headers: dict, query: str) -> list[dict]:
        cache_key = f"places_{query}"
        if self.cache_enabled:
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                return cached_data
        params = {"query": query}
        response = await self.client.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch places")
        data = response.json() or {}
        results = data.get("results", [])
        if self.cache_enabled and results:
            await self.cache.set(
                cache_key,
                results,
                ttl=settings.CACHE_DEFAULT_TTL
            )
        return results if isinstance(results, list) else []

    def validate_price_bounds(self, min_price: Optional[int], max_price: Optional[int]) -> None:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(status_code=400, detail="min_price must be <= max_price")

    @staticmethod
    def _get_price_value(item: dict) -> Optional[int]:
        price = item.get("price")
        if price:
            return int(price)
        return None

    @staticmethod
    def _passes_range(value: Optional[float], lo: Optional[float], hi: Optional[float]) -> bool:
        if lo is not None:
            if value is None or value < lo:
                return False
        if hi is not None:
            if value is None or value > hi:
                return False
        return True

    def filter_by_price(self, items: list[dict] | None, min_price: Optional[int], max_price: Optional[int]) -> list[dict]:
        if not isinstance(items, list):
            return []
        if min_price is None and max_price is None:
            return items
        filtered: list[dict] = []
        for item in items:
            price_value = self._get_price_value(item)
            if not self._passes_range(
                float(price_value) if price_value is not None else None,
                float(min_price) if min_price is not None else None,
                float(max_price) if max_price is not None else None,
            ):
                continue
            filtered.append(item)
        return filtered

    async def get_user_category_weights(self, user_id: int) -> dict[str, int]:
        stmt = (
            select(Category.name, func.sum(UserCategory.weight).label("w"))
            .join(UserCategory, UserCategory.category_id == Category.id)
            .where(UserCategory.user_id == user_id)
            .group_by(Category.name)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return {name: int(weight_sum) for name, weight_sum in rows}

    async def get_user_place_name_weights(self, user_id: int) -> dict[str, int]:
        stmt = (
            select(Place.name, func.sum(UserPlace.weight).label("w"))
            .join(UserPlace, UserPlace.place_id == Place.id)
            .where(UserPlace.user_id == user_id)
            .group_by(Place.name)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return {name: int(weight_sum) for name, weight_sum in rows}

    async def get_user_place_address_weights(self, user_id: int) -> dict[str, int]:
        stmt = (
            select(Place.address, func.sum(UserPlace.weight).label("w"))
            .join(UserPlace, UserPlace.place_id == Place.id)
            .where(UserPlace.user_id == user_id)
            .group_by(Place.address)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        return {address: int(weight_sum) for address, weight_sum in rows if address is not None}

    @staticmethod
    def _compute_place_score(
        item: dict,
        weights_by_category: dict[str, int],
        weights_by_place_name: Optional[dict[str, int]] = None,
        weights_by_place_address: Optional[dict[str, int]] = None,
    ) -> int:
        total = 0
        for category_dict in item.get("categories", []) or []:
            name = category_dict.get("name")
            if not name:
                continue
            total += int(weights_by_category.get(name, 0))
        if weights_by_place_name:
            place_name = item.get("name")
            if place_name:
                total += int(weights_by_place_name.get(place_name, 0))
        if weights_by_place_address:
            address = (item.get("location") or {}).get("formatted_address")
            if address:
                total += int(weights_by_place_address.get(address, 0))
        return total

    def score_places(
        self,
        items: list[dict],
        weights_by_category: dict[str, int],
        weights_by_place_name: Optional[dict[str, int]] = None,
        weights_by_place_address: Optional[dict[str, int]] = None,
    ) -> list[dict]:
        scored = [
            (
                self._compute_place_score(
                    item,
                    weights_by_category,
                    weights_by_place_name,
                    weights_by_place_address,
                ),
                item,
            )
            for item in items
        ]
        scored.sort(key=itemgetter(0), reverse=True)
        return [item for _, item in scored]

    async def _get_or_create_category(self, name: str, session: AsyncSession) -> Category:
        result = await session.execute(select(Category).where(Category.name == name))
        category_obj = result.scalar_one_or_none()
        if category_obj:
            return category_obj
        category_obj = Category(name=name)
        session.add(category_obj)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(select(Category).where(Category.name == name))
            category_obj = result.scalar_one()
        return category_obj

    async def _get_or_create_place(self, name: str, address: Optional[str], session: AsyncSession) -> Place:
        stmt = select(Place).where(Place.name == name, Place.address == address)
        result = await session.execute(stmt)
        place_obj = result.scalar_one_or_none()
        if place_obj:
            return place_obj
        place_obj = Place(name=name, address=address)
        session.add(place_obj)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(stmt)
            place_obj = result.scalar_one()
        return place_obj

    async def process_places(self, items: list[dict], user_id: Optional[int]) -> None:
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_PLACES)
        tasks = [self._process_single(item, user_id, semaphore) for item in items]
        await asyncio.gather(*tasks)
        if user_id and self.cache_enabled:
            await self.cache.delete(f"user:{user_id}:favorites")


    async def _process_single(self, item: dict, user_id: Optional[int], semaphore: asyncio.Semaphore) -> None:
        async with semaphore:
            async with SessionLocal() as session:
                category_objs: list[Category] = []
                for category_dict in item.get("categories", []) or []:
                    name = category_dict.get("name")
                    if not name:
                        continue
                    category = await self._get_or_create_category(name, session)
                    category_objs.append(category)
                address = (item.get("location") or {}).get("formatted_address")
                place = await self._get_or_create_place(item.get("name"), address, session)
                for category_obj in category_objs:
                    if category_obj not in place.categories:
                        place.categories.append(category_obj)
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()

                if user_id is not None:
                    result_user_place = await session.execute(
                        select(UserPlace).where(
                            UserPlace.user_id == user_id, UserPlace.place_id == place.id
                        )
                    )
                    user_place_record: UserPlace | None = result_user_place.scalar_one_or_none()
                    if user_place_record is None:
                        user_place_record = UserPlace(user_id=user_id, place_id=place.id, weight=1)
                        session.add(user_place_record)
                    else:
                        user_place_record.weight = int(user_place_record.weight) + 1
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()

                    for category_obj in category_objs:
                        result_user_category = await session.execute(
                            select(UserCategory).where(
                                UserCategory.user_id == user_id,
                                UserCategory.category_id == category_obj.id,
                            )
                        )
                        user_category_record: UserCategory | None = result_user_category.scalar_one_or_none()
                        if user_category_record is None:
                            user_category_record = UserCategory(user_id=user_id, category_id=category_obj.id, weight=1)
                            session.add(user_category_record)
                        else:
                            user_category_record.weight = int(user_category_record.weight) + 1
                        try:
                            await session.commit()
                        except IntegrityError:
                            await session.rollback()
