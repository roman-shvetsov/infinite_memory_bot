import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from typing import List, Tuple, Optional
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode
from cachetools import TTLCache

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

db_pool = None
timezone_cache = TTLCache(maxsize=100, ttl=3600)  # Кэш для timezone на 1 час
chat_id_cache = TTLCache(maxsize=100, ttl=3600)  # Кэш для chat_id на 1 час

def init_db_pool():
    global db_pool
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        parsed_url = urlparse(database_url)
        query_params = parse_qs(parsed_url.query)

        if 'sslmode' not in query_params:
            query_params['sslmode'] = ['require']
        if 'connect_timeout' not in query_params:
            query_params['connect_timeout'] = ['5']

        new_query = urlencode(query_params, doseq=True)
        new_url = parsed_url._replace(query=new_query).geturl()

        db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=2,
            dsn=new_url
        )
        logger.info("Database connection pool initialized successfully")
    except psycopg2.Error as e:
        logger.error(f"Error initializing database pool: {e}")
        raise
    except Exception as e:
        logger.error(f"Error parsing DATABASE_URL: {e}")
        raise

def get_db_connection():
    global db_pool
    if db_pool is None:
        init_db_pool()
    try:
        conn = db_pool.getconn()
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error getting connection from pool: {e}")
        raise

def release_db_connection(conn):
    global db_pool
    if db_pool and conn:
        try:
            db_pool.putconn(conn)
        except psycopg2.Error as e:
            logger.error(f"Error releasing connection to pool: {e}")

def close_db_pool():
    global db_pool
    if db_pool:
        try:
            db_pool.closeall()
            logger.info("Database connection pool closed")
        except psycopg2.Error as e:
            logger.error(f"Error closing database pool: {e}")
        finally:
            db_pool = None

def init_db() -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        firstname TEXT NOT NULL,
                        timezone TEXT NOT NULL,
                        chat_id BIGINT
                    );
                    CREATE TABLE IF NOT EXISTS topics (
                        topic_id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(user_id),
                        title TEXT NOT NULL,
                        is_paused BOOLEAN DEFAULT FALSE
                    );
                    CREATE TABLE IF NOT EXISTS reminders (
                        reminder_id SERIAL PRIMARY KEY,
                        topic_id INTEGER NOT NULL REFERENCES topics(topic_id),
                        scheduled_time TIMESTAMP NOT NULL,
                        repetition_count INTEGER NOT NULL DEFAULT 0,
                        is_processed BOOLEAN NOT NULL DEFAULT FALSE,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        sent_time TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_scheduled_time ON reminders(scheduled_time);
                    CREATE INDEX IF NOT EXISTS idx_is_processed ON reminders(is_processed);
                    CREATE INDEX IF NOT EXISTS idx_status ON reminders(status);
                    CREATE INDEX IF NOT EXISTS idx_is_paused ON topics(is_paused);
                    CREATE INDEX IF NOT EXISTS idx_user_id ON topics(user_id);
                """)
                conn.commit()
                logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        release_db_connection(conn)

def add_user(user_id: int, username: str, firstname: str, timezone: str, chat_id: int = None) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, username, firstname, timezone, chat_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        firstname = EXCLUDED.firstname,
                        timezone = EXCLUDED.timezone,
                        chat_id = EXCLUDED.chat_id
                    """,
                    (user_id, username, firstname, timezone, chat_id)
                )
                conn.commit()
                timezone_cache[user_id] = timezone
                if chat_id:
                    chat_id_cache[user_id] = chat_id
                logger.info(f"User {user_id} added/updated with timezone {timezone}")
    finally:
        release_db_connection(conn)

def get_user_timezone(user_id: int) -> Optional[str]:
    cached_timezone = timezone_cache.get(user_id)
    if cached_timezone is not None:
        logger.info(f"Returning cached timezone {cached_timezone} for user {user_id}")
        return cached_timezone
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT timezone FROM users WHERE user_id = %s", (user_id,))
                result = cur.fetchone()
                timezone = result[0] if result else None
                if timezone:
                    timezone_cache[user_id] = timezone
                return timezone
    finally:
        release_db_connection(conn)

