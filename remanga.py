import aiohttp
from urllib.parse import urljoin

from config import REMANGA_COOKIES

USER_ID = 1766758
API_ROOT = f"https://api.remanga.org/api/v2/" f"inventory/{USER_ID}/exchanges/"


class ReMangaAPIError(Exception):
    pass


class ReMangaClient:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)

        headers = {
            "Cookie": REMANGA_COOKIES,
            "Accept": "application/json",
            "Referer": "https://remanga.org/",
            "Origin": "https://remanga.org",
            "User-Agent": "Mozilla/5.0",
        }

        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
        )

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def _get_json(self, url: str) -> dict:
        if not self.session:
            raise RuntimeError("ReMangaClient is not opened")

        async with self.session.get(url) as response:
            if response.status == 401:
                raise ReMangaAPIError(
                    "ReManga вернул HTTP 401. " "Обнови REMANGA_COOKIES в .env."
                )

            if response.status != 200:
                body = (await response.text())[:300]
                raise ReMangaAPIError(
                    f"Ошибка ReManga API: HTTP {response.status}: {body}"
                )

            return await response.json()

    async def get_page(self, url: str | None = None) -> dict:
        if not url:
            url = f"{API_ROOT}?ordering=-id"
        else:
            url = urljoin("https://api.remanga.org", url)

        return await self._get_json(url)

    async def get_exchange(self, exchange_id: int) -> dict:
        return await self._get_json(f"{API_ROOT}{exchange_id}/")
