"""
Модуль планировщика для автоматической публикации постов
Использует APScheduler для управления расписанием
"""
import logging
import random
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config_loader import Config
from db_handler import DatabaseHandler
from source_aggregator import SourceAggregator
from gemini_processor import GeminiProcessor
from telegram_poster import TelegramPoster

logger = logging.getLogger(__name__)


class BotScheduler:
    """Класс для управления расписанием публикаций"""

    def __init__(self, config: Config):
        """
        Инициализация планировщика

        Args:
            config: Объект конфигурации
        """
        self.config = config
        self.scheduler = AsyncIOScheduler()

        # Инициализация модулей
        self.db = DatabaseHandler(config.database_path)
        self.aggregator = SourceAggregator(config)
        self.processor = GeminiProcessor(config)
        self.poster = TelegramPoster(config)

        logger.info("Планировщик инициализирован")

    async def run_workflow(self):
        """
        Основной рабочий процесс:
        1. Сбор контента
        2. Фильтрация дубликатов
        3. Выбор поста
        4. Обработка через Gemini
        5. Публикация в Telegram
        """
        try:
            logger.info("=" * 60)
            logger.info("🚀 ЗАПУСК РАБОЧЕГО ПРОЦЕССА")
            logger.info("=" * 60)

            # Шаг 1: Сбор контента из всех источников
            logger.info("📥 Шаг 1: Сбор контента из источников...")
            all_posts = await self.aggregator.fetch_all_sources()

            if not all_posts:
                logger.warning("⚠️ Нет новых постов из источников. Пропускаем цикл.")
                return

            logger.info(f"Собрано {len(all_posts)} постов")

            # Шаг 2: Фильтрация дубликатов
            logger.info("🔍 Шаг 2: Фильтрация дубликатов...")
            unique_posts = []

            for post in all_posts:
                # Вычисляем хэш контента
                content_hash = self.db.calculate_content_hash(
                    post.content,
                    post.url
                )

                # Проверяем, не публиковали ли мы это уже
                if not self.db.is_duplicate(content_hash):
                    unique_posts.append({
                        'post': post,
                        'hash': content_hash
                    })

            if not unique_posts:
                logger.warning("⚠️ Все посты уже были опубликованы ранее. Нет нового контента.")
                return

            logger.info(f"Найдено {len(unique_posts)} уникальных постов")

            # Шаг 3: Выбираем самый свежий/релевантный пост
            logger.info("🎯 Шаг 3: Выбор поста для публикации...")
            selected = unique_posts[0]  # Берем первый (самый свежий)
            selected_post = selected['post']
            selected_hash = selected['hash']

            logger.info(f"Выбран пост: {selected_post.title[:50]}...")
            logger.info(f"Источник: {selected_post.source_type}/{selected_post.source_name}")

            # Шаг 4: Обработка через Gemini
            logger.info("🧠 Шаг 4: Обработка текста через Gemini...")
            processed = await self.processor.process_post(
                original_text=selected_post.content,
                title=selected_post.title
            )

            rewritten_text = processed['rewritten_text']
            image_path = processed['image_path']

            logger.info(f"Текст обработан. Длина: {len(rewritten_text)} символов")

            # Шаг 5: Публикация в Telegram
            logger.info("📤 Шаг 5: Публикация в Telegram канал...")
            message_id = await self.poster.publish_post(
                text=rewritten_text,
                image_path=image_path
            )

            if message_id:
                logger.info(f"✅ Пост успешно опубликован! Message ID: {message_id}")

                # Шаг 6: Сохранение в БД
                logger.info("💾 Шаг 6: Сохранение в базу данных...")
                self.db.add_published_post(
                    content_hash=selected_hash,
                    source_url=selected_post.url,
                    source_type=selected_post.source_type,
                    title=selected_post.title,
                    telegram_message_id=message_id
                )

                logger.info("=" * 60)
                logger.info("✨ РАБОЧИЙ ПРОЦЕСС ЗАВЕРШЕН УСПЕШНО")
                logger.info("=" * 60)
            else:
                logger.error("❌ Не удалось опубликовать пост в Telegram")

        except Exception as e:
            logger.error(f"❌ Ошибка в рабочем процессе: {e}")
            import traceback
            traceback.print_exc()

    def calculate_posting_times(self) -> list:
        """
        Вычисление времени публикаций на день с учетом jitter

        Returns:
            list: Список времен для публикации (часы)
        """
        posts_per_day = self.config.posts_per_day
        jitter_minutes = self.config.schedule_jitter_minutes

        # Делим день на равные интервалы
        interval_hours = 24 / posts_per_day

        times = []
        for i in range(posts_per_day):
            # Базовое время
            base_hour = i * interval_hours

            # Добавляем случайное отклонение (jitter)
            jitter_hours = random.uniform(-jitter_minutes / 60, jitter_minutes / 60)
            actual_hour = (base_hour + jitter_hours) % 24

            times.append(actual_hour)

        times.sort()
        return times

    def start(self):
        """Запуск планировщика"""
        logger.info("🚀 Запуск планировщика...")

        # Вычисляем времена публикации
        posting_times = self.calculate_posting_times()

        logger.info(f"Настроено {len(posting_times)} публикаций в день:")
        for i, hour in enumerate(posting_times, 1):
            hour_int = int(hour)
            minute_int = int((hour - hour_int) * 60)
            logger.info(f"  {i}. Около {hour_int:02d}:{minute_int:02d}")

        # Вариант 1: Интервальный триггер (каждые N часов с jitter)
        # Это более простой подход
        hours_interval = 24 / self.config.posts_per_day

        self.scheduler.add_job(
            self.run_workflow,
            trigger=IntervalTrigger(hours=hours_interval),
            id='post_workflow',
            name='Публикация поста',
            replace_existing=True,
            max_instances=1  # Не запускать новый, пока предыдущий не завершен
        )

        # Вариант 2: Cron триггер для конкретных времен (закомментирован)
        # for hour in posting_times:
        #     hour_int = int(hour)
        #     minute_int = int((hour - hour_int) * 60)
        #
        #     self.scheduler.add_job(
        #         self.run_workflow,
        #         trigger=CronTrigger(hour=hour_int, minute=minute_int),
        #         id=f'post_workflow_{hour_int}_{minute_int}',
        #         name=f'Публикация поста {hour_int:02d}:{minute_int:02d}',
        #         replace_existing=True
        #     )

        # Опционально: запустить один раз сразу при старте
        # self.scheduler.add_job(
        #     self.run_workflow,
        #     'date',
        #     run_date=datetime.now() + timedelta(seconds=10),
        #     id='initial_run',
        #     name='Первоначальный запуск'
        # )

        self.scheduler.start()
        logger.info("✅ Планировщик запущен и работает")

    def stop(self):
        """Остановка планировщика"""
        logger.info("🛑 Остановка планировщика...")
        self.scheduler.shutdown(wait=True)
        logger.info("✅ Планировщик остановлен")

    async def run_once(self):
        """Запуск рабочего процесса один раз (для тестирования)"""
        await self.run_workflow()

    async def get_statistics(self):
        """Получение статистики работы бота"""
        stats = self.db.get_statistics()
        logger.info("📊 Статистика работы бота:")
        logger.info(f"  Всего опубликовано постов: {stats['total_posts']}")
        logger.info(f"  За последние 7 дней: {stats['recent_7days']}")
        logger.info(f"  По источникам: {stats['by_source_type']}")
        return stats


async def main():
    """Тестирование планировщика"""
    from config_loader import get_config

    try:
        config = get_config()
        scheduler = BotScheduler(config)

        print("🧪 Тестовый запуск рабочего процесса...")
        await scheduler.run_once()

        print("\n📊 Статистика:")
        await scheduler.get_statistics()

    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
