"""
Модуль загрузки конфигурации из .env файла
Загружает API ключи, ID каналов, списки источников и промпты
"""
import os
from typing import List, Optional
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Класс для управления конфигурацией проекта"""

    def __init__(self, env_path: Optional[str] = None):
        """
        Инициализация конфигурации

        Args:
            env_path: Путь к .env файлу (если None, загружается из корня проекта)
        """
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        self._validate_config()
        logger.info("Конфигурация успешно загружена")

    def _validate_config(self):
        """Проверка наличия обязательных переменных"""
        required_vars = [
            'GEMINI_API_KEY',
            'TELEGRAM_BOT_TOKEN',
            'TARGET_CHANNEL_ID'
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
            )

    # === Gemini API ===
    @property
    def gemini_api_key(self) -> str:
        """Ключ API для Gemini"""
        return os.getenv('GEMINI_API_KEY', '')

    # === Telegram Bot ===
    @property
    def telegram_bot_token(self) -> str:
        """Токен Telegram бота"""
        return os.getenv('TELEGRAM_BOT_TOKEN', '')

    @property
    def telegram_admin_id(self) -> Optional[str]:
        """ID администратора Telegram"""
        return os.getenv('TELEGRAM_ADMIN_ID')

    @property
    def target_channel_id(self) -> str:
        """ID целевого канала для публикаций"""
        return os.getenv('TARGET_CHANNEL_ID', '')

    @property
    def channel_link(self) -> str:
        """Ссылка на канал для добавления в посты"""
        return os.getenv('CHANNEL_LINK', 'https://t.me/scov_touch')

    # === Telegram User API (для чтения каналов через Telethon) ===
    @property
    def user_api_id(self) -> Optional[str]:
        """API ID для Telethon User-bot"""
        return os.getenv('USER_API_ID')

    @property
    def user_api_hash(self) -> Optional[str]:
        """API Hash для Telethon User-bot"""
        return os.getenv('USER_API_HASH')

    @property
    def session_name(self) -> str:
        """Имя сессии для Telethon"""
        return os.getenv('SESSION_NAME', 'neuroscov_user')

    # === Источники контента ===
    @property
    def rss_feeds(self) -> List[str]:
        """Список RSS лент для парсинга"""
        feeds_str = os.getenv('RSS_FEEDS', '')
        if not feeds_str:
            return []
        return [feed.strip() for feed in feeds_str.split(',') if feed.strip()]

    @property
    def telegram_source_channels(self) -> List[str]:
        """Список Telegram каналов-источников"""
        channels_str = os.getenv('TELEGRAM_SOURCE_CHANNELS', '')
        if not channels_str:
            return []
        return [channel.strip() for channel in channels_str.split(',') if channel.strip()]

    # === Промпты для Gemini ===
    @property
    def rewrite_prompt_template(self) -> str:
        """Шаблон промпта для рерайтинга текста"""
        default_prompt = """Ты — 'нейроскуф', бородатый ироничный айтишник.
Перепиши эту новость в своем стиле для Telegram-канала.
Используй Markdown-форматирование.
Убери воду, добавь иронии, но сохрани суть.
В конце добавь релевантные #хештеги и ссылку на канал {channel_link}.

Новость:
{text}"""
        return os.getenv('REWRITE_PROMPT', default_prompt)

    @property
    def image_prompt_template(self) -> str:
        """Шаблон промпта для генерации изображений"""
        default_prompt = """Создай стильную картинку для поста в Telegram.
Стиль: 'нейроскуф', киберпанк, татуировки, брутальный IT-юмор.
Тема поста: {topic}"""
        return os.getenv('IMAGE_PROMPT', default_prompt)

    # === Настройки расписания ===
    @property
    def posts_per_day(self) -> int:
        """Количество постов в день"""
        return int(os.getenv('POSTS_PER_DAY', '3'))

    @property
    def schedule_jitter_minutes(self) -> int:
        """Случайное отклонение в расписании (в минутах)"""
        return int(os.getenv('SCHEDULE_JITTER_MINUTES', '30'))

    # === Пути к файлам ===
    @property
    def database_path(self) -> str:
        """Путь к файлу базы данных"""
        return os.getenv('DATABASE_PATH', './data/neuroscov.db')

    @property
    def log_path(self) -> str:
        """Путь к директории с логами"""
        return os.getenv('LOG_PATH', './logs')

    # === Прочие настройки ===
    @property
    def max_posts_to_fetch(self) -> int:
        """Максимальное количество постов для чтения из одного источника"""
        return int(os.getenv('MAX_POSTS_TO_FETCH', '10'))

    @property
    def gemini_model(self) -> str:
        """Модель Gemini для использования"""
        return os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')

    @property
    def gemini_image_model(self) -> str:
        """Модель Gemini для генерации изображений"""
        return os.getenv('GEMINI_IMAGE_MODEL', 'gemini-2.0-flash-exp')


# Глобальный экземпляр конфигурации
_config_instance: Optional[Config] = None


def get_config(env_path: Optional[str] = None) -> Config:
    """
    Получить глобальный экземпляр конфигурации (Singleton)

    Args:
        env_path: Путь к .env файлу (используется только при первом вызове)

    Returns:
        Config: Экземпляр конфигурации
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = Config(env_path)

    return _config_instance


if __name__ == "__main__":
    # Тестирование загрузки конфигурации
    try:
        config = get_config()
        print("✅ Конфигурация загружена успешно!")
        print(f"Канал: {config.target_channel_id}")
        print(f"RSS лент: {len(config.rss_feeds)}")
        print(f"Telegram источников: {len(config.telegram_source_channels)}")
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
