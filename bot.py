import requests
import logging
import asyncio
import aiohttp
import random
import json
import os
import io
import re
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from config import Config

# Настройка логирования без эмодзи для Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CryptoNewsBot:
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.channel = Config.CHANNEL_ID
        self.session = None
        self.published_news = set()
        self.published_signals = set()
        self.load_published_news()

        # Байтовые фразы для постов
        self.viral_phrases = [
            "ЗАЛЕТАЕМ В ТРЕНДЫ!",
            "ХАЙП НА СТАРТЕ!",
            "ГОРИМ, НО НЕ СДАЕМСЯ!",
            "ВЗЛЕТАЕМ НА ЛУНУ!",
            "БОМБИЧЕСКИЕ НОВОСТИ!",
            "ВНИМАНИЕ, ХАЙП!",
            "ТОЧКА ВХОДА!",
            "МОМЕНТ ИСТИНЫ!",
            "ЗВЕЗДНЫЙ ЧАС!",
            "БОМБА ДНЯ!"
        ]

        self.signal_phrases = [
            "🚀 СИГНАЛ НА ПОКУПКУ!",
            "💎 ВИЖУ РОСТ!",
            "📈 ЛОВИМ ВОЛНУ!",
            "🔥 ГОРИМ НА ПРОФИТЕ!",
            "🎯 ТОЧКА ВХОДА ОТМЕЧЕНА!",
            "⚡ МОМЕНТ ИСТИНЫ!",
            "💸 ЗАРАБАТЫВАЕМ ВМЕСТЕ!",
            "🌟 ЗВЕЗДНЫЙ СИГНАЛ!"
        ]

        self.emojis = ["🚀", "💎", "🔥", "📈", "💥", "🎯", "⚡", "🌟", "💣", "🎊", "👑", "💸", "🤑", "👀"]

        # Загружаем логотип
        self.logo = self.load_logo()

    def load_logo(self):
        """Загружает логотип из файла"""
        try:
            if os.path.exists('лого.png'):
                logo = Image.open('лого.png')
                logo = logo.resize((200, 80), Image.Resampling.LANCZOS)
                logger.info("Логотип загружен успешно")
                return logo
            else:
                logger.warning("Логотип 'лого.png' не найден, создаем стандартный")
                return self.create_default_logo()
        except Exception as e:
            logger.error(f"Error loading logo: {e}")
            return self.create_default_logo()

    def create_default_logo(self):
        """Создает стандартный логотип если файл не найден"""
        try:
            logo = Image.new('RGB', (200, 80), color=(255, 193, 7))
            draw = ImageDraw.Draw(logo)

            try:
                font = ImageFont.truetype("arial.ttf", 20)
                font_small = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()

            draw.text((10, 10), "A", fill=(0, 0, 0), font=font)
            draw.text((40, 15), "ANT CAPITAL", fill=(0, 0, 0), font=font_small)
            draw.rectangle([0, 0, 199, 79], outline=(0, 0, 0), width=2)

            return logo
        except Exception as e:
            logger.error(f"Error creating default logo: {e}")
            return None

    def load_published_news(self):
        """Загружает историю опубликованных новостей и сигналов"""
        try:
            if os.path.exists('published_news.json'):
                with open('published_news.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.published_news = set(data.get('published_news', []))
                    self.published_signals = set(data.get('published_signals', []))
                    logger.info(
                        f"Загружено {len(self.published_news)} новостей и {len(self.published_signals)} сигналов")
        except Exception as e:
            logger.error(f"Error loading published data: {e}")

    def save_published_news(self):
        """Сохраняет историю опубликованных новостей и сигналов"""
        try:
            with open('published_news.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'published_news': list(self.published_news),
                    'published_signals': list(self.published_signals)
                }, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving published data: {e}")

    async def init_session(self):
        """Инициализация HTTP сессии с увеличенным таймаутом"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info("HTTP сессия инициализирована")

    async def close_session(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
            logger.info("HTTP сессия закрыта")

    # МЕТОДЫ ДЛЯ СИГНАЛОВ
    async def get_tradingview_signals(self):
        """Парсинг торговых сигналов с TradingView"""
        try:
            url = "https://ru.tradingview.com/ideas/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://ru.tradingview.com/'
            }

            logger.info("Получаем сигналы с TradingView...")
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                else:
                    logger.error(f"TradingView вернул статус: {response.status}")
                    return []

            soup = BeautifulSoup(html, 'html.parser')
            signals = []

            # Ищем карточки с идеями
            idea_cards = soup.find_all('div', class_=lambda x: x and 'card' in x)[:20]

            for card in idea_cards:
                try:
                    # Название актива и тип сигнала
                    title_elem = card.find('a', class_=lambda x: x and 'title' in x)
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()

                    # Фильтруем только BUY/LONG сигналы
                    title_upper = title.upper()
                    if not any(word in title_upper for word in
                               ['BUY', 'LONG', 'КУПИТЬ', 'ПОКУПКА', 'РОСТ', 'ВВЕРХ', 'BULL']):
                        continue

                    # Ссылка на идею
                    link = title_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://ru.tradingview.com' + link

                    # Описание идеи
                    description_elem = card.find('div', class_=lambda x: x and 'description' in x)
                    description = description_elem.text.strip() if description_elem else ""

                    # Автор
                    author_elem = card.find('a', class_=lambda x: x and 'username' in x)
                    author = author_elem.text.strip() if author_elem else "Аноним"

                    # Время
                    time_elem = card.find('span', class_=lambda x: x and 'time' in x)
                    time_text = time_elem.text.strip() if time_elem else ""

                    # Лайки
                    likes_elem = card.find('span', class_=lambda x: x and 'counter' in x)
                    likes = likes_elem.text.strip() if likes_elem else "0"

                    # Извлекаем тикер из заголовка
                    ticker_match = re.search(r'([A-Z]+:[A-Z]+|[A-Z]+/USD|[A-Z]+/USDT|[A-Z]+)', title)
                    ticker = ticker_match.group(1) if ticker_match else "N/A"

                    # Определяем тип актива
                    asset_type = "Крипто"
                    if any(word in ticker.upper() for word in [':US', ':NASDAQ', ':NYSE']):
                        asset_type = "Акции"
                    elif any(word in ticker.upper() for word in ['XAU', 'XAG', 'OIL', 'GOLD', 'SILVER']):
                        asset_type = "Товары"
                    elif any(word in ticker.upper() for word in ['EUR', 'USD', 'JPY', 'GBP']):
                        asset_type = "Форекс"

                    signal_id = hash(title + ticker + author)
                    if signal_id not in self.published_signals:
                        signals.append({
                            'ticker': ticker,
                            'title': title,
                            'description': description,
                            'link': link,
                            'author': author,
                            'time': time_text,
                            'likes': likes,
                            'asset_type': asset_type,
                            'id': signal_id
                        })

                except Exception as e:
                    continue

            logger.info(f"Найдено {len(signals)} новых сигналов с TradingView")
            return signals[:10]

        except Exception as e:
            logger.error(f"Error parsing TradingView signals: {e}")
            return []

    async def get_tradingview_crypto_signals(self):
        """Специализированный парсинг крипто-сигналов"""
        try:
            url = "https://ru.tradingview.com/ideas/cryptocurrencies/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }

            logger.info("Получаем крипто-сигналы с TradingView...")
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                else:
                    return []

            soup = BeautifulSoup(html, 'html.parser')
            signals = []

            # Ищем крипто-идеи
            crypto_ideas = soup.find_all('div', class_=lambda x: x and 'card' in x)[:15]

            for idea in crypto_ideas:
                try:
                    title_elem = idea.find('a', class_=lambda x: x and 'title' in x)
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()

                    # Фильтруем только позитивные сигналы
                    title_upper = title.upper()
                    if not any(word in title_upper for word in ['BUY', 'LONG', 'КУПИТЬ', 'BULLISH', 'РОСТ']):
                        continue

                    link = title_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://ru.tradingview.com' + link

                    # Извлекаем крипто-тикер
                    ticker_match = re.search(r'([A-Z]+USDT|[A-Z]+USD|BTC|ETH|BNB|ADA|DOT|SOL|XRP|DOGE)', title.upper())
                    if not ticker_match:
                        continue

                    ticker = ticker_match.group(1)

                    # Автор
                    author_elem = idea.find('a', class_=lambda x: x and 'username' in x)
                    author = author_elem.text.strip() if author_elem else "Крипто-трейдер"

                    signal_id = hash(title + ticker + author)
                    if signal_id not in self.published_signals:
                        signals.append({
                            'ticker': ticker,
                            'title': title,
                            'link': link,
                            'author': author,
                            'asset_type': 'Крипто',
                            'id': signal_id
                        })

                except Exception:
                    continue

            return signals[:5]

        except Exception as e:
            logger.error(f"Error parsing crypto signals: {e}")
            return []

    def create_signal_image(self, signal):
        """Создание изображения для сигнала"""
        try:
            width, height = 800, 600
            image = Image.new('RGB', (width, height), color=(13, 17, 23))
            draw = ImageDraw.Draw(image)

            # Градиентный фон
            for i in range(height):
                r = int(13 + (i / height) * 50)
                g = int(17 + (i / height) * 40)
                b = int(23 + (i / height) * 60)
                draw.line([(0, i), (width, i)], fill=(r, g, b))

            # Добавляем логотип
            if self.logo:
                image.paste(self.logo, (width - 210, 20))

            # Загружаем шрифты
            try:
                font_large = ImageFont.truetype("arial.ttf", 36)
                font_medium = ImageFont.truetype("arial.ttf", 24)
                font_small = ImageFont.truetype("arial.ttf", 18)
                font_bold = ImageFont.truetype("arialbd.ttf", 32)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
                font_bold = ImageFont.load_default()

            # Заголовок сигнала
            signal_phrase = random.choice(self.signal_phrases)
            bbox = draw.textbbox((0, 0), signal_phrase, font=font_medium)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, 100), signal_phrase,
                      fill=(76, 175, 80), font=font_medium)

            # Тикер
            ticker_text = f"🎯 {signal['ticker']}"
            bbox = draw.textbbox((0, 0), ticker_text, font=font_bold)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, 160), ticker_text,
                      fill=(255, 255, 255), font=font_bold)

            # Тип актива
            asset_text = f"📊 {signal['asset_type']}"
            bbox = draw.textbbox((0, 0), asset_text, font=font_medium)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, 210), asset_text,
                      fill=(255, 215, 0), font=font_medium)

            # Разделитель
            draw.line([(50, 260), (width - 50, 260)], fill=(255, 215, 0), width=2)

            # Описание сигнала
            description = signal['title']
            words = description.split()
            lines = []
            current_line = []

            for word in words:
                test_line = ' '.join(current_line + [word])
                if len(test_line) < 35:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]

            if current_line:
                lines.append(' '.join(current_line))

            lines = lines[:3]

            # Рисуем описание
            y_position = 290
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font_medium)
                text_width = bbox[2] - bbox[0]
                x_position = (width - text_width) // 2

                # Тень
                draw.text((x_position + 2, y_position + 2), line,
                          fill=(0, 0, 0), font=font_medium)
                # Основной текст
                draw.text((x_position, y_position), line,
                          fill=(255, 255, 255), font=font_medium)
                y_position += 45

            # Дополнительная информация
            info_y = y_position + 20
            if 'author' in signal:
                author_text = f"👤 Автор: {signal['author']}"
                bbox = draw.textbbox((0, 0), author_text, font=font_small)
                text_width = bbox[2] - bbox[0]
                draw.text(((width - text_width) // 2, info_y), author_text,
                          fill=(200, 200, 200), font=font_small)
                info_y += 30

            if 'likes' in signal:
                likes_text = f"❤️ Лайков: {signal['likes']}"
                bbox = draw.textbbox((0, 0), likes_text, font=font_small)
                text_width = bbox[2] - bbox[0]
                draw.text(((width - text_width) // 2, info_y), likes_text,
                          fill=(200, 200, 200), font=font_small)
                info_y += 30

            # Время и источник
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            source_text = f"Источник: TradingView | {timestamp}"
            bbox = draw.textbbox((0, 0), source_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, height - 80), source_text,
                      fill=(150, 150, 150), font=font_small)

            # Предупреждение
            warning_text = "⚠️ Торгуйте ответственно! Это не инвестиционная рекомендация."
            bbox = draw.textbbox((0, 0), warning_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, height - 40), warning_text,
                      fill=(255, 152, 0), font=font_small)

            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG', quality=95)
            img_buffer.seek(0)

            return img_buffer

        except Exception as e:
            logger.error(f"Error creating signal image: {e}")
            # Резервное изображение
            image = Image.new('RGB', (800, 600), color=(13, 17, 23))
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except:
                font = ImageFont.load_default()

            draw.text((100, 250), "🚀 СИГНАЛ НА ПОКУПКУ", fill=(76, 175, 80), font=font)
            draw.text((150, 300), f"Актив: {signal['ticker']}", fill=(255, 255, 255), font=font)

            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            return img_buffer

    def format_signal_text(self, signal):
        """Форматирование текста для сигнала"""
        ticker = signal['ticker']
        title = signal['title']
        asset_type = signal['asset_type']
        link = signal.get('link', '')
        author = signal.get('author', 'Трейдер')
        likes = signal.get('likes', '0')

        # Байтовое начало
        signal_phrase = random.choice(self.signal_phrases)

        text = f"<b>{signal_phrase}</b>\n\n"
        text += f"🎯 <b>Актив:</b> {ticker}\n"
        text += f"📊 <b>Тип:</b> {asset_type}\n"
        text += f"👤 <b>Автор:</b> {author}\n"
        text += f"❤️ <b>Лайков:</b> {likes}\n\n"

        text += f"💡 <b>Идея:</b>\n{title}\n\n"

        if link:
            text += f"🔗 <a href='{link}'>СМОТРЕТЬ АНАЛИЗ</a>\n\n"

        # Торговые рекомендации
        recommendations = [
            "📈 Рассмотреть лонг позицию",
            "💎 Установить стоп-лосс",
            "🎯 Определить тейк-профит",
            "⚠️ Управляйте рисками"
        ]

        text += "<b>🎯 РЕКОМЕНДАЦИИ:</b>\n"
        for rec in random.sample(recommendations, 3):
            text += f"• {rec}\n"

        text += "\n"
        text += "⚡ <b>ВАЖНО:</b> Это не инвестиционная рекомендация. Проводите собственный анализ!\n\n"

        # Хештеги
        text += f"#{asset_type.replace(' ', '')} #{ticker.replace(':', '').replace('/', '')} #Сигнал #Трейдинг"

        if asset_type == "Крипто":
            text += " #Crypto"
        elif asset_type == "Акции":
            text += " #Акции"
        elif asset_type == "Форекс":
            text += " #Форекс"

        return text

    async def publish_signal(self):
        """Публикация торгового сигнала"""
        try:
            logger.info("Проверяем новые сигналы...")

            # Получаем сигналы из разных источников
            signals_tasks = [
                self.get_tradingview_signals(),
                self.get_tradingview_crypto_signals()
            ]

            results = await asyncio.gather(*signals_tasks, return_exceptions=True)

            all_signals = []
            for result in results:
                if isinstance(result, list):
                    all_signals.extend(result)

            if not all_signals:
                logger.info("Новых сигналов не найдено")
                return False

            # Выбираем случайный сигнал
            signal = random.choice(all_signals)

            # Создаем изображение и текст
            image = self.create_signal_image(signal)
            post_text = self.format_signal_text(signal)

            # Отправляем в Telegram
            success = await self.send_photo_message(image, post_text)

            if success:
                self.published_signals.add(signal['id'])
                self.save_published_news()
                logger.info(f"Успешно опубликован сигнал: {signal['ticker']}")
                return True
            else:
                logger.error(f"Ошибка публикации сигнала: {signal['ticker']}")
                return False

        except Exception as e:
            logger.error(f"Ошибка в публикации сигнала: {e}")
            return False

    # МЕТОДЫ ДЛЯ НОВОСТЕЙ
    async def get_bitcoinist_news(self):
        """Парсинг новостей с Bitcoinist"""
        try:
            url = "https://bitcoinist.com/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }

            logger.info("Получаем новости с Bitcoinist...")
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                else:
                    logger.error(f"Bitcoinist вернул статус: {response.status}")
                    return []

            soup = BeautifulSoup(html, 'html.parser')
            articles = []

            # Ищем статьи
            news_items = soup.find_all('article')[:10]
            news_items.extend(soup.find_all('h2')[:5])
            news_items.extend(soup.find_all('h3')[:5])

            for item in news_items:
                try:
                    if item.name in ['h2', 'h3']:
                        title_elem = item.find('a')
                        if title_elem:
                            title = title_elem.text.strip()
                            link = title_elem.get('href', '')
                        else:
                            title = item.text.strip()
                            link = ""
                    else:
                        title_elem = item.find('h2') or item.find('h3') or item.find('a')
                        if title_elem:
                            title = title_elem.text.strip()
                            link_elem = title_elem if title_elem.name == 'a' else title_elem.find('a')
                            link = link_elem.get('href', '') if link_elem else ""
                        else:
                            continue

                    if title and len(title) > 10:
                        if link and not link.startswith('http'):
                            link = 'https://bitcoinist.com' + link

                        news_id = hash(title[:100])
                        if news_id not in self.published_news:
                            articles.append({
                                'title': title,
                                'link': link,
                                'source': 'Bitcoinist',
                                'id': news_id
                            })
                except Exception:
                    continue

            logger.info(f"Найдено {len(articles)} новых новостей с Bitcoinist")
            return articles[:5]

        except Exception as e:
            logger.error(f"Error parsing Bitcoinist: {e}")
            return []

    async def get_coingecko_news(self):
        """Парсинг новостей с CoinGecko"""
        try:
            url = "https://www.coingecko.com/en/news"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }

            logger.info("Получаем новости с CoinGecko...")
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                else:
                    return []

            soup = BeautifulSoup(html, 'html.parser')
            articles = []

            # Ищем новости
            news_items = soup.find_all('a', href=lambda x: x and '/news/' in x)[:10]

            for item in news_items:
                try:
                    title = item.text.strip()
                    if title and len(title) > 20:
                        link = item.get('href', '')
                        if link and not link.startswith('http'):
                            link = 'https://www.coingecko.com' + link

                        news_id = hash(title[:100])
                        if news_id not in self.published_news:
                            articles.append({
                                'title': title,
                                'link': link,
                                'source': 'CoinGecko',
                                'id': news_id
                            })
                except Exception:
                    continue

            logger.info(f"Найдено {len(articles)} новых новостей с CoinGecko")
            return articles[:5]

        except Exception as e:
            logger.error(f"Error parsing CoinGecko: {e}")
            return []

    async def get_newsbtc_news(self):
        """Парсинг новостей с NewsBTC"""
        try:
            url = "https://www.newsbtc.com/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }

            logger.info("Получаем новости с NewsBTC...")
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                else:
                    return []

            soup = BeautifulSoup(html, 'html.parser')
            articles = []

            # Ищем статьи
            news_items = soup.find_all('h3')[:10]

            for item in news_items:
                try:
                    title_elem = item.find('a')
                    if title_elem:
                        title = title_elem.text.strip()
                        link = title_elem.get('href', '')

                        if title and len(title) > 10:
                            if link and not link.startswith('http'):
                                link = 'https://www.newsbtc.com' + link

                            news_id = hash(title[:100])
                            if news_id not in self.published_news:
                                articles.append({
                                    'title': title,
                                    'link': link,
                                    'source': 'NewsBTC',
                                    'id': news_id
                                })
                except Exception:
                    continue

            logger.info(f"Найдено {len(articles)} новых новостей с NewsBTC")
            return articles[:5]

        except Exception as e:
            logger.error(f"Error parsing NewsBTC: {e}")
            return []

    async def get_economic_events(self):
        """Парсинг экономического календаря"""
        try:
            url = "https://ru.investing.com/economic-calendar/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            logger.info("Получаем экономический календарь...")
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                else:
                    return []

            soup = BeautifulSoup(html, 'html.parser')
            events = []

            event_rows = soup.find_all('tr', id=lambda x: x and x.startswith('eventRowId'))[:5]

            for row in event_rows:
                try:
                    time_elem = row.find('td', class_='time')
                    event_elem = row.find('td', class_='event')

                    if time_elem and event_elem:
                        time_str = time_elem.text.strip()
                        event_name = event_elem.text.strip()

                        events.append({
                            'time': time_str,
                            'event': event_name,
                            'importance': "Средняя"
                        })
                except Exception:
                    continue

            logger.info(f"Найдено {len(events)} экономических событий")
            return events
        except Exception as e:
            logger.error(f"Error parsing economic calendar: {e}")
            return []

    async def get_real_news(self):
        """Получение реальных новостей со всех источников"""
        all_articles = []

        sources = [
            self.get_bitcoinist_news(),
            self.get_coingecko_news(),
            self.get_newsbtc_news()
        ]

        results = await asyncio.gather(*sources, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)

        random.shuffle(all_articles)
        logger.info(f"Всего собрано {len(all_articles)} новостей из всех источников")
        return all_articles[:10]

    def create_news_image(self, title, source):
        """Создание изображения для новости"""
        try:
            width, height = 800, 600
            image = Image.new('RGB', (width, height), color=(13, 17, 23))
            draw = ImageDraw.Draw(image)

            # Градиентный фон
            for i in range(height):
                r = int(25 + (i / height) * 50)
                g = int(30 + (i / height) * 40)
                b = int(45 + (i / height) * 60)
                draw.line([(0, i), (width, i)], fill=(r, g, b))

            # Добавляем логотип
            if self.logo:
                image.paste(self.logo, (width - 210, 20))

            # Загружаем шрифты
            try:
                font_large = ImageFont.truetype("arial.ttf", 36)
                font_medium = ImageFont.truetype("arial.ttf", 24)
                font_small = ImageFont.truetype("arial.ttf", 18)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Виральная фраза
            viral_phrase = random.choice(self.viral_phrases)
            bbox = draw.textbbox((0, 0), viral_phrase, font=font_medium)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, 120), viral_phrase,
                      fill=(255, 215, 0), font=font_medium)

            # Разбиваем заголовок на строки
            words = title.split()
            lines = []
            current_line = []

            for word in words:
                test_line = ' '.join(current_line + [word])
                if len(test_line) < 40:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]

            if current_line:
                lines.append(' '.join(current_line))

            lines = lines[:4]

            # Рисуем заголовок
            y_position = 180
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font_large)
                text_width = bbox[2] - bbox[0]
                x_position = (width - text_width) // 2

                # Тень
                draw.text((x_position + 2, y_position + 2), line,
                          fill=(0, 0, 0), font=font_large)
                # Основной текст
                draw.text((x_position, y_position), line,
                          fill=(255, 255, 255), font=font_large)
                y_position += 50

            # Разделитель
            draw.line([(50, y_position + 20), (width - 50, y_position + 20)],
                      fill=(255, 215, 0), width=3)

            # Источник и время
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
            source_text = f"Источник: {source} | {timestamp}"
            bbox = draw.textbbox((0, 0), source_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, height - 80), source_text,
                      fill=(200, 200, 200), font=font_small)

            # Призыв к действию
            cta_text = "ПОДПИСЫВАЙСЯ И ЖМИ 👍"
            bbox = draw.textbbox((0, 0), cta_text, font=font_medium)
            text_width = bbox[2] - bbox[0]
            draw.text(((width - text_width) // 2, height - 40), cta_text,
                      fill=(255, 215, 0), font=font_medium)

            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG', quality=95)
            img_buffer.seek(0)

            return img_buffer

        except Exception as e:
            logger.error(f"Error creating image: {e}")
            image = Image.new('RGB', (800, 600), color=(13, 17, 23))
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            return img_buffer

    def format_post_text(self, article, economic_events=None):
        """Форматирование текста новости"""
        title = article['title']
        source = article['source']
        link = article['link']

        emoji = random.choice(self.emojis)
        start_phrase = random.choice([
            f"{emoji} ВАЖНЕЙШАЯ ИНФА ПО ТРЕЙДУ!",
            f"{emoji} ХАЙПАНЕМ НА ЭТОЙ НОВОСТИ!",
            f"{emoji} ТО, ЧТО ВСЕ ЖДАЛИ!",
            f"{emoji} СЕКРЕТНЫЙ ИНСАЙД!",
            f"{emoji} ЛУЧШИЙ ПОВОД ДЛЯ ВХОДА!"
        ])

        post_text = f"<b>{start_phrase}</b>\n\n"
        post_text += f"📢 {title}\n\n"

        reaction = random.choice([
            "💥 Это может изменить всё!",
            "🚀 Заряжаем ракеты!",
            "💎 Алмазные руки знают!",
            "🔥 Готовьте свои портфели!",
            "🎯 Идеальный момент для действия!"
        ])
        post_text += f"{reaction}\n\n"

        if link:
            post_text += f"🔗 <a href='{link}'>ЧИТАТЬ ПОДРОБНЕЕ</a>\n\n"

        if economic_events:
            post_text += "📅 <b>СЕГОДНЯ В ФОКУСЕ:</b>\n"
            for event in economic_events[:2]:
                post_text += f"• {event['time']} - {event['event']}\n"
            post_text += "\n"

        cta = random.choice([
            "👍 ЛАЙК ЕСЛИ АКТУАЛЬНО!",
            "🔔 ПОДПИСЫВАЙСЯ ЧТОБЫ НЕ ПРОПУСТИТЬ!",
            "🔄 РЕПОСТ ДРУЗЬЯМ-ТРЕЙДЕРАМ!"
        ])
        post_text += f"{cta}\n\n"

        post_text += "#Crypto #Трейдинг #Инвестиции #Новости"

        if any(word in title.lower() for word in ['bitcoin', 'btc', 'биткоин']):
            post_text += " #Bitcoin #BTC"
        elif any(word in title.lower() for word in ['ethereum', 'eth', 'эфириум']):
            post_text += " #Ethereum #ETH"

        return post_text

    async def publish_news_round(self):
        """Один цикл публикации новостей"""
        try:
            logger.info("Начинаем публикацию новостей...")

            fresh_news = await self.get_real_news()

            if not fresh_news:
                logger.warning("Новых новостей не найдено")
                backup_news = [
                    "Рынок криптовалют показывает стабильный рост - идеальное время для инвестиций!",
                    "Новые технологии блокчейн развиваются быстрыми темпами - не пропусти волну!",
                    "Крипто-индустрия привлекает все больше инвесторов - присоединяйся к успеху!"
                ]
                article = {
                    'title': random.choice(backup_news),
                    'source': 'ANT CAPITAL',
                    'link': '',
                    'id': hash(str(datetime.now()))
                }
                fresh_news = [article]

            economic_events = await self.get_economic_events()
            article = random.choice(fresh_news)

            image = self.create_news_image(article['title'], article['source'])
            post_text = self.format_post_text(article, economic_events)

            success = await self.send_photo_message(image, post_text)

            if success:
                self.published_news.add(article['id'])
                self.save_published_news()
                logger.info(f"Успешно опубликовано: {article['title']}")
            else:
                logger.error(f"Ошибка публикации: {article['title']}")

        except Exception as e:
            logger.error(f"Ошибка в цикле публикации: {e}")

    async def run(self):
        """Основной цикл бота"""
        await self.init_session()

        logger.info("ANT CAPITAL Crypto Bot Запущен!")
        logger.info(f"Канал: {self.channel}")
        logger.info(f"Токен: {self.token[:10]}...")
        logger.info("Режим: Новости + Торговые сигналы")

        # Приветственное сообщение
        welcome_msg = (
            "🚀 <b>ANT CAPITAL В ЭФИРЕ!</b>\n\n"
            "💎 Самый хайповый крипто-канал!\n"
            "📈 Надежные источники новостей\n"
            "🎯 Торговые сигналы с TradingView\n"
            "⚡ Аналитика и инсайды\n\n"
            "🔔 ПОДПИСЫВАЙСЯ И ЖМИ НА КОЛОКОЛЬЧИК!\n\n"
            "#ANT_CAPITAL #Запуск #Крипта #Сигналы"
        )
        await self.send_message(welcome_msg)

        await asyncio.sleep(10)

        # Чередуем публикацию новостей и сигналов
        content_types = ['news', 'signal']
        last_content_type = None

        while True:
            try:
                # Выбираем тип контента (чередуем новости и сигналы)
                if last_content_type == 'news':
                    current_type = 'signal'
                else:
                    current_type = random.choice(content_types)

                if current_type == 'news':
                    await self.publish_news_round()
                    last_content_type = 'news'
                else:
                    success = await self.publish_signal()
                    if success:
                        last_content_type = 'signal'
                    else:
                        # Если сигналов нет, публикуем новость
                        await self.publish_news_round()
                        last_content_type = 'news'

                # Умный планировщик публикаций
                current_hour = datetime.now().hour
                if 6 <= current_hour <= 23:  # Активная публикация с 6 утра до 23 вечера
                    wait_time = random.randint(1800, 3600)  # 30-60 минут
                else:  # Ночью реже
                    wait_time = random.randint(3600, 7200)  # 1-2 часа

                logger.info(f"Следующая публикация через {wait_time // 60} минут")
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                await asyncio.sleep(300)

    async def send_message(self, text):
        """Отправка простого текстового сообщения"""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {
            'chat_id': self.channel,
            'text': text,
            'parse_mode': 'HTML'
        }

        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                logger.info("Сообщение отправлено успешно!")
                return True
            else:
                logger.error(f"Ошибка отправки: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return False

    async def send_photo_message(self, image_buffer, caption):
        """Отправка сообщения с фото в Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendPhoto"

            files = {
                'photo': ('content.png', image_buffer.getvalue(), 'image/png')
            }

            data = {
                'chat_id': self.channel,
                'caption': caption,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, files=files, data=data, timeout=30)

            if response.status_code == 200:
                logger.info("Контент отправлен успешно!")
                return True
            else:
                logger.error(f"Ошибка отправки: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending content: {e}")
            return False


async def main():
    bot = CryptoNewsBot()
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    finally:
        await bot.close_session()


if __name__ == "__main__":
    asyncio.run(main())