from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    timezone = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class Topic(Base):
    __tablename__ = "topics"

    topic_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True)
    topic_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_reviewed = Column(DateTime)
    next_review = Column(DateTime, index=True)
    repetition_stage = Column(Integer, default=0)
    completed_repetitions = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)


class DeletedTopic(Base):
    __tablename__ = "deleted_topics"

    deleted_topic_id = Column(Integer, primary_key=True)
    topic_id = Column(Integer)
    user_id = Column(BigInteger)
    topic_name = Column(String(255))
    deleted_at = Column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self):
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not set in environment variables")

        # Configure connection pool for Neon
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=2,
            max_overflow=2,
            pool_timeout=30,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_user(self, user_id: int):
        with self.Session() as session:
            return session.query(User).filter_by(user_id=user_id).first()

    def save_user(self, user_id: int, username: str, timezone: str):
        with self.Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if not user:
                user = User(user_id=user_id, username=username, timezone=timezone)
                session.add(user)
            else:
                user.timezone = timezone
                user.username = username
            session.commit()