import asyncio
import logging

from database import Database
from remanga import ReMangaClient


async def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    db = Database()
    await db.initialize()

    total = 0
    unique_ids = set()
    waiting_ids = set()
    url = None
    page_number = 0

    async with ReMangaClient() as api:
        while True:
            data = await api.get_page(url)
            exchanges = data.get("results", [])
            page_number += 1

            for exchange in exchanges:
                exchange_id = int(exchange["id"])
                if exchange_id in unique_ids:
                    continue

                unique_ids.add(exchange_id)
                await db.save_exchange(exchange)
                total += 1

                if exchange.get("status") == "wait":
                    waiting_ids.add(exchange_id)

            print(
                f"Страница {page_number}: получено {len(exchanges)}, "
                f"уникальных сохранено {total}"
            )

            url = data.get("next")
            if not url:
                break

    print("\\nСинхронизация завершена.")
    print("Уникальных обменов загружено:", total)
    print("Ожидающих обменов:", len(waiting_ids))
    print("ID ожидающих:", sorted(waiting_ids, reverse=True))
    print("Всего записей в базе:", await db.count())


if __name__ == "__main__":
    asyncio.run(main())
