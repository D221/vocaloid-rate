import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()  # Load environment variables as early as possible

is_frozen_build = getattr(sys, "frozen", False)
SQLALCHEMY_DATABASE_URL = None if is_frozen_build else os.environ.get("DATABASE_URL")

connect_args = {}
if not SQLALCHEMY_DATABASE_URL:
    # Frozen desktop builds always use local SQLite.
    # Non-frozen runs also fall back to SQLite when DATABASE_URL is unset.
    DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
    DATA_DIR.mkdir(exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR / 'tracks.db'}"
    # SQLite-specific arguments
    connect_args = {"check_same_thread": False, "timeout": 15}

echo = False

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
