from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from datetime import datetime, timedelta
import pytz
import logging
from dotenv import load_dotenv

# Load .env file
load_dotenv()

Base = declarative_base()
logger = logging.getLogger(__name__)

class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    timezone = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))

class Topic(Base):
    __tablename__ = "topics"
    topic_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True)
    topic_name = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    last_reviewed = Column(DateTime(timezone=True))
    next_review = Column(DateTime(timezone=True), index=True)
    repetition_stage = Column(Integer, default=0)
    completed_repetitions = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)

class DeletedTopic(Base):
    __tablename__ = "deleted_topics"
    deleted_topic_id = Column(Integer, primary_key=True)
    topic_id = Column(Integer)
    user_id = Column(BigInteger)
    topic_name = Column(String(255))
    deleted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))

class Reminder(Base):
    __tablename__ = "reminders"
    reminder_id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, index=True)
    user_id = Column(BigInteger, index=True)
    scheduled_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))

class Database:
    def __init__(self):
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not set in environment variables")

        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://")

        try:
            self.engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=2,
                max_overflow=2,
                pool_timeout=30,
                pool_pre_ping=True,
            )
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            logger.debug("Database connection established")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_user(self, user_id: int):
        try:
            with self.Session() as session:
                user = session.query(User).filter_by(user_id=user_id).first()
                logger.debug(f"Queried user {user_id}: {'found' if user else 'not found'}")
                return user
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise

    def get_all_users(self):
        try:
            with self.Session() as session:
                users = session.query(User).all()
                logger.debug(f"Found {len(users)} users")
                return users
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            raise

    def save_user(self, user_id: int, username: str, timezone: str):
        try:
            with self.Session() as session:
                logger.debug(f"Saving user {user_id} with timezone {timezone}")
                user = session.query(User).filter_by(user_id=user_id).first()
                if not user:
                    user = User(user_id=user_id, username=username, timezone=timezone)
                    session.add(user)
                    logger.debug(f"Created new user {user_id}")
                else:
                    user.timezone = timezone
                    user.username = username
                    logger.debug(f"Updated user {user_id}")
                session.commit()
                logger.debug(f"User {user_id} saved successfully")
        except Exception as e:
            logger.error(f"Error saving user {user_id}: {e}")
            raise

    def add_topic(self, user_id: int, topic_name: str, timezone: str):
        try:
            with self.Session() as session:
                tz = pytz.timezone(timezone)
                now = datetime.now(tz).astimezone(tz)
                logger.debug(f"Creating topic '{topic_name}' with now={now.isoformat()}")
                topic = Topic(
                    user_id=user_id,
                    topic_name=topic_name,
                    created_at=now,
                    next_review=now + timedelta(hours=1),
                    repetition_stage=0,
                    completed_repetitions=0,
                )
                session.add(topic)
                session.flush()
                topic_id = topic.topic_id
                reminder = Reminder(
                    topic_id=topic_id,
                    user_id=user_id,
                    scheduled_time=now + timedelta(hours=1)
                )
                session.add(reminder)
                logger.debug(f"Added first reminder for topic '{topic_name}' at {(now + timedelta(hours=1)).isoformat()}")
                session.commit()
                logger.debug(f"Topic '{topic_name}' and first reminder added for user {user_id}, first review: {topic.next_review.isoformat()}")
                return topic_id
        except Exception as e:
            logger.error(f"Error adding topic '{topic_name}' for user {user_id}: {e}")
            raise

    def get_active_topics(self, user_id: int, timezone: str):
        try:
            with self.Session() as session:
                topics = session.query(Topic).filter_by(user_id=user_id, is_completed=False).all()
                tz = pytz.timezone(timezone)
                for topic in topics:
                    if topic.next_review:
                        logger.debug(f"Raw next_review for topic '{topic.topic_name}': {topic.next_review.isoformat()}, tzinfo: {topic.next_review.tzinfo}")
                        if topic.next_review.tzinfo is None:
                            topic.next_review = topic.next_review.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif topic.next_review.tzinfo != tz:
                            topic.next_review = topic.next_review.astimezone(tz)
                    if topic.last_reviewed:
                        if topic.last_reviewed.tzinfo is None:
                            topic.last_reviewed = topic.last_reviewed.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif topic.last_reviewed.tzinfo != tz:
                            topic.last_reviewed = topic.last_reviewed.astimezone(tz)
                logger.debug(f"Found {len(topics)} active topics for user {user_id}")
                return topics
        except Exception as e:
            logger.error(f"Error fetching topics for user {user_id}: {e}")
            raise

    def get_topic(self, topic_id: int, user_id: int, timezone: str):
        try:
            with self.Session() as session:
                topic = session.query(Topic).filter_by(topic_id=topic_id, user_id=user_id).first()
                if topic:
                    tz = pytz.timezone(timezone)
                    if topic.next_review:
                        logger.debug(f"Raw next_review for topic {topic_id}: {topic.next_review.isoformat()}, tzinfo: {topic.next_review.tzinfo}")
                        if topic.next_review.tzinfo is None:
                            topic.next_review = topic.next_review.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif topic.next_review.tzinfo != tz:
                            topic.next_review = topic.next_review.astimezone(tz)
                    if topic.last_reviewed:
                        if topic.last_reviewed.tzinfo is None:
                            topic.last_reviewed = topic.last_reviewed.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif topic.last_reviewed.tzinfo != tz:
                            topic.last_reviewed = topic.last_reviewed.astimezone(tz)
                logger.debug(f"Queried topic {topic_id} for user {user_id}: {'found' if topic else 'not found'}")
                return topic
        except Exception as e:
            logger.error(f"Error fetching topic {topic_id}: {e}")
            raise

    def get_topic_by_name(self, user_id: int, topic_name: str, timezone: str):
        try:
            with self.Session() as session:
                topic = session.query(Topic).filter_by(user_id=user_id, topic_name=topic_name).first()
                if topic:
                    tz = pytz.timezone(timezone)
                    if topic.next_review:
                        if topic.next_review.tzinfo is None:
                            topic.next_review = topic.next_review.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif topic.next_review.tzinfo != tz:
                            topic.next_review = topic.next_review.astimezone(tz)
                    if topic.last_reviewed:
                        if topic.last_reviewed.tzinfo is None:
                            topic.last_reviewed = topic.last_reviewed.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif topic.last_reviewed.tzinfo != tz:
                            topic.last_reviewed = topic.last_reviewed.astimezone(tz)
                logger.debug(f"Queried topic '{topic_name}' for user {user_id}: {'found' if topic else 'not found'}")
                return topic
        except Exception as e:
            logger.error(f"Error fetching topic '{topic_name}' for user {user_id}: {e}")
            raise

    def get_reminders(self, user_id: int, timezone: str):
        try:
            with self.Session() as session:
                reminders = session.query(Reminder).filter_by(user_id=user_id).all()
                tz = pytz.timezone(timezone)
                for reminder in reminders:
                    if reminder.scheduled_time:
                        if reminder.scheduled_time.tzinfo is None:
                            reminder.scheduled_time = reminder.scheduled_time.replace(tzinfo=pytz.UTC).astimezone(tz)
                        elif reminder.scheduled_time.tzinfo != tz:
                            reminder.scheduled_time = reminder.scheduled_time.astimezone(tz)
                logger.debug(f"Found {len(reminders)} reminders for user {user_id}")
                return reminders
        except Exception as e:
            logger.error(f"Error fetching reminders for user {user_id}: {e}")
            raise

    def delete_topic(self, topic_id: int, user_id: int, topic_name: str):
        try:
            with self.Session() as session:
                topic = session.query(Topic).filter_by(topic_id=topic_id, user_id=user_id).first()
                if topic:
                    # Удаляем все напоминания, связанные с этой темой
                    session.query(Reminder).filter_by(topic_id=topic_id, user_id=user_id).delete()
                    # Переносим тему в deleted_topics
                    deleted_topic = DeletedTopic(
                        topic_id=topic_id,
                        user_id=user_id,
                        topic_name=topic_name,
                        deleted_at=datetime.now(pytz.UTC),
                    )
                    session.add(deleted_topic)
                    session.delete(topic)
                    session.commit()
                    logger.debug(f"Topic '{topic_name}' (id: {topic_id}) and its reminders deleted for user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting topic {topic_id}: {e}")
            session.rollback()
            raise

    def complete_reminder(self, reminder_id: int, user_id: int, timezone: str):
        try:
            with self.Session() as session:
                reminder = session.query(Reminder).filter_by(reminder_id=reminder_id, user_id=user_id).first()
                if not reminder:
                    logger.warning(f"Reminder {reminder_id} not found for user {user_id}")
                    return None
                topic = session.query(Topic).filter_by(topic_id=reminder.topic_id, user_id=user_id).first()
                if not topic:
                    logger.warning(f"Topic {reminder.topic_id} not found for user {user_id} for reminder {reminder_id}")
                    session.delete(reminder)
                    session.commit()
                    return None
                tz = pytz.timezone(timezone)
                now = datetime.now(tz).astimezone(tz)
                topic.completed_repetitions += 1
                topic.last_reviewed = now
                topic.repetition_stage += 1
                review_intervals = [timedelta(hours=1), timedelta(days=1), timedelta(days=3),
                                  timedelta(days=7), timedelta(days=14), timedelta(days=30)]
                new_reminder_id = None
                if topic.repetition_stage < len(review_intervals):
                    topic.next_review = now + review_intervals[topic.repetition_stage]
                    new_reminder = Reminder(
                        topic_id=topic.topic_id,
                        user_id=user_id,
                        scheduled_time=topic.next_review
                    )
                    session.add(new_reminder)
                    session.flush()
                    new_reminder_id = new_reminder.reminder_id
                else:
                    topic.is_completed = True
                    topic.next_review = None
                session.delete(reminder)
                session.commit()
                logger.debug(f"Completed reminder {reminder_id} for topic '{topic.topic_name}' (id: {topic.topic_id}), "
                            f"repetitions: {topic.completed_repetitions}/6, next_review: {topic.next_review.isoformat() if topic.next_review else 'None'}")
                return topic, new_reminder_id
        except Exception as e:
            logger.error(f"Error completing reminder {reminder_id} for user {user_id}: {e}")
            session.rollback()
            raise