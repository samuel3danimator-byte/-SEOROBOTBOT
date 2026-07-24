from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

import config

_url = config.DATABASE_URL
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    keywords = relationship("TrackedKeyword", back_populates="user", cascade="all, delete-orphan")


class TrackedKeyword(Base):
    __tablename__ = "tracked_keywords"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    keyword = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="keywords")
    history = relationship("RankHistory", back_populates="tracked_keyword", cascade="all, delete-orphan")


class RankHistory(Base):
    __tablename__ = "rank_history"
    id = Column(Integer, primary_key=True)
    keyword_id = Column(Integer, ForeignKey("tracked_keywords.id"))
    position = Column(Integer, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
    tracked_keyword = relationship("TrackedKeyword", back_populates="history")


def init_db():
    Base.metadata.create_all(engine)
