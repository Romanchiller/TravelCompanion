from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic, Optional
from sqlalchemy.ext.asyncio import AsyncSession


class BaseService(ABC):
    """
    Базовый класс для всех сервисов приложения.
    Предоставляет общую функциональность для работы с базой данных.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def validate(self, *args, **kwargs) -> bool:
        """
        Абстрактный метод для валидации данных.
        Должен быть реализован в дочерних классах.
        """
        pass

    async def commit(self) -> None:
        """Фиксирует изменения в базе данных."""
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise

    async def refresh(self, obj: Any) -> None:
        """Обновляет состояние объекта из базы данных."""
        await self.db.refresh(obj)
