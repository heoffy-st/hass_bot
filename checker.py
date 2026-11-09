import asyncio
import logging

from aiogram.types import BufferedInputFile
from collage import build_exchange_collage

from database import Database
from notifications import build_exchange_notification
from remanga import ReMangaClient

POLL_INTERVAL = 60
USER_ID = 1766758


class ExchangeMonitor:
    def __init__(self, database: Database, owner_id: int):
        self.database = database
        self.owner_id = owner_id

    async def _notify(self, bot, exchange: dict, message: str):
        # Одно сообщение Telegram: коллаж + текст в подписи к фотографии.
        try:
            collage_bytes = await build_exchange_collage(exchange)
        except Exception:
            logging.exception(
                "Не удалось создать коллаж обмена %s",
                exchange.get("id"),
            )
            collage_bytes = None

        if collage_bytes:
            # Telegram ограничивает подпись к фотографии 1024 символами.
            # Если текст длиннее, оставляем обычный текст подписи без HTML-разметки
            # и сокращаем его до допустимого размера.
            caption = message
            parse_mode = "HTML"
            if len(caption) > 1024:
                import re
                from html import unescape

                caption = unescape(re.sub(r"<[^>]+>", "", caption))
                caption = caption[:1000].rstrip() + "\\n…"
                parse_mode = None

            photo = BufferedInputFile(
                collage_bytes,
                filename=f"exchange_{exchange.get('id', 'cards')}.jpg",
            )
            await bot.send_photo(
                self.owner_id,
                photo=photo,
                caption=caption,
                parse_mode=parse_mode,
            )
        else:
            # Если изображения недоступны, отправляем текстовое уведомление.
            await bot.send_message(
                self.owner_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    async def initial_sync(self):
        """Сохраняет историю без уведомлений при первом запуске."""
        saved = 0
        url = None

        async with ReMangaClient() as api:
            while True:
                page = await api.get_page(url)
                exchanges = page.get("results", [])
                for exchange in exchanges:
                    await self.database.save_exchange(exchange)
                    saved += 1

                url = page.get("next")
                if not url:
                    break

        logging.info("Первичная синхронизация завершена: %s обменов", saved)

    async def check_new_exchanges(self, bot):
        known_ids = await self.database.get_known_ids()
        url = None
        found_new = []

        async with ReMangaClient() as api:
            while True:
                page = await api.get_page(url)
                exchanges = page.get("results", [])
                if not exchanges:
                    break

                reached_known = False
                for exchange in exchanges:
                    exchange_id = int(exchange["id"])
                    if exchange_id in known_ids:
                        reached_known = True
                        break
                    found_new.append(exchange)

                if reached_known:
                    break

                url = page.get("next")
                if not url:
                    break

            # Сначала сохраняем все записи, чтобы повторный цикл не создал дубликаты.
            for exchange in reversed(found_new):
                try:
                    detailed = await api.get_exchange(int(exchange["id"]))
                except Exception:
                    logging.exception(
                        "Не удалось получить подробности обмена %s", exchange.get("id")
                    )
                    detailed = exchange
                await self.database.save_exchange(detailed)

            for exchange in reversed(found_new):
                stored = await self.database.get_exchange(int(exchange["id"]))
                detailed = stored.get("payload") if stored else exchange
                await self._notify(
                    bot,
                    detailed,
                    build_exchange_notification(detailed, "new"),
                )

        if found_new:
            logging.info("Найдено новых обменов: %s", len(found_new))

    async def check_waiting_statuses(self, bot):
        waiting_ids = await self.database.get_waiting_exchanges()
        if not waiting_ids:
            return

        async with ReMangaClient() as api:
            for exchange_id in waiting_ids:
                try:
                    latest = await api.get_exchange(exchange_id)
                    old = await self.database.get_exchange(exchange_id)
                    if not old:
                        await self.database.save_exchange(latest)
                        continue

                    old_status = old["status"]
                    new_status = latest.get("status", old_status)

                    if new_status != old_status:
                        await self.database.save_exchange(latest)
                        await self._notify(
                            bot,
                            latest,
                            build_exchange_notification(
                                latest,
                                "status",
                                old_status,
                                new_status,
                            ),
                        )
                except Exception:
                    logging.exception(
                        "Не удалось проверить статус обмена %s",
                        exchange_id,
                    )

    async def run(self, bot):
        await self.database.initialize()

        if await self.database.is_empty():
            logging.info(
                "База пуста. Выполняется первичная синхронизация без уведомлений."
            )
            async with ReMangaClient() as api:
                await api.get_page()
            await self.initial_sync()

        while True:
            try:
                await self.check_new_exchanges(bot)
                await self.check_waiting_statuses(bot)
            except Exception:
                logging.exception("Ошибка цикла мониторинга")

            await asyncio.sleep(POLL_INTERVAL)
