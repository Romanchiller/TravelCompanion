from typing import Any, Optional, Callable, Awaitable, TypeVar, cast
from functools import wraps
import json
from urllib.parse import quote

from ..cache import cache_manager
from ..config import settings
from loguru import logger

T = TypeVar('T')

class CacheService:
    """
    Сервис для работы с кэшем.
    Предоставляет методы для кэширования данных и декораторы для кэширования результатов функций.
    """
    
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """
        Получает значение из кэша по ключу.
        
        Args:
            key: Ключ кэша
            
        Returns:
            Optional[Any]: Значение из кэша или None, если не найдено
        """
        if not settings.CACHE_ENABLED:
            return None
            
        try:
            value = await cache_manager.get(key)
            if value:
                logger.debug(f"Кэш-попадание для ключа: {key}")
            return value
        except Exception as e:
            logger.error(f"Ошибка при получении из кэша: {str(e)}")
            return None

    @staticmethod
    async def set(
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Сохраняет значение в кэш.
        
        Args:
            key: Ключ кэша
            value: Значение для сохранения
            ttl: Время жизни кэша в секундах
            
        Returns:
            bool: True если успешно, иначе False
        """
        if not settings.CACHE_ENABLED:
            return False
            
        try:
            ttl = ttl or settings.CACHE_DEFAULT_TTL
            await cache_manager.set(key, value, ttl)
            logger.debug(f"Значение сохранено в кэш. Ключ: {key}, TTL: {ttl} сек")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кэш: {str(e)}")
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        """
        Удаляет значение из кэша по ключу.
        
        Args:
            key: Ключ кэша
            
        Returns:
            bool: True если успешно, иначе False
        """
        if not settings.CACHE_ENABLED:
            return False
            
        try:
            await cache_manager.delete(key)
            logger.debug(f"Значение удалено из кэша. Ключ: {key}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении из кэша: {str(e)}")
            return False

    @staticmethod
    def cached(
        key_template: str,
        ttl: Optional[int] = None,
        exclude_params: list[str] = None
    ) -> Callable[..., Callable[..., Awaitable[T]]]:
        """
        Декоратор для кэширования результатов асинхронных функций.
        
        Args:
            key_template: Шаблон ключа кэша (может содержать имена параметров в фигурных скобках)
            ttl: Время жизни кэша в секундах
            exclude_params: Список параметров, которые не должны влиять на ключ кэша
            
        Returns:
            Декоратор функции
        """
        if exclude_params is None:
            exclude_params = []
            
        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> T:
                if not settings.CACHE_ENABLED:
                    return await func(*args, **kwargs)
                
                # Формируем ключ кэша на основе аргументов
                bound_args = {}
                if hasattr(func, '__annotations__'):
                    # Получаем имена позиционных аргументов
                    arg_names = list(func.__annotations__.keys())
                    bound_args.update(zip(arg_names, args))
                
                # Добавляем именованные аргументы
                bound_args.update({
                    k: v for k, v in kwargs.items() 
                    if k not in exclude_params and not k.startswith('_')
                })
                
                # Заменяем имена параметров в шаблоне на их значения
                cache_key = key_template.format(**{
                    k: quote(str(v)) if isinstance(v, str) else v
                    for k, v in bound_args.items()
                })
                
                # Пытаемся получить значение из кэша
                cached_value = await CacheService.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Кэш-попадание для {func.__name__} с ключом: {cache_key}")
                    return cast(T, cached_value)
                
                # Если в кэше нет, выполняем функцию
                result = await func(*args, **kwargs)
                
                # Сохраняем результат в кэш
                if result is not None:
                    await CacheService.set(cache_key, result, ttl)
                
                return cast(T, result)
                
            return wrapper
            
        return decorator
