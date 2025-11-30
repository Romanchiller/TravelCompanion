"""
Пакет для работы с внедрением зависимостей.
Содержит контейнер зависимостей и утилиты для их настройки.
"""

import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent))

from search_place_app.di.container import Container, get_container, override_providers

# Экспортируем только необходимые сущности
__all__ = [
    'Container',
    'get_container',
    'override_providers',
]
