"""Database migration runner for GramSetu AI PostgreSQL & PostGIS schema."""
from __future__ import annotations

import os
import sys
import logging
from sqlalchemy import text
from gramsetu.database.session import get_db_engine, check_db_connection
from gramsetu.core.config import Settings

logger = logging.getLogger("gramsetu.migration")
logging.basicConfig(level=logging.INFO)


def run_migrations(settings: Settings | None = None) -> bool:
    """Execute SQL schema migrations if PostgreSQL connection is available."""
    cfg = settings or Settings()
    logger.info("Auditing PostgreSQL & PostGIS connection...")
    check = check_db_connection(cfg)

    if not check["is_connected"]:
        logger.warning(
            "PostgreSQL database is currently unavailable at %s: %s. "
            "Migration cannot execute against live DB; schema file is prepared in 001_initial_schema.sql.",
            check["configured_url"],
            check["error"],
        )
        return False

    engine = get_db_engine(cfg)
    sql_file = os.path.join(os.path.dirname(__file__), "001_initial_schema.sql")

    if not os.path.exists(sql_file):
        logger.error("Migration file not found at %s", sql_file)
        return False

    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    try:
        with engine.connect() as conn:
            # Execute migration batch
            conn.execute(text(sql_content))
            conn.commit()
            logger.info("Successfully executed 001_initial_schema.sql on PostgreSQL database!")
            return True
    except Exception as exc:
        logger.error("Failed to execute migration: %s", exc)
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
