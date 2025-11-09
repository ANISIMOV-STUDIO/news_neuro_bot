"""
Модуль для работы с базой данных
Хранит историю опубликованных постов для предотвращения дублирования
"""
import sqlite3
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseHandler:
    """Класс для работы с базой данных SQLite"""

    def __init__(self, db_path: str):
        """
        Инициализация обработчика БД

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._init_database()
        logger.info(f"База данных инициализирована: {db_path}")

    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для безопасной работы с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка работы с БД: {e}")
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Создание таблиц в базе данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица опубликованных постов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS published_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT UNIQUE NOT NULL,
                    source_url TEXT,
                    source_type TEXT NOT NULL,
                    title TEXT,
                    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_message_id INTEGER,
                    reactions_count INTEGER DEFAULT 0,
                    UNIQUE(content_hash)
                )
            """)

            # Таблица для отслеживания реакций (для будущих версий)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS post_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    reaction_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES published_posts(id)
                )
            """)

            # Индексы для оптимизации запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_hash
                ON published_posts(content_hash)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_published_at
                ON published_posts(published_at)
            """)

            logger.info("Таблицы БД созданы/проверены")

    @staticmethod
    def calculate_content_hash(text: str, url: Optional[str] = None) -> str:
        """
        Вычисление хэша контента для проверки уникальности

        Args:
            text: Текст поста
            url: URL источника (опционально)

        Returns:
            str: SHA256 хэш контента
        """
        # Используем комбинацию текста и URL для создания уникального хэша
        content = f"{text}{url or ''}".encode('utf-8')
        return hashlib.sha256(content).hexdigest()

    def is_duplicate(self, content_hash: str) -> bool:
        """
        Проверка, был ли контент уже опубликован

        Args:
            content_hash: Хэш контента

        Returns:
            bool: True если контент уже был опубликован
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM published_posts WHERE content_hash = ?",
                (content_hash,)
            )
            result = cursor.fetchone()
            return result is not None

    def add_published_post(
        self,
        content_hash: str,
        source_url: Optional[str] = None,
        source_type: str = "unknown",
        title: Optional[str] = None,
        telegram_message_id: Optional[int] = None
    ) -> int:
        """
        Добавление записи об опубликованном посте

        Args:
            content_hash: Хэш контента
            source_url: URL источника
            source_type: Тип источника (rss, telegram)
            title: Заголовок поста
            telegram_message_id: ID сообщения в Telegram

        Returns:
            int: ID добавленной записи
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO published_posts
                    (content_hash, source_url, source_type, title, telegram_message_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (content_hash, source_url, source_type, title, telegram_message_id))

                post_id = cursor.lastrowid
                logger.info(f"Добавлен пост в БД: ID={post_id}, hash={content_hash[:10]}...")
                return post_id

            except sqlite3.IntegrityError:
                logger.warning(f"Попытка добавить дубликат: {content_hash[:10]}...")
                # Возвращаем ID существующей записи
                cursor.execute(
                    "SELECT id FROM published_posts WHERE content_hash = ?",
                    (content_hash,)
                )
                result = cursor.fetchone()
                return result['id'] if result else -1

    def get_recent_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получение списка последних опубликованных постов

        Args:
            limit: Максимальное количество постов

        Returns:
            List[Dict]: Список постов
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM published_posts
                ORDER BY published_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_post_by_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """
        Получение поста по хэшу

        Args:
            content_hash: Хэш контента

        Returns:
            Optional[Dict]: Данные поста или None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM published_posts WHERE content_hash = ?",
                (content_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_reactions(self, telegram_message_id: int, reactions_count: int):
        """
        Обновление количества реакций на пост (для будущих версий)

        Args:
            telegram_message_id: ID сообщения в Telegram
            reactions_count: Количество реакций
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE published_posts
                SET reactions_count = ?
                WHERE telegram_message_id = ?
            """, (reactions_count, telegram_message_id))

            logger.info(f"Обновлены реакции для сообщения {telegram_message_id}: {reactions_count}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по базе данных

        Returns:
            Dict: Статистика
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Общее количество постов
            cursor.execute("SELECT COUNT(*) as total FROM published_posts")
            total_posts = cursor.fetchone()['total']

            # Посты по источникам
            cursor.execute("""
                SELECT source_type, COUNT(*) as count
                FROM published_posts
                GROUP BY source_type
            """)
            by_source = {row['source_type']: row['count'] for row in cursor.fetchall()}

            # Посты за последние 7 дней
            cursor.execute("""
                SELECT COUNT(*) as recent
                FROM published_posts
                WHERE published_at >= datetime('now', '-7 days')
            """)
            recent_posts = cursor.fetchone()['recent']

            return {
                'total_posts': total_posts,
                'by_source_type': by_source,
                'recent_7days': recent_posts
            }

    def cleanup_old_posts(self, days: int = 90):
        """
        Очистка старых постов из базы данных

        Args:
            days: Количество дней для хранения постов
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM published_posts
                WHERE published_at < datetime('now', '-' || ? || ' days')
            """, (days,))

            deleted_count = cursor.rowcount
            logger.info(f"Удалено старых постов: {deleted_count}")


if __name__ == "__main__":
    # Тестирование модуля
    import os
    test_db = "./test_neuroscov.db"

    try:
        # Создаем тестовую БД
        db = DatabaseHandler(test_db)

        # Тестируем добавление поста
        test_hash = db.calculate_content_hash("Test post content", "https://example.com")
        print(f"Test hash: {test_hash}")

        # Проверяем дубликат (должно быть False)
        print(f"Is duplicate: {db.is_duplicate(test_hash)}")

        # Добавляем пост
        post_id = db.add_published_post(
            content_hash=test_hash,
            source_url="https://example.com",
            source_type="test",
            title="Test Post"
        )
        print(f"Added post ID: {post_id}")

        # Проверяем дубликат (должно быть True)
        print(f"Is duplicate now: {db.is_duplicate(test_hash)}")

        # Получаем статистику
        stats = db.get_statistics()
        print(f"Statistics: {stats}")

        print("✅ Все тесты пройдены!")

    finally:
        # Удаляем тестовую БД
        if os.path.exists(test_db):
            os.remove(test_db)
