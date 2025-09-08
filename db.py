from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool
from datetime import datetime, timedelta
import pytz
import logging
from dotenv import load_dotenv
import os
import tenacity
from sqlalchemy.exc import OperationalError

# Загрузка переменных окружения
load_dotenv()

Base = declarative_base()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    timezone = Column(String)

class Topic(Base):
    __tablename__ = 'topics'
    topic_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    category_id = Column(Integer, ForeignKey('categories.category_id'), nullable=True)
    topic_name = Column(String)
    created_at = Column(DateTime)
    last_reviewed = Column(DateTime)
    next_review = Column(DateTime)
    repetition_stage = Column(Integer)
    completed_repetitions = Column(Integer)
    is_completed = Column(Boolean)
    user = relationship("User")
    category = relationship("Category", back_populates="topics")

class Reminder(Base):
    __tablename__ = 'reminders'
    reminder_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    topic_id = Column(Integer, ForeignKey('topics.topic_id'))
    scheduled_time = Column(DateTime)

class CompletedTopic(Base):
    __tablename__ = 'completed_topics'
    completed_topic_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    topic_name = Column(String)
    category_id = Column(Integer, ForeignKey('categories.category_id'), nullable=True)
    completed_at = Column(DateTime)
    user = relationship("User")
    category = relationship("Category")

class Category(Base):
    __tablename__ = 'categories'
    category_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    category_name = Column(String)
    user = relationship("User")
    topics = relationship("Topic", back_populates="category")

