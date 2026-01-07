import asyncio
from typing import Dict, Any, Optional

from requests import session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import traceback
from loguru import logger
from httpx import AsyncClient
from ..models import Hotel, UserHotel, User
from .base_service import BaseService
from ..config import settings
from fastapi import HTTPException, status
from ..validators.country_validator import CountryValidator
from ..database import SessionLocal
from typing import List


class HotelService:
    """
    Сервис для работы с отелями.
    Обеспечивает бизнес-логику для создания, обновления и управления отелями.
    """
    def __init__(self, db: AsyncSession, client: AsyncClient):
        self.db = db
        self.client = client
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)
        self.SessionLocal = SessionLocal



    async def search_hotel(self, token: str, search_info: str, country_code: str, max_results: int):
        if token is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, )
        logger.info(f'token:{token}')
        params = {'keyword': search_info,
                  'subType': 'HOTEL_GDS',
                  }

        if country_code:
            country_code = CountryValidator.validate_country_code(country_code)
            params['countryCode'] = country_code
        if max_results:
            params['max_results'] = max_results
        async with self.semaphore:
            response = await self.client.get(url='https://test.api.amadeus.com/v1/reference-data/locations/hotel',
                                                      headers={'accept': 'application/vnd.amadeus+json',
                                                               'Authorization': 'Bearer ' + token},
                                                      params=params
                                                      )
            return response.json()
    
    async def _get_or_create_hotel(self, session: AsyncSession, name: str, address: str = "") -> Hotel:
        """
        Получает отель по имени или создает новый, если не найден.
        
        Args:
            name: Название отеля
            address: Адрес отеля (опционально)
            
        Returns:
            Hotel: Существующий или созданный отель
        """
        stmt = select(Hotel).where(Hotel.name == name)
        result = await session.execute(stmt)
        hotel = result.scalar_one_or_none()
        
        if not hotel:
            hotel = Hotel(name=name, address=address)
            session.add(hotel)
            await session.flush()
            logger.info(f"Создан новый отель: {name}")
        
        return hotel

    async def _update_user_hotel(self, session: AsyncSession, user_id: int, hotel_id: int) -> UserHotel:
        """
        Обновляет связь пользователя с отелем.
        Если связь существует, увеличивает счетчик, иначе создает новую.
        
        Args:
            user_id: ID пользователя
            hotel_id: ID отеля
            
        Returns:
            UserHotel: Обновленная или созданная связь
        """
        stmt = select(UserHotel).where(
            UserHotel.user_id == user_id,
            UserHotel.hotel_id == hotel_id
        )
        result = await session.execute(stmt)
        user_hotel = result.scalar_one_or_none()
        
        if not user_hotel:
            user_hotel = UserHotel(
                user_id=user_id,
                hotel_id=hotel_id,
                weight=1
            )
            session.add(user_hotel)
            logger.debug(f"Создана новая связь пользователя {user_id} с отелем {hotel_id}")
        else:
            user_hotel.weight += 1
            logger.debug(f"Обновлен вес связи пользователя {user_id} с отелем {hotel_id}: {user_hotel.weight}")
            
        return user_hotel

    async def process_hotel(self, hotel_data: Dict[str, Any], user: User) -> Dict[str, Any]:
        """
        Обрабатывает данные отеля и связывает его с пользователем.
        
        Args:
            hotel_data: Данные отеля
            user: Объект пользователя
            
        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            hotel_name = hotel_data.get('name', '')
            address = hotel_data.get('address', {}).get('cityName', '')
            
            async with self.db.begin():
                hotel = await self.get_or_create_hotel(hotel_name, address)
                user_hotel = await self.update_user_hotel(user.id, hotel.id)
                
                result_data = {
                    "status": "success", 
                    "hotel_id": hotel.id,
                    "weight": user_hotel.weight
                }
                
                return result_data
                
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = f"Ошибка целостности данных при обработке отеля {hotel_name}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {"status": "error", "message": error_msg, "hotel": hotel_name}
            
        except Exception as e:
            await self.db.rollback()
            error_msg = f"Неожиданная ошибка при обработке отеля {hotel_name}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            return {"status": "error", "message": "Внутренняя ошибка сервера", "hotel": hotel_name}

    async def _process_single_hotel(self, hotel_data: Dict[str, Any], user: User) -> Dict[str, Any]:
        """
        Обрабатывает один отель в отдельной сессии
        """
        session = None
        try:
            # Создаем новую сессию для каждого отеля
            session = SessionLocal()
            await session.begin()

            # Обрабатываем отель
            hotel_name = hotel_data.get('name', '')
            address = hotel_data.get('address', {}).get('cityName', '')

            # Получаем или создаем отель
            hotel = await self._get_or_create_hotel(session, hotel_name, address)

            # Связываем пользователя с отелем
            user_hotel = await self._update_user_hotel(session, user.id, hotel.id)

            await session.commit()

            return {
                "status": "success",
                "hotel_id": hotel.id,
                "weight": user_hotel.weight
            }

        except IntegrityError as e:
            if session:
                await session.rollback()
            logger.error(f"Ошибка целостности при обработке отеля {hotel_name}: {str(e)}")
            return {
                "status": "error",
                "error": "Ошибка целостности базы данных",
                "hotel": hotel_name
            }
        except Exception as e:
            if session:
                await session.rollback()
            logger.error(f"Ошибка при обработке отеля {hotel_name}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "hotel": hotel_name
            }
        finally:
            if session:
                await session.close()

    async def process_hotels_batch(self, hotels_data: List[Dict[str, Any]], user: User) -> Dict[str, Any]:
        """
        Обрабатывает пакет отелей конкурентно
        """
        if not hotels_data:
            return {"status": "success", "processed": 0, "errors": []}

        tasks = [self._process_single_hotel(hotel, user) for hotel in hotels_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = 0
        errors = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Ошибка при обработке отеля: {str(result)}")
                errors.append(str(result))
            elif result and result.get('status') == 'success':
                success_count += 1
            else:
                errors.append(result.get('error', 'Неизвестная ошибка'))

        return {
            "status": "success",
            "processed": len(hotels_data),
            "successful": success_count,
            "errors": errors
        }

    async def get_hotel_weights(self, user_id: int, hotel_ids: Dict[str, str]) -> Dict[str, int]:
        """
        Получает веса отелей для пользователя
        :param user_id: ID пользователя
        :param hotel_ids: Словарь {название_отеля: id_отеля}
        :return: Словарь {id_отеля: вес}
        """
        if not hotel_ids:
            return {}

        try:
            # Получаем ID отелей, которые есть в базе
            stmt = select(UserHotel.hotel_id, UserHotel.weight).where(
                UserHotel.user_id == user_id,
                UserHotel.hotel_id.in_(hotel_ids.values())
            )
            result = await self.db.execute(stmt)
            return {str(hotel_id): weight for hotel_id, weight in result.all()}
        except Exception as e:
            logger.error(f"Ошибка при получении весов отелей: {str(e)}")
            return {}

    async def get_hotel_ids_by_names(self, hotel_names: List[str]) -> Dict[str, int]:
        """
        Получает ID отелей по их названиям
        :param hotel_names: Список названий отелей
        :return: Словарь {название_отеля: id_отеля}
        """
        if not hotel_names:
            return {}

        try:
            stmt = select(Hotel.name, Hotel.id).where(Hotel.name.in_(hotel_names))
            result = await self.db.execute(stmt)
            return {name: str(hotel_id) for name, hotel_id in result.all()}
        except Exception as e:
            logger.error(f"Ошибка при получении ID отелей: {str(e)}")
            return {}
