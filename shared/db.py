from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime
import os
import uuid

# ============================================================
# Koneksi DB — ambil dari environment variable
# Orang 5 (shared) yang maintain file ini.
# Semua modul tinggal import get_db() dan Base dari sini.
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/gateway_db"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================
# Dependency untuk FastAPI route (pakai di Depends)
# ============================================================

def get_db():
    """
    Dependency injection untuk mendapatkan DB session.
    Contoh pemakaian di route:
        @app.get("/example")
        async def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Buat semua tabel (berdasarkan ORM models di models.py).
    Panggil sekali saat startup, atau jalankan:
        python -c "from shared.db import init_db; init_db()"
    """
    # import models supaya Base mengenali semua tabel
    from shared import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
