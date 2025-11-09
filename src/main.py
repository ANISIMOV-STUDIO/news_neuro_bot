"""
NeuroScov Bot - Главный модуль
Автоматизированный AI-ассистент для Telegram-канала "Scov Touch"
"""
import sys
import os
import asyncio
import logging
import argparse
from pathlib import Path

# Добавляем src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import get_config
from scheduler import BotScheduler

# Настройка логирования
def setup_logging(log_level=logging.INFO):
    """Настройка системы логирования"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Создаем директорию для логов, если её нет
    log_dir = Path('./logs')
    log_dir.mkdir(exist_ok=True)

    # Настраиваем логирование в файл и консоль
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_dir / 'neuroscov_bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

logger = logging.getLogger(__name__)


def print_banner():
    """Вывод банера приложения"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║              🤖 NEUROSCOV BOT v1.0 MVP                    ║
    ║                                                           ║
    ║      AI-Powered Telegram Channel Automation               ║
    ║      for "Scov Touch"                                     ║
    ║                                                           ║
    ║      Powered by: Gemini AI + Telegram Bot API             ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


async def run_bot(args):
    """
    Основная функция запуска бота

    Args:
        args: Аргументы командной строки
    """
    try:
        # Загружаем конфигурацию
        logger.info("Загрузка конфигурации...")
        config = get_config(args.env_file)

        # Создаем планировщик
        logger.info("Инициализация планировщика...")
        scheduler = BotScheduler(config)

        # Режим работы
        if args.mode == 'once':
            # Однократный запуск (тест)
            logger.info("Режим: Однократный запуск")
            await scheduler.run_once()
            logger.info("Однократный запуск завершен")

        elif args.mode == 'daemon':
            # Режим демона (постоянная работа)
            logger.info("Режим: Демон (постоянная работа)")
            scheduler.start()

            # Держим бота запущенным
            try:
                while True:
                    await asyncio.sleep(60)  # Проверяем каждую минуту
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки (Ctrl+C)")
                scheduler.stop()

        elif args.mode == 'stats':
            # Вывод статистики
            logger.info("Режим: Вывод статистики")
            await scheduler.get_statistics()

        else:
            logger.error(f"Неизвестный режим: {args.mode}")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='NeuroScov Bot - AI-ассистент для Telegram канала',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py                    # Запуск в режиме демона
  python main.py --mode once        # Однократный запуск (тест)
  python main.py --mode stats       # Вывод статистики
  python main.py --env-file .env    # Указать путь к .env файлу
  python main.py --debug            # Запуск с отладочными логами
        """
    )

    parser.add_argument(
        '--mode',
        choices=['daemon', 'once', 'stats'],
        default='daemon',
        help='Режим работы бота (по умолчанию: daemon)'
    )

    parser.add_argument(
        '--env-file',
        type=str,
        default=None,
        help='Путь к .env файлу (по умолчанию: .env в корне проекта)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Включить отладочные логи'
    )

    return parser.parse_args()


def main():
    """Точка входа в приложение"""
    # Парсим аргументы
    args = parse_arguments()

    # Настраиваем логирование
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)

    # Выводим баннер
    print_banner()

    # Запускаем бота
    try:
        asyncio.run(run_bot(args))
    except KeyboardInterrupt:
        logger.info("\n👋 Работа бота прервана пользователем")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
