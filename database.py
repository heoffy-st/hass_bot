import json
import os
import aiosqlite

DB_PATH = "data/remanga.db"


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path

    async def initialize(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS exchanges (
                    id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT,
                    payload TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_exchanges_status
                ON exchanges(status)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_exchanges_created
                ON exchanges(created_at DESC)
            """)
            await db.commit()

    async def is_empty(self) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM exchanges")
            row = await cursor.fetchone()
            return row[0] == 0

    async def get_known_ids(self) -> set[int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT id FROM exchanges")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    async def save_exchange(self, exchange: dict):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO exchanges (id, status, created_at, payload, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    created_at = excluded.created_at,
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                int(exchange["id"]),
                exchange.get("status", "unknown"),
                exchange.get("created_at"),
                json.dumps(exchange, ensure_ascii=False),
            ))
            await db.commit()

    async def get_exchange(self, exchange_id: int):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT status, payload FROM exchanges WHERE id = ?",
                (exchange_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {"status": row[0], "payload": json.loads(row[1])}

    async def get_waiting_exchanges(self) -> list[int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT id FROM exchanges WHERE status = 'wait' ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def count(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM exchanges")
            row = await cursor.fetchone()
            return row[0]

    async def status_counts(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) FROM exchanges GROUP BY status"
            )
            return {status: count for status, count in await cursor.fetchall()}

    async def get_recent(self, limit: int = 10) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT id, status, created_at, payload FROM exchanges "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "payload": json.loads(row[3]),
                }
                for row in rows
            ]

    async def search_exchange(self, exchange_id: int):
        return await self.get_exchange(exchange_id)
