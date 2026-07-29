import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "gestion_documental")
DB_USER = os.getenv("DB_USER", "gestion_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "gestion_pass")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()