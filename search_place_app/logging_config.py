
import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any
from loguru import logger


class InterceptHandler(logging.Handler):
    """Перехватчик логов стандартной библиотеки logging."""
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:

    logger.remove()

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    dev_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    prod_format = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"

    if os.getenv("ENV_TYPE", "dev") == "dev":
        logger.add(
            sys.stderr,
            level="DEBUG",
            format=dev_format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
        logger.info("Режим разработки: логирование настроено для вывода в консоль")
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format=prod_format,
            colorize=False,
            backtrace=True,
            diagnose=False,
        )
        
        logger.add(
            log_dir / "app.log",
            rotation="10 MB",
            retention="30 days",
            level="DEBUG",
            format=prod_format,
            compression="zip",
            backtrace=True,
            diagnose=False,
        )
        logger.info("Режим продакшена: логирование настроено в файл и консоль")

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for logger_name in ["uvicorn", "uvicorn.error", "fastapi"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    logger.info("Логирование успешно настроено")
