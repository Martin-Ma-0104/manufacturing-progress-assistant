"""Human-confirmed production entry into the existing reviewed SQLite table."""
import sqlite3
from contextlib import closing
from production import import_records
from .data import db_path
from .models import ProductionEntry


class EntryConflict(ValueError):
    pass


def save_entry(value: ProductionEntry):
    record = value.model_dump(mode='json', exclude={'confirmed_real', 'source'})
    # mode=rw refuses to silently create a new/empty database at a wrong path.
    with closing(sqlite3.connect(db_path().as_uri() + '?mode=rw', uri=True, timeout=10)) as connection:
        connection.execute('PRAGMA foreign_keys = ON')
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='slitting_records'").fetchone():
            raise ValueError('Reviewed production table is unavailable. Check the database configuration.')
        try:
            # Lock before checking the existing key: simultaneous submissions serialize.
            connection.execute('BEGIN IMMEDIATE')
            added = import_records([record], connection, manage_transaction=False)
            connection.commit()
        except ValueError as exc:
            connection.rollback()
            if str(exc).startswith('Conflicting existing record:'):
                raise EntryConflict('A record already exists for this date, shift, machine and product with different values. Nothing was overwritten; review the existing record before correcting it.') from None
            raise
        except Exception:
            connection.rollback()
            raise
    return dict(status='saved' if added else 'unchanged', added=added,
                production_date=value.production_date.isoformat(), machine_id=value.machine_id,
                shift=value.shift, product=value.product, source='reviewed')
