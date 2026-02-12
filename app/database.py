import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()  # Load environment variables as early as possible

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set")

echo = False

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
