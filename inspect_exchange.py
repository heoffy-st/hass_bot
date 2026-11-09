import asyncio
import json
from remanga import ReMangaClient


async def main():
    async with ReMangaClient() as api:
        data = await api.get_exchange(1041628)

        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
