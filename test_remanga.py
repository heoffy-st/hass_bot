import asyncio
from remanga import ReMangaClient


async def main():
    async with ReMangaClient() as api:
        url = None
        page_number = 1
        total = 0
        waiting = []

        while True:
            data = await api.get_page(url)
            exchanges = data.get("results", [])

            total += len(exchanges)

            for exchange in exchanges:
                if exchange.get("status") == "wait":
                    waiting.append(exchange["id"])

            print(
                f"Страница {page_number}: "
                f"{len(exchanges)} обменов"
            )

            url = data.get("next")

            if not url:
                break

            page_number += 1

        print("\nВсего обменов:", total)
        print("Обменов в ожидании:", len(waiting))
        print("ID ожидающих обменов:", waiting)


if __name__ == "__main__":
    asyncio.run(main())