def get_user_chat_id(user_id: int) -> Optional[int]:
    cached_chat_id = chat_id_cache.get(user_id)
    if cached_chat_id is not None:
        logger.info(f"Returning cached chat_id {cached_chat_id} for user {user_id}")
        return cached_chat_id
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chat_id FROM users WHERE user_id = %s", (user_id,))
                result = cur.fetchone()
                chat_id = result[0] if result else None
                if chat_id:
                    chat_id_cache[user_id] = chat_id
                return chat_id
    finally:
        release_db_connection(conn)

def add_topic(user_id: int, title: str) -> int:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO topics (user_id, title) VALUES (%s, %s) RETURNING topic_id",
                    (user_id, title)
                )
                topic_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Added topic '{title}' for user {user_id} with topic_id {topic_id}")
                return topic_id
    finally:
        release_db_connection(conn)

def schedule_reminder(topic_id: int, scheduled_time: datetime, repetition_count: int = 0,
                      status: str = "PENDING") -> int:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reminders (topic_id, scheduled_time, repetition_count, is_processed, status)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING reminder_id
                    """,
                    (topic_id, scheduled_time, repetition_count, False, status)
                )
                reminder_id = cur.fetchone()[0]
                conn.commit()
                logger.info(
                    f"Scheduled reminder: topic_id={topic_id}, reminder_id={reminder_id}, scheduled_time={scheduled_time}, repetition_count={repetition_count}, status={status}")
                return reminder_id
    finally:
        release_db_connection(conn)

def mark_reminder_processed(reminder_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reminders SET is_processed = TRUE, status = 'PROCESSED' WHERE reminder_id = %s",
                    (reminder_id,)
                )
                conn.commit()
                logger.info(f"Marked reminder {reminder_id} as processed")
    finally:
        release_db_connection(conn)

def mark_reminder_sent(reminder_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reminders SET status = 'SENT', sent_time = NOW() WHERE reminder_id = %s",
                    (reminder_id,)
                )
                conn.commit()
                logger.info(f"Marked reminder {reminder_id} as sent")
    finally:
        release_db_connection(conn)

def is_reminder_processed(reminder_id: int) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_processed FROM reminders WHERE reminder_id = %s",
                    (reminder_id,)
                )
                result = cur.fetchone()
                return result[0] if result else False
    finally:
        release_db_connection(conn)

def get_reminder_scheduled_time(reminder_id: int) -> Optional[datetime]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT scheduled_time FROM reminders WHERE reminder_id = %s",
                    (reminder_id,)
                )
                result = cur.fetchone()
                return result[0] if result else None
    finally:
        release_db_connection(conn)

def get_reminder_repetition_count(reminder_id: int) -> int:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT repetition_count FROM reminders WHERE reminder_id = %s",
                    (reminder_id,)
                )
                result = cur.fetchone()
                return result[0] if result else 0
    finally:
        release_db_connection(conn)

def get_topic_repetition_count(topic_id: int) -> int:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(
                        MAX(repetition_count),
                        0
                    ) FROM reminders
                    WHERE topic_id = %s
                    AND status = 'PROCESSED'
                    """,
                    (topic_id,)
                )
                result = cur.fetchone()
                logger.info(f"Returning repetition_count={result[0]} for topic {topic_id}")
                return result[0]
    finally:
        release_db_connection(conn)

def get_overdue_reminders() -> List[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        r.reminder_id, r.topic_id, t.user_id, t.title, r.scheduled_time,
                        r.repetition_count, u.chat_id
                    FROM reminders r
                    JOIN topics t ON r.topic_id = t.topic_id
                    JOIN users u ON t.user_id = u.user_id
                    WHERE r.scheduled_time <= NOW()
                    AND t.is_paused = FALSE
                    AND r.is_processed = FALSE
                    AND r.status = 'PENDING'
                    """
                )
                reminders = cur.fetchall()
                logger.info(f"Retrieved {len(reminders)} overdue reminders")
                return reminders
    finally:
        release_db_connection(conn)

def get_all_pending_reminders() -> List[dict]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        r.reminder_id, r.topic_id, t.user_id, t.title, r.scheduled_time,
                        r.repetition_count, u.chat_id
                    FROM reminders r
                    JOIN topics t ON r.topic_id = t.topic_id
                    JOIN users u ON t.user_id = u.user_id
                    WHERE r.is_processed = FALSE
                    AND r.status = 'PENDING'
                    AND r.scheduled_time >= NOW()
                    """
                )
                reminders = cur.fetchall()
                logger.info(f"Retrieved {len(reminders)} pending reminders")
                return reminders
    finally:
        release_db_connection(conn)

