"""Database session and connection management for GramSetu AI."""
from __future__ import annotations

import logging
from typing import Generator, Optional, Dict, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from gramsetu.core.config import Settings

logger = logging.getLogger("gramsetu.database")

Base = declarative_base()

_engine = None
_SessionFactory = None


def get_db_engine(settings: Optional[Settings] = None):
    """Retrieve or initialize singleton SQLAlchemy database engine."""
    global _engine, _SessionFactory
    if _engine is None:
        cfg = settings or Settings()
        db_url = cfg.get_database_url()
        try:
            _engine = create_engine(
                db_url,
                pool_size=cfg.DB_POOL_SIZE,
                max_overflow=cfg.DB_MAX_OVERFLOW,
                echo=cfg.DB_ECHO,
                future=True,
            )
            _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False, future=True)
            logger.info("Database engine initialized for %s", db_url.split("@")[-1])
        except Exception as exc:
            logger.warning("Failed to initialize database engine for URL: %s", exc)
            return None
    return _engine


@contextmanager
def get_db_session(settings: Optional[Settings] = None) -> Generator[Session, None, None]:
    """Context manager providing a transactional database session."""
    engine = get_db_engine(settings)
    if engine is None or _SessionFactory is None:
        raise RuntimeError("Database engine is not configured or unavailable.")

    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Audit database connectivity and PostGIS extension status without crashing."""
    cfg = settings or Settings()
    result = {
        "configured_url": cfg.get_database_url().split("@")[-1],
        "is_connected": False,
        "postgis_enabled": False,
        "server_version": None,
        "error": None,
    }

    try:
        engine = get_db_engine(cfg)
        if engine is None:
            result["error"] = "SQLAlchemy engine could not be created (missing driver or invalid URL)."
            return result

        with engine.connect() as conn:
            # Check version
            res = conn.execute(text("SELECT version();")).scalar()
            result["is_connected"] = True
            result["server_version"] = str(res)

            # Check PostGIS extension
            try:
                pgis = conn.execute(text("SELECT PostGIS_Version();")).scalar()
                result["postgis_enabled"] = True
                result["postgis_version"] = str(pgis)
            except Exception as e:
                result["postgis_enabled"] = False
                result["postgis_notice"] = f"PostGIS extension not active: {e}"

    except Exception as exc:
        result["error"] = str(exc)
        result["is_connected"] = False

    return result


def init_db_schema(engine=None) -> bool:
    """Create all declarative tables and PostGIS extension if database is reachable."""
    eng = engine or get_db_engine()
    if eng is None:
        return False
    try:
        with eng.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
            except Exception as e:
                logger.warning("Could not execute CREATE EXTENSION postgis: %s", e)

        from gramsetu.database.models import Base
        Base.metadata.create_all(bind=eng)
        return True
    except Exception as exc:
        logger.warning("Could not create schema tables: %s", exc)
        return False
