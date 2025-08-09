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

class DeletedTopic(Base):
    __tablename__ = 'deleted_topics'
    deleted_topic_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    topic_name = Column(String)
    deleted_at = Column(DateTime)
    user = relationship("User")

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
            logger.debug(f"Queried user {user_id}: {'found' if user else 'not found'}")
            return user
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {str(e)}")
            raise
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
            now = datetime.now(tz)
            topic = Topic(
                user_id=user_id,
                category_id=category_id,
                topic_name=topic_name,
                created_at=now,
                last_reviewed=None,
                next_review=now + timedelta(hours=1),
                repetition_stage=1,
                completed_repetitions=0,
                is_completed=False
            )
            session.add(topic)
            session.flush()
            reminder = Reminder(
                user_id=user_id,
                topic_id=topic.topic_id,
                scheduled_time=now + timedelta(hours=1)
            )
            session.add(reminder)
            session.flush()
            session.commit()
            logger.debug(
                f"Added topic '{topic_name}' for user {user_id} with category_id {category_id}, reminder_id {reminder.reminder_id}")
            return topic.topic_id, reminder.reminder_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding topic '{topic_name}' for user {user_id}: {str(e)}")
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
            logger.debug(f"Found {len(topics)} active topics for user {user_id} in category {category_id}")
            return topics
        except Exception as e:
            logger.error(f"Error fetching active topics for user {user_id}: {str(e)}")
            raise
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
            logger.debug(f"Queried topic {topic_id} for user {user_id}: {'found' if topic else 'not found'}")
            return topic
        except Exception as e:
            logger.error(f"Error fetching topic {topic_id} for user {user_id}: {str(e)}")
            raise
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
            logger.debug(f"Queried topic '{topic_name}' for user {user_id}: {'found' if topic else 'not found'}")
            return topic
        except Exception as e:
            logger.error(f"Error fetching topic '{topic_name}' for user {user_id}: {str(e)}")
            raise
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
                logger.debug(f"Queried topic by reminder {reminder_id} for user {user_id}: {'found' if topic else 'not found'}")
                return topic
            return None
        except Exception as e:
            logger.error(f"Error fetching topic by reminder {reminder_id} for user {user_id}: {str(e)}")
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def delete_topic(self, topic_id, user_id, topic_name):
        session = self.Session()
        try:
            topic = session.query(Topic).filter_by(topic_id=topic_id, user_id=user_id).first()
            if topic:
                deleted_topic = DeletedTopic(
                    user_id=user_id,
                    topic_name=topic_name,
                    deleted_at=datetime.now(pytz.UTC)
                )
                session.add(deleted_topic)
                session.delete(topic)
                session.commit()
                logger.debug(f"Deleted topic {topic_id} for user {user_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting topic {topic_id} for user {user_id}: {str(e)}")
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_deleted_topics(self, user_id):
        session = self.Session()
        try:
            deleted_topics = session.query(DeletedTopic).filter_by(user_id=user_id).all()
            logger.debug(f"Found {len(deleted_topics)} deleted topics for user {user_id}")
            return deleted_topics
        except Exception as e:
            logger.error(f"Error fetching deleted topics for user {user_id}: {str(e)}")
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def restore_topic(self, deleted_topic_id, user_id, timezone):
        session = self.Session()
        try:
            deleted_topic = session.query(DeletedTopic).filter_by(deleted_topic_id=deleted_topic_id, user_id=user_id).first()
            if deleted_topic:
                tz = pytz.timezone(timezone)
                now = datetime.now(tz)
                topic = Topic(
                    user_id=user_id,
                    topic_name=deleted_topic.topic_name,
                    created_at=now,
                    last_reviewed=None,
                    next_review=now + timedelta(hours=1),
                    repetition_stage=1,
                    completed_repetitions=0,
                    is_completed=False
                )
                session.add(topic)
                session.flush()
                reminder = Reminder(
                    user_id=user_id,
                    topic_id=topic.topic_id,
                    scheduled_time=now + timedelta(hours=1)
                )
                session.add(reminder)
                session.delete(deleted_topic)
                session.commit()
                logger.debug(f"Restored topic '{deleted_topic.topic_name}' for user {user_id}")
                return topic.topic_id, topic.topic_name
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error restoring topic {deleted_topic_id} for user {user_id}: {str(e)}")
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
            logger.debug(f"Added category '{category_name}' for user {user_id}")
            return category.category_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding category '{category_name}' for user {user_id}: {str(e)}")
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
            logger.debug(f"Found {len(categories)} categories for user {user_id}")
            return categories
        except Exception as e:
            logger.error(f"Error fetching categories for user {user_id}: {str(e)}")
            raise
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
            logger.debug(f"Queried category {category_id} for user {user_id}: {'found' if category else 'not found'}")
            return category
        except Exception as e:
            logger.error(f"Error fetching category {category_id} for user {user_id}: {str(e)}")
            raise
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
                logger.debug(f"Renamed category {category_id} to '{new_name}' for user {user_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error renaming category {category_id} for user {user_id}: {str(e)}")
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
                session.delete(category)
                session.commit()
                logger.debug(f"Deleted category {category_id} for user {user_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting category {category_id} for user {user_id}: {str(e)}")
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
                logger.debug(f"Moved topic {topic_id} to category {category_id} for user {user_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error moving topic {topic_id} to category {category_id} for user {user_id}: {str(e)}")
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
            now = datetime.now(tz)
            topic.last_reviewed = now
            topic.completed_repetitions += 1
            topic.repetition_stage += 1

            # Define intervals for spaced repetition
            intervals = [1, 1, 3, 7, 14, 30]  # Days for each stage (1-based indexing)
            if topic.repetition_stage <= len(intervals):
                topic.next_review = now + timedelta(days=intervals[topic.repetition_stage - 1])
                reminder = Reminder(
                    user_id=user_id,
                    topic_id=topic.topic_id,
                    scheduled_time=topic.next_review
                )
                session.add(reminder)
                session.flush()
                reminder_id = reminder.reminder_id
            else:
                topic.is_completed = True
                topic.next_review = None
                reminder_id = None

            # Delete old reminders for this topic
            session.query(Reminder).filter_by(topic_id=topic.topic_id).delete()

            session.commit()
            logger.debug(
                f"Marked topic '{topic_name}' as repeated for user {user_id}. "
                f"Stage: {topic.repetition_stage}, Completed: {topic.completed_repetitions}, "
                f"Next review: {topic.next_review}, Reminder ID: {reminder_id}"
            )
            return topic.topic_id, topic.completed_repetitions, topic.next_review, reminder_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error marking topic '{topic_name}' as repeated for user {user_id}: {str(e)}")
            raise
        finally:
            session.close()

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        retry=tenacity.retry_if_exception_type(OperationalError),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )
    def get_reminders(self, user_id, timezone):
        session = self.Session()
        try:
            reminders = session.query(Reminder).filter_by(user_id=user_id).all()
            logger.debug(f"Found {len(reminders)} reminders for user {user_id}")
            return reminders
        except Exception as e:
            logger.error(f"Error fetching reminders for user {user_id}: {str(e)}")
            raise
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
            logger.debug(f"Found {len(users)} users")
            return users
        except Exception as e:
            logger.error(f"Error fetching all users: {str(e)}")
            raise
        finally:
            session.close()