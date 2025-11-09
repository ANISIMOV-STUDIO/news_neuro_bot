"""
Модуль для публикации постов в Telegram канал
Использует Telegram Bot API
"""
import logging
import asyncio
from typing import Optional
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
import re

from config_loader import Config

logger = logging.getLogger(__name__)


class TelegramPoster:
    """Класс для публикации постов в Telegram канал"""

    def __init__(self, config: Config):
        """
        Инициализация постера

        Args:
            config: Объект конфигурации
        """
        self.config = config
        self.bot = Bot(token=config.telegram_bot_token)
        logger.info("Telegram Bot инициализирован")

    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """
        Экранирование специальных символов для MarkdownV2

        Args:
            text: Исходный текст

        Returns:
            str: Экранированный текст
        """
        # Символы, которые нужно экранировать в MarkdownV2
        special_chars = r'_*[]()~`>#+-=|{}.!'

        # Экранируем каждый специальный символ
        escaped_text = text
        for char in special_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')

        return escaped_text

    @staticmethod
    def prepare_markdown_text(text: str) -> str:
        """
        Подготовка текста с Markdown разметкой для Telegram

        Args:
            text: Текст с Markdown

        Returns:
            str: Подготовленный текст
        """
        # Пока просто возвращаем текст как есть
        # Gemini должен сам форматировать текст правильно
        # Если будут проблемы, здесь можно добавить дополнительную обработку
        return text

    async def send_text_message(
        self,
        text: str,
        use_markdown: bool = True
    ) -> Optional[int]:
        """
        Отправка текстового сообщения в канал

        Args:
            text: Текст сообщения
            use_markdown: Использовать ли Markdown форматирование

        Returns:
            Optional[int]: ID отправленного сообщения или None
        """
        try:
            parse_mode = ParseMode.MARKDOWN_V2 if use_markdown else None

            # Если используем Markdown, подготавливаем текст
            message_text = self.prepare_markdown_text(text) if use_markdown else text

            logger.info(f"Отправка сообщения в канал {self.config.target_channel_id}...")

            message = await self.bot.send_message(
                chat_id=self.config.target_channel_id,
                text=message_text,
                parse_mode=parse_mode,
                disable_web_page_preview=False
            )

            logger.info(f"✅ Сообщение успешно отправлено (ID: {message.message_id})")
            return message.message_id

        except TelegramError as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
            return None

    async def send_photo_with_caption(
        self,
        photo_path: str,
        caption: str,
        use_markdown: bool = True
    ) -> Optional[int]:
        """
        Отправка фото с подписью в канал

        Args:
            photo_path: Путь к файлу изображения
            caption: Текст подписи
            use_markdown: Использовать ли Markdown форматирование

        Returns:
            Optional[int]: ID отправленного сообщения или None
        """
        try:
            parse_mode = ParseMode.MARKDOWN_V2 if use_markdown else None

            # Подготавливаем текст подписи
            caption_text = self.prepare_markdown_text(caption) if use_markdown else caption

            logger.info(f"Отправка фото с подписью в канал {self.config.target_channel_id}...")

            with open(photo_path, 'rb') as photo:
                message = await self.bot.send_photo(
                    chat_id=self.config.target_channel_id,
                    photo=photo,
                    caption=caption_text,
                    parse_mode=parse_mode
                )

            logger.info(f"✅ Фото успешно отправлено (ID: {message.message_id})")
            return message.message_id

        except FileNotFoundError:
            logger.error(f"Файл изображения не найден: {photo_path}")
            return None
        except TelegramError as e:
            logger.error(f"Ошибка отправки фото в Telegram: {e}")
            return None

    async def publish_post(
        self,
        text: str,
        image_path: Optional[str] = None
    ) -> Optional[int]:
        """
        Публикация поста в канал (с изображением или без)

        Args:
            text: Текст поста (с Markdown)
            image_path: Путь к изображению (опционально)

        Returns:
            Optional[int]: ID отправленного сообщения или None
        """
        try:
            # Если есть изображение - отправляем фото с подписью
            if image_path:
                logger.info("Публикация поста с изображением...")
                return await self.send_photo_with_caption(
                    photo_path=image_path,
                    caption=text,
                    use_markdown=True
                )
            # Иначе - просто текстовое сообщение
            else:
                logger.info("Публикация текстового поста...")
                return await self.send_text_message(
                    text=text,
                    use_markdown=True
                )

        except Exception as e:
            logger.error(f"Ошибка публикации поста: {e}")
            return None

    async def test_connection(self) -> bool:
        """
        Тестирование соединения с Telegram Bot API

        Returns:
            bool: True если соединение успешно
        """
        try:
            me = await self.bot.get_me()
            logger.info(f"✅ Telegram Bot подключен: @{me.username}")
            return True
        except TelegramError as e:
            logger.error(f"❌ Ошибка подключения к Telegram Bot: {e}")
            return False

    async def get_channel_info(self) -> Optional[dict]:
        """
        Получение информации о канале

        Returns:
            Optional[dict]: Информация о канале или None
        """
        try:
            chat = await self.bot.get_chat(chat_id=self.config.target_channel_id)
            info = {
                'title': chat.title,
                'type': chat.type,
                'username': chat.username,
                'description': chat.description
            }
            logger.info(f"Информация о канале: {info['title']} (@{info['username']})")
            return info
        except TelegramError as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
            return None


async def main():
    """Тестирование модуля"""
    from config_loader import get_config

    try:
        config = get_config()
        poster = TelegramPoster(config)

        # Тест подключения
        print("🔗 Тестирование подключения к Telegram Bot...")
        if await poster.test_connection():
            print("✅ Подключение успешно!")

        # Получаем информацию о канале
        print("\n📢 Получение информации о канале...")
        channel_info = await poster.get_channel_info()
        if channel_info:
            print(f"Канал: {channel_info['title']}")
            print(f"Username: @{channel_info['username']}")

        # Тестовая публикация (закомментировано, чтобы не спамить)
        # test_text = """
        # *Тестовый пост от NeuroScov Bot*
        #
        # Это тестовое сообщение для проверки работы бота\.
        #
        # #тест #нейроскуф
        # """
        #
        # print("\n📤 Отправка тестового сообщения...")
        # message_id = await poster.publish_post(test_text)
        # if message_id:
        #     print(f"✅ Сообщение опубликовано (ID: {message_id})")

    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
