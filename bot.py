import asyncio
import logging
from datetime import datetime
from html import escape

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from config import BOT_TOKEN, OWNER_ID
from database import Database
from checker import ExchangeMonitor
from notifications import build_exchange_notification, STATUS_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
database = Database()


def is_owner(message: Message) -> bool:
    return OWNER_ID is not None and message.from_user is not None and message.from_user.id == OWNER_ID


def format_date(value):
    if not value:
        return "дата не указана"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def get_usernames(exchange):
    creator = exchange.get("creator") or {}
    partner = exchange.get("partner") or {}
    return (
        creator.get("username") or creator.get("name") or str(creator.get("id") or "Unknown"),
        partner.get("username") or partner.get("name") or str(partner.get("id") or "Unknown"),
    )


@dp.message(CommandStart())
async def start(message: Message):
    if OWNER_ID is None:
        await message.answer(
            "Ваш Telegram ID: "
            f"{message.from_user.id}\n\n"
            "Добавьте его в .env в строку OWNER_ID= и перезапустите бота."
        )
        return

    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return

    await message.answer(
        "<b>ReManga Exchange Bot</b>\n\n"
        "Мониторинг обменов работает каждую минуту.\n\n"
        "<b>Команды:</b>\n"
        "/status — состояние бота\n"
        "/stats — статистика обменов\n"
        "/history — последние 10 обменов\n"
        "/waiting — обмены, ожидающие ответа\n"
        "/search ID — найти обмен\n"
        "/exchange ID — подробности обмена",
        parse_mode="HTML",
    )


@dp.message(Command("status"))
async def status(message: Message):
    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return

    count = await database.count()
    waiting = len(await database.get_waiting_exchanges())
    await message.answer(
        "Статус: бот работает.\n"
        "Мониторинг: каждую минуту.\n"
        f"Обменов в базе: {count}\n"
        f"Ожидают ответа: {waiting}"
    )


@dp.message(Command("stats"))
async def stats(message: Message):
    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return

    counts = await database.status_counts()
    total = sum(counts.values())
    labels = {
        "wait": "⏳ Ожидают ответа",
        "accepted": "✅ Приняты",
        "denied": "❌ Отклонены",
        "canceled": "🚫 Отменены",
    }
    lines = ["<b>Статистика обменов</b>", f"Всего в базе: <b>{total}</b>"]
    for status_code, label in labels.items():
        lines.append(f"{label}: <b>{counts.get(status_code, 0)}</b>")
    other = total - sum(counts.get(code, 0) for code in labels)
    if other:
        lines.append(f"Другие статусы: <b>{other}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("history"))
async def history(message: Message):
    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return

    records = await database.get_recent(10)
    if not records:
        await message.answer("История пока пуста.")
        return

    lines = ["<b>Последние обмены</b>"]
    for record in records:
        creator, partner = get_usernames(record["payload"])
        status_label = STATUS_NAMES.get(record["status"], record["status"])
        lines.append(
            f"\n<b>#{record['id']}</b> — {escape(status_label)}\n"
            f"{escape(creator)} → {escape(partner)}\n"
            f"🕒 {escape(format_date(record['created_at']))}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("waiting"))
async def waiting(message: Message):
    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return

    ids = await database.get_waiting_exchanges()
    if not ids:
        await message.answer("Нет обменов, ожидающих ответа.")
        return

    lines = [f"<b>Ожидают ответа: {len(ids)}</b>"]
    for exchange_id in ids[:30]:
        record = await database.get_exchange(exchange_id)
        if not record:
            continue
        creator, partner = get_usernames(record["payload"])
        lines.append(f"• <code>#{exchange_id}</code> — {escape(creator)} → {escape(partner)}")
    if len(ids) > 30:
        lines.append(f"\n… и ещё {len(ids) - 30}")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def show_exchange(message: Message, command_text: str):
    parts = (command_text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Укажи ID обмена. Пример: /search 1043253")
        return
    exchange_id = int(parts[1])
    record = await database.search_exchange(exchange_id)
    if not record:
        await message.answer(f"Обмен #{exchange_id} не найден в базе.")
        return
    payload = record["payload"]
    # Детальная карточка выводится обычным текстовым сообщением, без коллажа.
    await message.answer(
        build_exchange_notification(payload, "new"),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@dp.message(Command("search"))
async def search(message: Message):
    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return
    await show_exchange(message, message.text or "")


@dp.message(Command("exchange"))
async def exchange(message: Message):
    if not is_owner(message):
        await message.answer("Доступ запрещён.")
        return
    await show_exchange(message, message.text or "")


async def main():
    await database.initialize()
    print("ReManga Exchange Bot запущен")

    monitor_task = None
    if OWNER_ID is None:
        logging.warning("OWNER_ID не задан. Мониторинг не запущен.")
    else:
        monitor = ExchangeMonitor(database, OWNER_ID)
        monitor_task = asyncio.create_task(monitor.run(bot))

    try:
        await dp.start_polling(bot)
    finally:
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
