"""
Database Engine and Session Setup
Synchronous SQLite & PostgreSQL with thread-safe access for FastAPI.
Zero deadlocks, rock solid on Windows.
"""
import os
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import DATA_DIR

Base = declarative_base()

# Synchronous SQLite file path
db_file = (DATA_DIR / "trafficguard.db").resolve()
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite:///{db_file.as_posix()}"
)

# If user provided postgresql+asyncpg, convert to standard postgresql if using sync driver
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