def update_awaiting_reminders() -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE reminders
                    SET status = 'AWAITING'
                    WHERE status = 'SENT'
                    AND sent_time <= NOW() - INTERVAL '1 day'
                    AND is_processed = FALSE
                    """
                )
                updated = cur.rowcount
                conn.commit()
                logger.info(f"Updated {updated} reminders to AWAITING status")
    finally:
        release_db_connection(conn)

def clear_unprocessed_reminders(topic_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM reminders
                    WHERE topic_id = %s
                    AND is_processed = FALSE
                    """,
                    (topic_id,)
                )
                conn.commit()
                logger.info(f"Cleared unprocessed reminders for topic {topic_id}")
    finally:
        release_db_connection(conn)

def delete_topic(topic_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM reminders WHERE topic_id = %s", (topic_id,))
                cur.execute("DELETE FROM topics WHERE topic_id = %s", (topic_id,))
                conn.commit()
                logger.info(f"Deleted topic {topic_id} and its reminders")
    finally:
        release_db_connection(conn)

def pause_topic(topic_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE topics
                    SET is_paused = TRUE
                    WHERE topic_id = %s
                    """,
                    (topic_id,)
                )
                conn.commit()
                logger.info(f"Paused topic {topic_id}")
    finally:
        release_db_connection(conn)

def resume_topic(topic_id: int) -> None:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE topics
                    SET is_paused = FALSE
                    WHERE topic_id = %s
                    """,
                    (topic_id,)
                )
                conn.commit()
                logger.info(f"Resumed topic {topic_id}")
    finally:
        release_db_connection(conn)

def get_all_topics(user_id: int) -> List[Tuple[int, str, bool]]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT topic_id, title, is_paused
                    FROM topics
                    WHERE user_id = %s
                    ORDER BY topic_id
                    """,
                    (user_id,)
                )
                return [(row[0], row[1], row[2]) for row in cur.fetchall()]
    finally:
        release_db_connection(conn)

def get_active_topics(user_id: int) -> List[Tuple[int, str]]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT topic_id, title
                    FROM topics
                    WHERE user_id = %s
                    AND is_paused = FALSE
                    ORDER BY topic_id
                    """,
                    (user_id,)
                )
                return [(row[0], row[1]) for row in cur.fetchall()]
    finally:
        release_db_connection(conn)

def get_paused_topics(user_id: int) -> List[Tuple[int, str]]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT topic_id, title
                    FROM topics
                    WHERE user_id = %s
                    AND is_paused = TRUE
                    ORDER BY topic_id
                    """,
                    (user_id,)
                )
                return [(row[0], row[1]) for row in cur.fetchall()]
    finally:
        release_db_connection(conn)

def get_user_progress(user_id: int) -> List[Tuple[str, int, Optional[datetime], bool, str]]:
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH processed_reminders AS (
                        SELECT topic_id, COUNT(*) as repetitions
                        FROM reminders
                        WHERE status = 'PROCESSED'
                        GROUP BY topic_id
                    ),
                    next_reminder AS (
                        SELECT topic_id,
                               MIN(scheduled_time) as next_scheduled_time,
                               MAX(status) as status
                        FROM reminders
                        WHERE is_processed = FALSE
                        AND status IN ('PENDING', 'SENT')
                        AND scheduled_time > NOW()
                        GROUP BY topic_id
                    )
                    SELECT t.title,
                           COALESCE(pr.repetitions, 0),
                           nr.next_scheduled_time,
                           t.is_paused,
                           COALESCE(nr.status, 'NO_PENDING')
                    FROM topics t
                    LEFT JOIN processed_reminders pr ON t.topic_id = pr.topic_id
                    LEFT JOIN next_reminder nr ON t.topic_id = nr.topic_id
                    WHERE t.user_id = %s
                    ORDER BY t.topic_id
                    """,
                    (user_id,)
                )
                return [(row[0], row[1], row[2], row[3], row[4]) for row in cur.fetchall()]
    finally:
        release_db_connection(conn)