import asyncpg
from datetime import datetime, timedelta

pool = None

REVIEW_DELAYS = [
    timedelta(hours=1),
    timedelta(days=1),
    timedelta(days=4),
    timedelta(days=7),
    timedelta(days=30),
    timedelta(days=180),
]

async def init_db():
    global pool
    from dotenv import load_dotenv
    import os
    load_dotenv()
    pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            timezone_offset INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            topic TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            topic_id INTEGER REFERENCES topics(id),
            review_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending'
        );
        """)

async def get_user_id(telegram_id, offset):
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", telegram_id
        )
        if user:
            return user["id"]
        else:
            return await conn.fetchval(
                "INSERT INTO users (telegram_id, timezone_offset) VALUES ($1, $2) RETURNING id",
                telegram_id, offset
            )

async def add_topic(user_id, topic_text):
    async with pool.acquire() as conn:
        topic_id = await conn.fetchval(
            "INSERT INTO topics (user_id, topic) VALUES ($1, $2) RETURNING id",
            user_id, topic_text
        )
        now = datetime.utcnow()
        for delay in REVIEW_DELAYS:
            await conn.execute(
                "INSERT INTO reviews (topic_id, review_time) VALUES ($1, $2)",
                topic_id, now + delay
            )

async def get_progress(user_id):
    async with pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM topics WHERE user_id = $1
        """, user_id)
        pending = await conn.fetchval("""
            SELECT COUNT(*) FROM reviews 
            WHERE topic_id IN (SELECT id FROM topics WHERE user_id = $1)
            AND status = 'pending'
        """, user_id)
        return count, pending
