import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = f"sqlite:///{(BASE_DIR / 'careguide.db').as_posix()}"
DATABASE_URL = os.getenv('DATABASE_URL') or DEFAULT_SQLITE
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
        yield session
