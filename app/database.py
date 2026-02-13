import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()  # Load environment variables as early as possible

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")

connect_args = {}
if SQLALCHEMY_DATABASE_URL is None:
    # Fallback to SQLite for self-hosted option
    DATA_DIR = Path("data")
    DATA_DIR.mkdir(exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR / 'tracks.db'}"
    # SQLite-specific arguments
    connect_args = {"check_same_thread": False, "timeout": 15}

echo = False

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