class Database:
    def __init__(self):
        self.engine = create_engine(
            os.getenv('DATABASE_URL'),
            echo=True,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _to_utc_naive(self, dt, tz_str):
        tz = pytz.timezone(tz_str)
        return dt.astimezone(pytz.utc).replace(tzinfo=None)

    def _from_utc_naive(self, dt_utc, tz_str):
        if dt_utc is None:
            return None
        if dt_utc.tzinfo is not None:
            dt_utc = dt_utc.replace(tzinfo=None)
        tz = pytz.timezone(tz_str)
        return pytz.utc.localize(dt_utc).astimezone(tz)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def save_user(self, user_id, username, timezone):
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.username = username
                user.timezone = timezone
            else:
                user = User(user_id=user_id, username=username, timezone=timezone)
                session.add(user)
            session.commit()
            logger.debug(f"User {user_id} saved with timezone {timezone}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving user {user_id}: {str(e)}")
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_user(self, user_id):
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            return user
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def add_topic(self, user_id, topic_name, timezone, category_id=None):
        session = self.Session()
        try:
            tz = pytz.timezone(timezone)
            now_local = datetime.now(tz)
            now_utc = self._to_utc_naive(now_local, timezone)
            next_review_local = now_local + timedelta(hours=1)
            next_review_utc = self._to_utc_naive(next_review_local, timezone)
            topic = Topic(
                user_id=user_id,
                category_id=category_id,
                topic_name=topic_name,
                created_at=now_utc,
                last_reviewed=None,
                next_review=next_review_utc,
                repetition_stage=1,
                completed_repetitions=0,
                is_completed=False
            )
            session.add(topic)
            session.flush()
            reminder = Reminder(
                user_id=user_id,
                topic_id=topic.topic_id,
                scheduled_time=next_review_utc
            )
            session.add(reminder)
            session.flush()
            session.commit()
            return topic.topic_id, reminder.reminder_id
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_active_topics(self, user_id, timezone, category_id=None):
        session = self.Session()
        try:
            query = session.query(Topic).filter_by(user_id=user_id, is_completed=False)
            if category_id == 'all':
                pass
            elif category_id is not None:
                query = query.filter(Topic.category_id == category_id)
            else:
                query = query.filter(Topic.category_id.is_(None))
            topics = query.order_by(Topic.created_at).all()
            for topic in topics:
                topic.next_review = topic.next_review  # remains utc naive
            return topics
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_topic(self, topic_id, user_id, timezone):
        session = self.Session()
        try:
            topic = session.query(Topic).filter_by(topic_id=topic_id, user_id=user_id).first()
            if topic:
                topic.next_review = topic.next_review  # utc naive
            return topic
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_topic_by_name(self, user_id, topic_name, timezone):
        session = self.Session()
        try:
            topic = session.query(Topic).filter_by(user_id=user_id, topic_name=topic_name).first()
            if topic:
                topic.next_review = topic.next_review
            return topic
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_topic_by_reminder_id(self, reminder_id, user_id, timezone):
        session = self.Session()
        try:
            reminder = session.query(Reminder).filter_by(reminder_id=reminder_id, user_id=user_id).first()
            if reminder:
                topic = session.query(Topic).filter_by(topic_id=reminder.topic_id, user_id=user_id).first()
                if topic:
                    topic.next_review = topic.next_review
                return topic
            return None
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def delete_topic(self, topic_id, user_id):
        session = self.Session()
        try:
            topic = session.query(Topic).filter_by(topic_id=topic_id, user_id=user_id).first()
            if topic:
                session.query(Reminder).filter_by(topic_id=topic_id).delete()
                session.delete(topic)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_completed_topics(self, user_id):
        session = self.Session()
        try:
            completed_topics = session.query(CompletedTopic).filter_by(user_id=user_id).all()
            return completed_topics
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def restore_topic(self, completed_topic_id, user_id, timezone):
        session = self.Session()
        try:
            completed_topic = session.query(CompletedTopic).filter_by(completed_topic_id=completed_topic_id, user_id=user_id).first()
            if completed_topic:
                tz = pytz.timezone(timezone)
                now_local = datetime.now(tz)
                now_utc = self._to_utc_naive(now_local, timezone)
                next_review_local = now_local + timedelta(hours=1)
                next_review_utc = self._to_utc_naive(next_review_local, timezone)
                topic = Topic(
                    user_id=user_id,
                    topic_name=completed_topic.topic_name,
                    category_id=completed_topic.category_id,
                    created_at=now_utc,
                    last_reviewed=None,
                    next_review=next_review_utc,
                    repetition_stage=1,
                    completed_repetitions=0,
                    is_completed=False
                )
                session.add(topic)
                session.flush()
                reminder = Reminder(
                    user_id=user_id,
                    topic_id=topic.topic_id,
                    scheduled_time=next_review_utc
                )
                session.add(reminder)
                session.delete(completed_topic)
                session.commit()
                return topic.topic_id, topic.topic_name
            return None
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def add_category(self, user_id, category_name):
        session = self.Session()
        try:
            category = Category(user_id=user_id, category_name=category_name)
            session.add(category)
            session.commit()
            return category.category_id
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_categories(self, user_id):
        session = self.Session()
        try:
            categories = session.query(Category).filter_by(user_id=user_id).all()
            return categories
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_category(self, category_id, user_id):
        session = self.Session()
        try:
            category = session.query(Category).filter_by(category_id=category_id, user_id=user_id).first()
            return category
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def rename_category(self, category_id, user_id, new_name):
        session = self.Session()
        try:
            category = session.query(Category).filter_by(category_id=category_id, user_id=user_id).first()
            if category:
                category.category_name = new_name
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def delete_category(self, category_id, user_id):
        session = self.Session()
        try:
            category = session.query(Category).filter_by(category_id=category_id, user_id=user_id).first()
            if category:
                # Move topics to none
                session.query(Topic).filter_by(category_id=category_id).update({Topic.category_id: None})
                session.delete(category)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def move_topic_to_category(self, topic_id, user_id, category_id):
        session = self.Session()
        try:
            topic = session.query(Topic).filter_by(topic_id=topic_id, user_id=user_id).first()
            if topic:
                topic.category_id = category_id if category_id != 'none' else None
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def mark_topic_repeated(self, user_id, topic_name, timezone):
        session = self.Session()
        try:
            topic = session.query(Topic).filter_by(user_id=user_id, topic_name=topic_name, is_completed=False).first()
            if not topic:
                return None
            tz = pytz.timezone(timezone)
            now_local = datetime.now(tz)
            now_utc = self._to_utc_naive(now_local, timezone)
            topic.last_reviewed = now_utc
            topic.completed_repetitions += 1
            topic.repetition_stage = topic.completed_repetitions + 1

            intervals = [1, 1, 3, 7, 14, 30, 90]  # days
            if topic.completed_repetitions < len(intervals):
                next_review_local = now_local + timedelta(days=intervals[topic.completed_repetitions])

                # Обновляем существующее напоминание вместо удаления
                existing_reminder = session.query(Reminder).filter_by(topic_id=topic.topic_id).first()
                if existing_reminder:
                    existing_reminder.scheduled_time = topic.next_review
                    reminder_id = existing_reminder.reminder_id
                else:
                    new_reminder = Reminder(
                        user_id=user_id,
                        topic_id=topic.topic_id,
                        scheduled_time=topic.next_review
                    )
                    session.add(new_reminder)
                    session.flush()
                    reminder_id = new_reminder.reminder_id
            else:
                topic.is_completed = True
                topic.next_review = None
                completed_topic = CompletedTopic(
                    user_id=user_id,
                    topic_name=topic.topic_name,
                    category_id=topic.category_id,
                    completed_at=now_utc
                )
                session.add(completed_topic)
                reminder_id = None

            session.commit()
            return topic.topic_id, topic.completed_repetitions, topic.next_review, reminder_id
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def mark_topic_repeated_by_reminder(self, reminder_id, user_id, timezone):
        session = self.Session()
        try:
            reminder = session.query(Reminder).filter_by(reminder_id=reminder_id).first()
            if not reminder:
                return None
            topic = session.query(Topic).filter_by(topic_id=reminder.topic_id, is_completed=False).first()
            if not topic:
                return None
            tz = pytz.timezone(timezone)
            now_local = datetime.now(tz)
            now_utc = self._to_utc_naive(now_local, timezone)
            topic.last_reviewed = now_utc
            topic.completed_repetitions += 1
            topic.repetition_stage = topic.completed_repetitions + 1

            intervals = [1, 1, 3, 7, 14, 30, 90]  # days
            if topic.completed_repetitions < len(intervals):
                next_review_local = now_local + timedelta(days=intervals[topic.completed_repetitions])
                topic.next_review = self._to_utc_naive(next_review_local, timezone)

                # Обновляем существующее напоминание вместо удаления
                existing_reminder = session.query(Reminder).filter_by(topic_id=topic.topic_id).first()
                if existing_reminder:
                    existing_reminder.scheduled_time = topic.next_review
                    new_reminder_id = existing_reminder.reminder_id
                else:
                    new_reminder = Reminder(
                        user_id=user_id,
                        topic_id=topic.topic_id,
                        scheduled_time=topic.next_review
                    )
                    session.add(new_reminder)
                    session.flush()
                    new_reminder_id = new_reminder.reminder_id
            else:
                topic.is_completed = True
                topic.next_review = None
                completed_topic = CompletedTopic(
                    user_id=user_id,
                    topic_name=topic.topic_name,
                    category_id=topic.category_id,
                    completed_at=now_utc
                )
                session.add(completed_topic)
                new_reminder_id = None

            session.commit()
            return topic.completed_repetitions, topic.next_review, new_reminder_id
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def add_reminder(self, user_id, topic_id, scheduled_time_utc):
        session = self.Session()
        try:
            reminder = Reminder(
                user_id=user_id,
                topic_id=topic_id,
                scheduled_time=scheduled_time_utc
            )
            session.add(reminder)
            session.commit()
            return reminder.reminder_id
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def delete_reminder(self, reminder_id):
        session = self.Session()
        try:
            session.query(Reminder).filter_by(reminder_id=reminder_id).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_reminders(self, user_id):
        session = self.Session()
        try:
            reminders = session.query(Reminder).filter_by(user_id=user_id).all()
            return reminders
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_reminder(self, reminder_id):
        session = self.Session()
        try:
            reminder = session.query(Reminder).filter_by(reminder_id=reminder_id).first()
            return reminder
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_reminder_by_topic(self, topic_id):
        session = self.Session()
        try:
            reminder = session.query(Reminder).filter_by(topic_id=topic_id).first()
            return reminder
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_all_users(self):
        session = self.Session()
        try:
            users = session.query(User).all()
            return users
        finally:
            session.close()