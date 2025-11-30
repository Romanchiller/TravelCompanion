from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import traceback
from loguru import logger

from ..models import Hotel, UserHotel, User
from .base_service import BaseService

class HotelService(BaseService):
    """
    Сервис для работы с отелями.
    Обеспечивает бизнес-логику для создания, обновления и управления отелями.
    """
    
    async def get_or_create_hotel(self, name: str, address: str = "") -> Hotel:
        """
        Получает отель по имени или создает новый, если не найден.
        
        Args:
            name: Название отеля
            address: Адрес отеля (опционально)
            
        Returns:
            Hotel: Существующий или созданный отель
        """
        stmt = select(Hotel).where(Hotel.name == name)
        result = await self.db.execute(stmt)
        hotel = result.scalar_one_or_none()
        
        if not hotel:
            hotel = Hotel(name=name, address=address)
            self.db.add(hotel)
            await self.db.flush()
            logger.info(f"Создан новый отель: {name}")
        
        return hotel

    async def update_user_hotel(self, user_id: int, hotel_id: int) -> UserHotel:
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
        result = await self.db.execute(stmt)
        user_hotel = result.scalar_one_or_none()
        
        if not user_hotel:
            user_hotel = UserHotel(
                user_id=user_id,
                hotel_id=hotel_id,
                weight=1
            )
            self.db.add(user_hotel)
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
