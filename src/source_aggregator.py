"""
Модуль для сбора контента из различных источников
Поддерживает RSS ленты и Telegram каналы
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import feedparser
from telethon import TelegramClient
from telethon.tl.types import Message

from config_loader import Config

logger = logging.getLogger(__name__)


class SourcePost:
    """Класс для представления поста из любого источника"""

    def __init__(
        self,
        title: str,
        content: str,
        url: Optional[str] = None,
        source_type: str = "unknown",
        source_name: str = "",
        published_at: Optional[datetime] = None,
        media_url: Optional[str] = None
    ):
        self.title = title
        self.content = content
        self.url = url
        self.source_type = source_type
        self.source_name = source_name
        self.published_at = published_at or datetime.now()
        self.media_url = media_url

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'source_type': self.source_type,
            'source_name': self.source_name,
            'published_at': self.published_at.isoformat(),
            'media_url': self.media_url
        }

    def __repr__(self):
        return f"<SourcePost: {self.title[:50]}... from {self.source_type}/{self.source_name}>"


class SourceAggregator:
    """Класс для сбора контента из всех источников"""

    def __init__(self, config: Config):
        """
        Инициализация агрегатора

        Args:
            config: Объект конфигурации
        """
        self.config = config
        self.telegram_client: Optional[TelegramClient] = None

    async def _init_telegram_client(self):
        """Инициализация Telegram клиента (Telethon)"""
        if not self.config.user_api_id or not self.config.user_api_hash:
            logger.warning("Telegram User API credentials не настроены")
            return

        try:
            self.telegram_client = TelegramClient(
                self.config.session_name,
                int(self.config.user_api_id),
                self.config.user_api_hash
            )
            await self.telegram_client.start()
            logger.info("Telegram клиент успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Telegram клиента: {e}")
            self.telegram_client = None

    def fetch_rss_news(self) -> List[SourcePost]:
        """
        Парсинг RSS лент

        Returns:
            List[SourcePost]: Список постов из RSS
        """
        posts = []
        rss_feeds = self.config.rss_feeds

        if not rss_feeds:
            logger.info("RSS ленты не настроены")
            return posts

        logger.info(f"Парсинг {len(rss_feeds)} RSS лент...")

        for feed_url in rss_feeds:
            try:
                logger.info(f"Парсинг RSS: {feed_url}")
                feed = feedparser.parse(feed_url)

                if feed.bozo:
                    logger.warning(f"Проблемы с парсингом RSS {feed_url}: {feed.bozo_exception}")
                    continue

                feed_title = feed.feed.get('title', 'Unknown Feed')

                # Берем только N последних постов согласно конфигурации
                entries = feed.entries[:self.config.max_posts_to_fetch]

                for entry in entries:
                    # Извлекаем данные
                    title = entry.get('title', 'No Title')
                    content = entry.get('summary', entry.get('description', ''))
                    link = entry.get('link', '')

                    # Парсим дату публикации
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_at = datetime(*entry.published_parsed[:6])
                        except Exception:
                            pass

                    # Создаем объект поста
                    post = SourcePost(
                        title=title,
                        content=content,
                        url=link,
                        source_type='rss',
                        source_name=feed_title,
                        published_at=published_at
                    )

                    posts.append(post)

                logger.info(f"Получено {len(entries)} постов из {feed_title}")

            except Exception as e:
                logger.error(f"Ошибка парсинга RSS {feed_url}: {e}")
                continue

        logger.info(f"Всего получено {len(posts)} постов из RSS лент")
        return posts

    async def fetch_telegram_news(self) -> List[SourcePost]:
        """
        Чтение постов из Telegram каналов

        Returns:
            List[SourcePost]: Список постов из Telegram
        """
        posts = []
        channels = self.config.telegram_source_channels

        if not channels:
            logger.info("Telegram каналы-источники не настроены")
            return posts

        # Инициализируем клиент, если еще не инициализирован
        if not self.telegram_client:
            await self._init_telegram_client()

        if not self.telegram_client:
            logger.error("Не удалось инициализировать Telegram клиент")
            return posts

        logger.info(f"Чтение {len(channels)} Telegram каналов...")

        for channel in channels:
            try:
                logger.info(f"Чтение канала: {channel}")

                # Получаем последние N сообщений из канала
                messages = await self.telegram_client.get_messages(
                    channel,
                    limit=self.config.max_posts_to_fetch
                )

                for msg in messages:
                    if not isinstance(msg, Message):
                        continue

                    # Пропускаем сообщения без текста
                    if not msg.message:
                        continue

                    # Создаем URL сообщения
                    msg_url = f"https://t.me/{channel.replace('@', '')}/{msg.id}"

                    # Проверяем наличие медиа
                    media_url = None
                    if msg.photo:
                        # Для фото можно попробовать сохранить или получить URL
                        # Пока просто отмечаем наличие
                        media_url = "photo_present"
                    elif msg.video:
                        media_url = "video_present"

                    # Создаем объект поста
                    post = SourcePost(
                        title=msg.message[:100] + "..." if len(msg.message) > 100 else msg.message,
                        content=msg.message,
                        url=msg_url,
                        source_type='telegram',
                        source_name=channel,
                        published_at=msg.date,
                        media_url=media_url
                    )

                    posts.append(post)

                logger.info(f"Получено {len(messages)} постов из {channel}")

            except Exception as e:
                logger.error(f"Ошибка чтения Telegram канала {channel}: {e}")
                continue

        logger.info(f"Всего получено {len(posts)} постов из Telegram каналов")
        return posts

    async def fetch_all_sources(self) -> List[SourcePost]:
        """
        Сбор постов из всех источников (RSS + Telegram)

        Returns:
            List[SourcePost]: Объединенный список постов
        """
        logger.info("Начало сбора контента из всех источников...")

        # Собираем из RSS синхронно
        rss_posts = self.fetch_rss_news()

        # Собираем из Telegram асинхронно
        telegram_posts = await self.fetch_telegram_news()

        # Объединяем
        all_posts = rss_posts + telegram_posts

        logger.info(f"Всего собрано {len(all_posts)} постов (RSS: {len(rss_posts)}, Telegram: {len(telegram_posts)})")

        # Сортируем по дате публикации (новые сначала)
        all_posts.sort(key=lambda x: x.published_at, reverse=True)

        return all_posts

    async def close(self):
        """Закрытие соединений"""
        if self.telegram_client:
            await self.telegram_client.disconnect()
            logger.info("Telegram клиент отключен")


async def main():
    """Тестирование модуля"""
    from config_loader import get_config

    try:
        config = get_config()
        aggregator = SourceAggregator(config)

        # Тестируем сбор из всех источников
        posts = await aggregator.fetch_all_sources()

        print(f"\n✅ Собрано {len(posts)} постов:")
        for i, post in enumerate(posts[:5], 1):  # Показываем первые 5
            print(f"\n{i}. {post.title}")
            print(f"   Источник: {post.source_type}/{post.source_name}")
            print(f"   Дата: {post.published_at}")
            print(f"   URL: {post.url}")

        await aggregator.close()

    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
