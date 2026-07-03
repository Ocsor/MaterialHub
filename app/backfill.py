"""Conservative maintenance backfill for existing MaterialHub databases.

Run from the project root with ``python -m app.backfill``. Only blank local
fields are filled; values already entered by an administrator are preserved.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Material
from .sync import _initial_local_fields


@dataclass
class BackfillResult:
    scanned: int = 0
    friendly_names_filled: int = 0
    matex_values_filled: int = 0


def backfill_local_defaults(db: Session) -> BackfillResult:
    """Populate missing local defaults without changing populated fields."""
    result = BackfillResult()
    try:
        for material in db.scalars(select(Material)).all():
            result.scanned += 1
            defaults = _initial_local_fields(material.name)

            if not material.friendly_name or not material.friendly_name.strip():
                material.friendly_name = defaults["friendly_name"]
                result.friendly_names_filled += 1

            if (
                (not material.matex or not material.matex.strip())
                and defaults["matex"] is not None
            ):
                material.matex = defaults["matex"]
                result.matex_values_filled += 1

        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


def main() -> None:
    """Run the backfill against MaterialHub's configured SQLite database."""
    with SessionLocal() as db:
        result = backfill_local_defaults(db)
    print(
        f"Backfill complete: {result.scanned} scanned, "
        f"{result.friendly_names_filled} friendly names filled, "
        f"{result.matex_values_filled} Matex values filled."
    )


if __name__ == "__main__":
    main()
