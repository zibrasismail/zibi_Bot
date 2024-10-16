import asyncpg
from config import DATABASE_URL

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)

async def create_messages_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                user_message TEXT,
                ai_response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

async def insert_user_message(pool, chat_id, user_message):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (chat_id, user_message) VALUES ($1, $2)",
            chat_id, user_message
        )

async def insert_ai_response(pool, chat_id, ai_response):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (chat_id, ai_response) VALUES ($1, $2)",
            chat_id, ai_response
        )
