from typing import Dict, Any, List, Optional, Callable, Awaitable, TypeVar, cast
from functools import wraps
from fastapi import Request, Response
from loguru import logger

T = TypeVar('T')

class RequestLogger:
    """
    Утилита для логирования HTTP-запросов и ответов.
    Поддерживает как синхронные, так и асинхронные эндпоинты.
    """
    
    @staticmethod
    def log_request_data(
        request_data: Dict[str, Any], 
        exclude_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Логирует данные запроса, исключая конфиденциальные поля.
        
        Args:
            request_data: Словарь с данными запроса
            exclude_fields: Список полей, которые нужно исключить из лога
            
        Returns:
            Dict[str, Any]: Отфильтрованные данные запроса для логирования
        """
        if exclude_fields is None:
            exclude_fields = ['password', 'token', 'access_token', 'refresh_token', 'authorization']
        
        log_data = {
            k: '***HIDDEN***' if k.lower() in [f.lower() for f in exclude_fields] else v 
            for k, v in request_data.items()
        }
        
        logger.debug(f"Данные запроса: {log_data}")
        return log_data

    @classmethod
    def log_request(cls, exclude_params: Optional[List[str]] = None):
        """
        Декоратор для логирования входящих запросов и ответов.
        
        Args:
            exclude_params: Список параметров, которые не нужно логировать
            
        Returns:
            Декоратор функции
        """
        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs) -> T:
                # Логируем входящий запрос
                request_data = {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "query_params": dict(request.query_params),
                }
                
                # Логируем тело запроса, если оно есть
                if request.method in ["POST", "PUT", "PATCH"]:
                    try:
                        body = await request.json()
                        request_data["body"] = body
                    except Exception as e:
                        logger.debug(f"Не удалось прочитать тело запроса: {str(e)}")
                
                # Логируем запрос, исключая конфиденциальные данные
                cls.log_request_data(request_data, exclude_params)
                
                # Вызываем обработчик
                response = await func(request, *args, **kwargs)
                
                # Логируем ответ
                if hasattr(response, 'body'):
                    try:
                        response_data = {
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                        }
                        
                        # Пытаемся распарсить JSON-ответ
                        try:
                            import json
                            response_body = json.loads(response.body.decode())
                            response_data["body"] = response_body
                        except:
                            response_data["body"] = "[binary or non-json data]"
                            
                        logger.debug(f"Ответ: {response_data}")
                    except Exception as e:
                        logger.error(f"Ошибка при логировании ответа: {str(e)}")
                
                return response
                
            return wrapper
            
        return decorator

    @classmethod
    def log_http_errors(cls):
        """
        Декоратор для перехвата и логирования HTTP-исключений.
        
        Returns:
            Декоратор функции
        """
        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> T:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"Ошибка при обработке запроса: {str(e)}\n"
                        f"Тип ошибки: {type(e).__name__}\n"
                        f"Аргументы: {args}, {kwargs}\n"
                        f"Трассировка: {e.__traceback__}"
                    )
                    raise
                    
            return wrapper
            
        return decorator
