"""
SQLite database setup using SQLAlchemy ORM.
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Stock(Base):
    """
    A stock the user has manually added to their watchlist/dashboard.
    """
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)   # e.g. RELIANCE.NS
    name = Column(String, nullable=False)                              # e.g. Reliance Industries Limited
    exchange = Column(String, default="NSE")
    buy_price_min = Column(Float, nullable=True)
    buy_price_max = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Latest cached snapshot (updated on refresh) so dashboard loads fast
    last_price = Column(Float, nullable=True)
    last_rsi = Column(Float, nullable=True)
    last_updated = Column(DateTime, nullable=True)


class PriceSnapshot(Base):
    """
    Historical snapshot log every time RSI/price is refreshed for a stock.
    Useful for the RAG layer to reference recent history.
    """
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    rsi_14 = Column(Float, nullable=True)
    signal = Column(String, nullable=True)   # "BUY", "HOLD", "WATCH"
    captured_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
