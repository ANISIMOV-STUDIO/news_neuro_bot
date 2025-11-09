"""
Модуль для обработки контента через Gemini API
Рерайтинг текста и генерация изображений
"""
import logging
import os
import base64
import asyncio
from typing import Optional, Dict, Any
import google.generativeai as genai
from PIL import Image
import io

from config_loader import Config

logger = logging.getLogger(__name__)


class GeminiProcessor:
    """Класс для работы с Gemini API"""

    def __init__(self, config: Config):
        """
        Инициализация процессора

        Args:
            config: Объект конфигурации
        """
        self.config = config

        # Настройка API ключа
        genai.configure(api_key=config.gemini_api_key)

        # Инициализация моделей
        self.text_model = genai.GenerativeModel(config.gemini_model)
        self.image_model = genai.GenerativeModel(config.gemini_image_model)

        logger.info(f"Gemini процессор инициализирован (модель: {config.gemini_model})")

    def rewrite_text(self, text: str) -> str:
        """
        Рерайтинг текста в стиле "нейроскуфа"

        Args:
            text: Исходный текст новости

        Returns:
            str: Переписанный текст с Markdown-форматированием и хештегами
        """
        try:
            # Формируем промпт из шаблона
            prompt = self.config.rewrite_prompt_template.format(
                text=text,
                channel_link=self.config.channel_link
            )

            logger.info("Отправка запроса на рерайтинг в Gemini...")
            logger.debug(f"Промпт: {prompt[:200]}...")

            # Генерация ответа
            response = self.text_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.9,  # Более креативный подход
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=1024,
                )
            )

            # Извлекаем текст из ответа
            if response.text:
                rewritten_text = response.text.strip()
                logger.info(f"Текст успешно переписан ({len(rewritten_text)} символов)")
                return rewritten_text
            else:
                logger.warning("Gemini вернул пустой ответ")
                return text

        except Exception as e:
            logger.error(f"Ошибка рерайтинга текста: {e}")
            # В случае ошибки возвращаем оригинальный текст
            return text

    def generate_image(self, prompt_text: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Генерация изображения через Gemini/Imagen

        Args:
            prompt_text: Описание того, что должно быть на картинке
            output_path: Путь для сохранения изображения (опционально)

        Returns:
            Optional[str]: Путь к сохраненному изображению или None
        """
        try:
            # Формируем промпт для генерации изображения
            image_prompt = self.config.image_prompt_template.format(topic=prompt_text)

            logger.info("Отправка запроса на генерацию изображения...")
            logger.debug(f"Промпт для изображения: {image_prompt[:200]}...")

            # Определяем путь для сохранения
            if not output_path:
                os.makedirs('./temp_images', exist_ok=True)
                output_path = f'./temp_images/generated_{int(asyncio.get_event_loop().time())}.png'

            # Попытка генерации через Imagen API
            try:
                # Используем модель для генерации изображения
                response = self.image_model.generate_content(
                    image_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.8,
                    )
                )

                # Проверяем, есть ли в ответе изображение
                if hasattr(response, '_result') and hasattr(response._result, 'candidates'):
                    for part in response._result.candidates[0].content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Сохраняем изображение из inline_data
                            image_data = part.inline_data.data
                            with open(output_path, 'wb') as f:
                                f.write(image_data)

                            logger.info(f"✅ Изображение сгенерировано и сохранено: {output_path}")
                            return output_path

                logger.warning("API не вернул изображение, создаю placeholder...")

            except Exception as api_error:
                logger.warning(f"Ошибка API генерации изображений: {api_error}")
                logger.info("Создаю placeholder изображение...")

            # Fallback: создаем placeholder изображение с PIL
            return self._create_placeholder_image(prompt_text, output_path)

        except Exception as e:
            logger.error(f"Критическая ошибка генерации изображения: {e}")
            return None

    def _create_placeholder_image(self, prompt_text: str, output_path: str) -> str:
        """
        Создание placeholder изображения с текстом

        Args:
            prompt_text: Текст для отображения
            output_path: Путь для сохранения

        Returns:
            str: Путь к созданному изображению
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Создаем изображение в стиле киберпанк
            width, height = 1200, 630

            # Градиент от темно-синего к фиолетовому
            img = Image.new('RGB', (width, height), color='#0a0e27')
            draw = ImageDraw.Draw(img)

            # Добавляем градиент
            for y in range(height):
                color_value = int(10 + (y / height) * 40)
                draw.rectangle([(0, y), (width, y+1)], fill=(color_value, color_value//2, color_value*2))

            # Добавляем текст
            text = "🤖 NeuroScov Bot"
            subtitle = prompt_text[:80] + "..." if len(prompt_text) > 80 else prompt_text

            # Используем дефолтный шрифт
            try:
                # Пытаемся использовать системный шрифт
                font_large = ImageFont.truetype("/system/fonts/Roboto-Bold.ttf", 60)
                font_small = ImageFont.truetype("/system/fonts/Roboto-Regular.ttf", 30)
            except:
                # Fallback на дефолтный
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Рисуем текст по центру
            bbox = draw.textbbox((0, 0), text, font=font_large)
            text_width = bbox[2] - bbox[0]
            text_x = (width - text_width) // 2

            # Основной заголовок
            draw.text((text_x, height//2 - 80), text, fill='#00ffff', font=font_large)

            # Подзаголовок
            bbox_sub = draw.textbbox((0, 0), subtitle, font=font_small)
            sub_width = bbox_sub[2] - bbox_sub[0]
            sub_x = (width - sub_width) // 2
            draw.text((sub_x, height//2 + 20), subtitle, fill='#ff00ff', font=font_small)

            # Сохраняем
            img.save(output_path, 'PNG')
            logger.info(f"✅ Placeholder изображение создано: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Ошибка создания placeholder: {e}")
            raise

    def generate_image_prompt(self, text: str) -> str:
        """
        Генерация промпта для изображения на основе текста поста

        Args:
            text: Текст поста

        Returns:
            str: Промпт для генерации изображения
        """
        try:
            prompt = f"""На основе этого текста создай краткое описание (на английском) для генерации изображения.
Описание должно быть в стиле: киберпанк, брутальный IT-юмор, неоновые цвета.
Максимум 2-3 предложения.

Текст:
{text[:500]}

Верни только описание для изображения, без дополнительных комментариев."""

            response = self.text_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=200,
                )
            )

            if response.text:
                image_prompt = response.text.strip()
                logger.info(f"Сгенерирован промпт для изображения: {image_prompt}")
                return image_prompt
            else:
                return "cyberpunk IT theme with neon colors"

        except Exception as e:
            logger.error(f"Ошибка генерации промпта для изображения: {e}")
            return "cyberpunk IT theme with neon colors"

    def extract_summary(self, text: str, max_length: int = 200) -> str:
        """
        Извлечение краткой сути из текста

        Args:
            text: Исходный текст
            max_length: Максимальная длина резюме

        Returns:
            str: Краткое резюме
        """
        try:
            prompt = f"""Создай краткую суть этого текста (максимум {max_length} символов).
Только суть, без лишних слов.

Текст:
{text}"""

            response = self.text_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=100,
                )
            )

            if response.text:
                summary = response.text.strip()
                logger.info(f"Извлечена суть текста: {summary[:50]}...")
                return summary
            else:
                # Fallback: просто обрезаем текст
                return text[:max_length]

        except Exception as e:
            logger.error(f"Ошибка извлечения сути: {e}")
            return text[:max_length]

    async def process_post(self, original_text: str, title: str = "") -> Dict[str, Any]:
        """
        Полная обработка поста: рерайтинг + подготовка к публикации

        Args:
            original_text: Оригинальный текст поста
            title: Заголовок поста (опционально)

        Returns:
            Dict: Обработанные данные поста
        """
        logger.info("Начало обработки поста...")

        # Объединяем заголовок и текст для рерайтинга
        full_text = f"{title}\n\n{original_text}" if title else original_text

        # Рерайтинг текста
        rewritten_text = self.rewrite_text(full_text)

        # Генерация промпта для изображения
        image_prompt = self.generate_image_prompt(rewritten_text)

        # Генерация изображения
        logger.info("Генерация изображения для поста...")
        image_path = self.generate_image(image_prompt)

        # Извлекаем краткую суть (для метаданных)
        summary = self.extract_summary(rewritten_text, max_length=150)

        result = {
            'rewritten_text': rewritten_text,
            'image_prompt': image_prompt,
            'summary': summary,
            'image_path': image_path  # Теперь реально генерируется
        }

        logger.info(f"Пост успешно обработан (изображение: {'✅' if image_path else '❌'})")
        return result


async def main():
    """Тестирование модуля"""
    from config_loader import get_config

    try:
        config = get_config()
        processor = GeminiProcessor(config)

        # Тестовый текст
        test_text = """
        OpenAI представила новую версию GPT-5, которая превосходит все предыдущие модели
        по качеству генерации текста и понимания контекста. Компания утверждает, что
        новая модель может решать сложные задачи программирования и математики.
        """

        print("🧠 Тестируем рерайтинг текста...")
        result = await processor.process_post(test_text, "Новая модель от OpenAI")

        print("\n✅ Результат обработки:")
        print(f"\nПереписанный текст:\n{result['rewritten_text']}")
        print(f"\nПромпт для изображения: {result['image_prompt']}")
        print(f"\nСуть: {result['summary']}")

    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
