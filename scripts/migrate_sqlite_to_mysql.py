"""Copy MaterialHub rows from SQLite into an empty MySQL database.

Usage:
    python scripts/migrate_sqlite_to_mysql.py

Environment:
    SOURCE_DATABASE_URL  Optional. Defaults to sqlite:///materials.db at repo root.
    DATABASE_URL         Required. Target MySQL URL, for example:
                         mysql+pymysql://USER:PASSWORD@HOST:3306/DBNAME
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database import Base
import app.models  # noqa: F401 - import models so Base.metadata is populated


DEFAULT_SOURCE_DATABASE_URL = f"sqlite:///{(ROOT_DIR / 'materials.db').as_posix()}"
BATCH_SIZE = 500


def usage() -> str:
    return (
        "Usage: python scripts/migrate_sqlite_to_mysql.py\n\n"
        "Set DATABASE_URL to the target MySQL database URL before running.\n"
        "Optionally set SOURCE_DATABASE_URL; it defaults to sqlite:///materials.db.\n"
        "The target database must already exist and must be empty."
    )


def main() -> int:
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        print(usage())
        return 0

    source_url = os.getenv("SOURCE_DATABASE_URL", DEFAULT_SOURCE_DATABASE_URL)
    target_url = os.getenv("DATABASE_URL")
    if not target_url:
        print("ERROR: DATABASE_URL is required for the target MySQL database.", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2
    if not target_url.startswith("mysql+pymysql://"):
        print("ERROR: DATABASE_URL must use mysql+pymysql://", file=sys.stderr)
        return 2

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    try:
        _assert_target_is_empty(target_engine)
        _copy_all_tables(source_engine, target_engine)
    except SQLAlchemyError as exc:
        print(f"ERROR: migration failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Migration completed successfully.")
    return 0


def _assert_target_is_empty(target_engine: Engine) -> None:
    with Session(target_engine) as session:
        non_empty = []
        for table in Base.metadata.sorted_tables:
            count = session.execute(select(func.count()).select_from(table)).scalar_one()
            if count:
                non_empty.append(f"{table.name} ({count})")
        if non_empty:
            joined = ", ".join(non_empty)
            raise RuntimeError(f"target database is not empty: {joined}")


def _copy_all_tables(source_engine: Engine, target_engine: Engine) -> None:
    tables = list(Base.metadata.sorted_tables)
    with Session(source_engine) as source_session, target_engine.begin() as target_connection:
        _set_mysql_foreign_key_checks(target_connection, enabled=False)
        try:
            for table in tables:
                inserted = 0
                result = source_session.execute(select(table))
                batch = []
                for row in result.mappings():
                    batch.append(dict(row))
                    if len(batch) >= BATCH_SIZE:
                        target_connection.execute(table.insert(), batch)
                        inserted += len(batch)
                        batch.clear()
                if batch:
                    target_connection.execute(table.insert(), batch)
                    inserted += len(batch)
                print(f"{table.name}: inserted {inserted}")
        finally:
            _set_mysql_foreign_key_checks(target_connection, enabled=True)


def _set_mysql_foreign_key_checks(connection, *, enabled: bool) -> None:
    value = 1 if enabled else 0
    connection.execute(text(f"SET FOREIGN_KEY_CHECKS={value}"))


if __name__ == "__main__":
    raise SystemExit(main())
