from typing import Any, Optional, Callable, Awaitable
from functools import wraps
from pymemcache.client.base import Client as MemcacheClient
from pymemcache import serde
import hashlib
from loguru import logger
from .config import settings


class CacheManager:
    def __init__(self, host: str = 'localhost', port: int = 11211, default_ttl: int = 3600):
        """
        Инициализация менеджера кэширования.
        
        :param host: Хост Memcached
        :param port: Порт Memcached
        :param default_ttl: Время жизни кэша по умолчанию в секундах
        """
        self.host = host
        self.port = port
        self.default_ttl = default_ttl
        self._client = None
    
    @property
    def client(self) -> MemcacheClient:
        """Ленивая инициализация клиента Memcached."""
        if self._client is None:
            self._client = MemcacheClient(
                (self.host, self.port),
                serializer=serde.python_memcache_serializer,
                deserializer=serde.python_memcache_deserializer
            )
        return self._client
    
    async def get(self, key: str) -> Any:
        """Получить значение из кэша."""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.warning(f"Ошибка при получении из кэша: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Установить значение в кэш."""
        try:
            return self.client.set(key, value, expire=ttl or self.default_ttl)
        except Exception as e:
            logger.warning(f"Ошибка при сохранении в кэш: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Удалить значение из кэша."""
        try:
            return self.client.delete(key) is not None
        except Exception as e:
            logger.warning(f"Ошибка при удалении из кэша: {e}")
            return False
    
    def generate_key(self, *args, **kwargs) -> str:
        """Сгенерировать ключ кэша на основе аргументов функции."""
        key_parts = [str(arg) for arg in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        key_string = ":".join(key_parts).encode('utf-8')
        return f"tc:{hashlib.md5(key_string).hexdigest()}"
    
    def cached(self, ttl: Optional[int] = None, key_prefix: str = ""):
        """
        Декоратор для кэширования результатов функций.
        
        :param ttl: Время жизни кэша в секундах
        :param key_prefix: Префикс для ключа кэша
        """
        def decorator(func: Callable[..., Awaitable[Any]]):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Исключаем self из аргументов для методов класса
                if args and hasattr(args[0], func.__name__):
                    instance = args[0]
                    cache_key = self.generate_key(
                        f"{key_prefix or func.__module__}:{func.__name__}",
                        *args[1:],
                        **kwargs
                    )
                else:
                    cache_key = self.generate_key(
                        f"{key_prefix or func.__module__}:{func.__name__}",
                        *args,
                        **kwargs
                    )
                
                # Пытаемся получить данные из кэша
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Кэш-попадание для ключа: {cache_key}")
                    return cached_result
                
                # Если в кэше нет, выполняем функцию
                result = await func(*args, **kwargs)
                
                # Сохраняем результат в кэш
                if result is not None:
                    await self.set(cache_key, result, ttl=ttl)
                
                return result
            return wrapper
        return decorator

cache_manager = CacheManager(
    host=settings.MEMCACHED_HOST,
    port=settings.MEMCACHED_PORT,
    default_ttl=settings.CACHE_DEFAULT_TTL
)