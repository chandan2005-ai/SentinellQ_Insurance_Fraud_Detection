"""SQLAlchemy engine and per-request transactional session."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import DB_URL

class Base(DeclarativeBase):
    pass

engine = create_engine(DB_URL, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
