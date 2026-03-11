from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slack_user_id = Column(String(50), nullable=False)
    slack_channel = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    remind_at = Column(DateTime, nullable=False)  # UTC
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slack_user_id = Column(String(50), nullable=False)
    slack_thread_ts = Column(String(50), nullable=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    content = Column(Text, nullable=False)
    slack_channel = Column(String(100), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)


# SQLite for local/Render (ファイルDB)
engine = create_engine("sqlite:///./secretary.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
