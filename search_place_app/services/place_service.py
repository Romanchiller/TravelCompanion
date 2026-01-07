import asyncio
from operator import itemgetter
from typing import Optional
from httpx import AsyncClient
from sqlalchemy.orm import selectinload, Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update, delete, func
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from loguru import logger
import traceback
import asyncio
from ..config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Place, Category, UserPlace, UserCategory, User, PlaceCategory
from ..database import SessionLocal
from sqlalchemy.future import select


class PlaceService:
    def __init__(self, db: SessionLocal, client: Any, cache: Optional[Any] = None):
        self.db = db
        self.client = client
        self.cache = cache
        self.cache_enabled = cache is not None

    async def _get_or_create_place(self, name: str, address: Optional[str], session: AsyncSession) -> Place:
        """Получает или создает место.
        
        Args:
            name: Название места
            address: Адрес места
            session: Асинхронная сессия SQLAlchemy
            
        Returns:
            Place: Существующий или созданный объект места
        """
        try:
            # Сначала пробуем найти существующее место
            query = select(Place).where(Place.name == name)
            if address:
                query = query.where(Place.address == address)
                
            result = await session.execute(query.options(selectinload(Place.categories)))
            place = result.scalar_one_or_none()

            if place is None:
                # Если место не найдено, создаем новое
                place = Place(name=name, address=address)
                session.add(place)
                await session.flush()
                # Перезагружаем место с категориями
                result = await session.execute(
                    select(Place)
                    .options(selectinload(Place.categories))
                    .where(Place.id == place.id)
                )
                place = result.scalar_one()
            
            return place
        except Exception as e:
            logger.error(f"Ошибка в _get_or_create_place: {str(e)}")
            await session.rollback()
            raise
        
    async def _get_or_create_category(self, name: str, session: AsyncSession) -> Category:
        """
        Получает или создает категорию.
        
        Args:
            name: Название категории
            session: Асинхронная сессия SQLAlchemy
            
        Returns:
            Category: Существующая или созданная категория
        """
        try:
            result = await session.execute(select(Category).where(Category.name == name))
            category = result.scalar_one_or_none()

            if category is None:
                category = Category(name=name)
                session.add(category)
                try:
                    await session.flush()
                except IntegrityError:
                    # Если возникла ошибка уникальности (категория уже создана другим запросом)
                    await session.rollback()
                    # Пытаемся снова получить категорию
                    result = await session.execute(select(Category).where(Category.name == name))
                    category = result.scalar_one()

            return category
        except Exception as e:
            logger.error(f"Ошибка в _get_or_create_category: {str(e)}")
            await session.rollback()
            raise


    async def _add_category_to_place(self, place: Place, category: Category, session: AsyncSession) -> None:
        """
        Добавляет категорию к месту, если она еще не добавлена.
        
        Args:
            place: Объект места
            category: Объект категории
            session: Асинхронная сессия SQLAlchemy
        """
        try:
            # Перезагружаем место с категориями
            result = await session.execute(
                select(Place)
                .options(selectinload(Place.categories))
                .where(Place.id == place.id)
            )
            place = result.scalar_one()
            
            if category not in place.categories:
                place.categories.append(category)
                await session.flush()
        except Exception as e:
            logger.error(f"Ошибка в _add_category_to_place: {str(e)}")
            await session.rollback()
            raise

    async def _link_user_to_category(self, user_id: int, category_id: int, session: AsyncSession) -> None:
        """Связывает пользователя с категорией.
        
        Args:
            user_id: ID пользователя
            category_id: ID категории
            session: Асинхронная сессия SQLAlchemy
        """
        if not isinstance(user_id, int):
            logger.error(f"Ожидается числовой user_id, получен {type(user_id)}: {user_id}")
            return
        if not isinstance(category_id, int):
            logger.error(f"Ожидается числовой place_id, получен {type(category_id)}: {category_id}")
            return
        try:
            result = await session.execute(
                select(UserCategory)
                .where(
                    UserCategory.user_id == user_id,
                    UserCategory.category_id == category_id
                )
            )
            user_category = result.scalar_one_or_none()

            if user_category is None:
                user_category = UserCategory(
                    user_id=user_id,
                    category_id=category_id,
                    weight=1
                )
                session.add(user_category)
            else:
                user_category.weight += 1
            
            await session.flush()
        except Exception as e:
            logger.error(f"Ошибка в _link_user_to_category: {str(e)}")
            await session.rollback()
            raise

    async def _link_user_to_place(self, user_id: int, place_id: int, session: AsyncSession) -> None:
        """Связывает пользователя с местом.
        
        Args:
            user_id: ID пользователя
            place_id: ID места
            session: Асинхронная сессия SQLAlchemy
        """
        if not isinstance(user_id, int):
            logger.error(f"Ожидается числовой user_id, получен {type(user_id)}: {user_id}")
            return
        if not isinstance(place_id, int):
            logger.error(f"Ожидается числовой place_id, получен {type(place_id)}: {place_id}")
            return
        try:
            result = await session.execute(
                select(UserPlace)
                .where(
                    UserPlace.user_id == user_id,
                    UserPlace.place_id == place_id
                )
            )
            user_place = result.scalar_one_or_none()

            if user_place is None:
                user_place = UserPlace(
                    user_id=user_id,
                    place_id=place_id,
                    weight=1
                )
                session.add(user_place)
            else:
                user_place.weight += 1
            
            await session.flush()
        except Exception as e:
            logger.error(f"Ошибка в _link_user_to_place: {str(e)}")
            await session.rollback()
            raise




    async def get_user_place_name_weights(self, user_id: int) -> dict[str, int]:
        stmt = (
            select(Place.name, func.sum(UserPlace.weight).label("w"))
            .join(UserPlace, UserPlace.place_id == Place.id)
            .where(UserPlace.user_id == user_id)
            .group_by(Place.name)
        )
        if not isinstance(user_id, int):
            logger.error(f"Ожидается числовой user_id, получен {type(user_id)}: {user_id}")
            return {}
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
        if not isinstance(user_id, int):
            logger.error(f"Ожидается числовой user_id, получен {type(user_id)}: {user_id}")
            return {}
        result = await self.db.execute(stmt)
        rows = result.all()
        return {address: int(weight_sum) for address, weight_sum in rows if address is not None}

    async def process_places(self, items: list[dict], user_id: Optional[int]) -> None:
        logger.info(f"Начало обработки {len(items)} мест. user_id={user_id}, type(user_id)={type(user_id)}")
        if not items:
            return

            # Если пользователь не аутентифицирован, просто выходим
        if user_id is None:
            logger.info("Пользователь не аутентифицирован, пропускаем обработку связей")
            return
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)
        tasks = [self._process_single(item, user_id, semaphore) for item in items]
        await asyncio.gather(*tasks)
        if user_id is not None and self.cache_enabled and self.cache:
            try:
                await self.cache.delete(f"user:{user_id}:favorites")
            except Exception as e:
                logger.error(f"Ошибка при очистке кэша: {str(e)}")


    async def _process_single(self, item: dict, user_id: Optional[int], semaphore: asyncio.Semaphore) -> None:
        logger.info(f"Обработка места. user_id={user_id}, type(user_id)={type(user_id)}")
        if user_id is not None and not isinstance(user_id, int):
            logger.error(f"Некорректный user_id: {user_id} (тип: {type(user_id)})")
            return
        async with semaphore:
            session = None
            try:
                # Создаем новую сессию
                session = SessionLocal()
                
                # Начинаем транзакцию
                await session.begin()
                
                # 1. Обрабатываем категории
                category_objs = []
                for category_dict in item.get("categories", []) or []:
                    name = category_dict.get("name")
                    if not name:
                        continue
                    # Используем асинхронный метод для работы с категориями
                    category = await self._get_or_create_category(name, session)
                    category_objs.append(category)

                # 2. Получаем адрес из данных о местоположении
                address = (item.get("location") or {}).get("formatted_address")
                
                # 3. Получаем или создаем место
                place = await self._get_or_create_place(item.get("name"), address, session)
                
                # 4. Добавляем категории к месту
                for category_obj in category_objs:
                    await self._add_category_to_place(place, category_obj, session)
                
                # 5. Если передан user_id, обрабатываем связи пользователя
                if user_id is not None:
                    try:
                        await self._link_user_to_place(user_id, place.id, session)
                        for category_obj in category_objs:
                            await self._link_user_to_category(user_id, category_obj.id, session)
                    except Exception as e:
                        logger.error(f"Ошибка при связывании пользователя: {str(e)}")
                        await session.rollback()
                        raise
                # Фиксируем изменения в базе данных
                await session.commit()
                
            except Exception as e:
                # В случае ошибки откатываем изменения
                if session is not None:
                    await session.rollback()
                logger.error(f"Ошибка при обработке места {item.get('name')}: {str(e)}")
                # Пробрасываем исключение дальше для обработки на более высоком уровне
                raise
            finally:
                # Всегда закрываем сессию
                if session is not None:
                    await session.close()

    async def _calculate_place_score(
            self,
            place: Dict,
            name_weights: Dict[str, int],
            address_weights: Dict[str, int],
            category_weights: Dict[str, int]
    ) -> float:
        """
        Вычисляет рейтинг места на основе предпочтений пользователя.

        Args:
            place: Данные о месте
            name_weights: Словарь с весами названий мест
            address_weights: Словарь с весами адресов
            category_weights: Словарь с весами категорий

        Returns:
            float: Рейтинг места
        """
        try:
            place_name = place.get('name', '')
            place_address = (place.get('location', {}).get('formatted_address', '') or
                             place.get('address', ''))
            categories = [c.get('name', '') for c in place.get('categories', [])]

            name_score = name_weights.get(place_name, 0) * 0.4
            address_score = address_weights.get(place_address, 0) * 0.3
            category_score = sum(category_weights.get(cat, 0) for cat in categories) * 0.3
            total_score = name_score + address_score + category_score

            logger.debug(f"Место: {place_name}")
            logger.debug(f"  Вес имени ({place_name}): {name_weights.get(place_name, 0)} * 0.4 = {name_score:.2f}")
            logger.debug(
                f"  Вес адреса ({place_address}): {address_weights.get(place_address, 0)} * 0.3 = {address_score:.2f}")
            logger.debug(
                f"  Вес категорий ({categories}): {sum(category_weights.get(cat, 0) for cat in categories)} * 0.3 = {category_score:.2f}")
            logger.debug(f"  Итоговый рейтинг: {total_score:.2f}")

            return total_score
        except Exception as e:
            logger.error(f"Ошибка при расчете рейтинга для места: {str(e)}")
            return 0.0

    async def sort_places_by_preferences(self, places: List[Dict], user: User) -> List[Dict]:
        """
        Сортирует места на основе предпочтений пользователя.
        """
        if not places or not user:
            return []

        try:
            if not hasattr(user, 'id') or not isinstance(user.id, int):
                logger.warning(f"Некорректный объект пользователя: {user}")
                return places

            user_id = user.id
            logger.info(f"Сортировка мест для пользователя с ID: {user_id}")

            # Получаем веса для имен и адресов мест
            try:
                name_weights = await self.get_user_place_name_weights(user.id)
                address_weights = await self.get_user_place_address_weights(user.id)
            except Exception as e:
                logger.error(f"Ошибка при получении весов: {str(e)}")
                return places

            # Получаем веса категорий пользователя
            try:
                stmt = (
                    select(Category.name, UserCategory.weight)
                    .join(UserCategory, UserCategory.category_id == Category.id)
                    .where(UserCategory.user_id == user.id)
                )
                result = await self.db.execute(stmt)
                category_weights = {name: weight for name, weight in result.all()}
            except Exception as e:
                logger.error(f"Ошибка при получении весов категорий: {str(e)}")
                category_weights = {}

            logger.info(f"Персонализация для пользователя {user.id} ({user.email}):")
            logger.info(f"Всего мест для сортировки: {len(places)}")


            # Вычисляем рейтинги для всех мест
            try:
                # Создаем список кортежей (оценка, место) для сортировки
                place_scores = []
                for place in places:
                    score = await self._calculate_place_score(
                        place, name_weights, address_weights, category_weights
                    )
                    place_scores.append((score, place))

                # Сортируем по убыванию рейтинга
                place_scores.sort(key=lambda x: x[0], reverse=True)
                sorted_places = [place for score, place in place_scores]

                # Логируем топ-5 мест с их рейтингами
                for i, (score, place) in enumerate(place_scores[:5], 1):
                    logger.info(f"{i}. {place.get('name')} (рейтинг: {score:.2f})")

                return sorted_places
            except Exception as e:
                logger.error(f"Ошибка при сортировке мест: {str(e)}")
                return places

        except Exception as e:
            logger.error(f"Критическая ошибка при сортировке мест: {str(e)}")
            logger.error(traceback.format_exc())
            return places

    async def search_place(self, search_info, min_price, max_price):
        headers = {
            'accept': 'application/json',
            'X-Places-Api-Version': settings.PLACES_API_VERSION,
            'Authorization': settings.PLACES_API_TOKEN
        }
        params = {'query': search_info}
        if min_price:
            params['min_price'] = min_price
        if max_price:
            params['max_price'] = max_price
        
        try:
            # Логируем параметры запроса
            logger.info(f"Выполняется запрос к Foursquare API с параметрами: {params}")
            
            response = await self.client.get(
                url=settings.PLACES_API_URL,
                params=params,
                headers=headers
            )

            # Логируем статус ответа
            logger.info(f"Получен ответ от Foursquare API. Статус: {response.status_code}")
            
            response.raise_for_status()  # Проверяем статус ответа
            data = response.json()
            
            # Логируем полный ответ от API (первые 500 символов)
            logger.debug(f"Ответ от Foursquare API: {str(data)[:500]}...")

            places = data.get('results', [])

            if not places:
                logger.warning(f"Не найдено мест по запросу: {search_info}")
                logger.warning(f"Полный ответ API: {data}")

            return places

        except Exception as e:
            logger.error(f"Ошибка при запросе к Places API: {str(e)}")
            logger.error(traceback.format_exc())
            return []



