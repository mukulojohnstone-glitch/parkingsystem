"""SQLite helpers for slots, active vehicles, rates, and the audit log."""

from contextlib import contextmanager
import sqlite3


SLOT_COUNT = 20
DEFAULT_RATES = [
    ("free", "Up to 30 minutes", 30, 0),
    ("two_hours", "31 minutes to 2 hours", 120, 50),
    ("four_hours", "Over 2 to 4 hours", 240, 100),
    ("six_hours", "Over 4 to 6 hours", 360, 300),
    ("over_six", "Over 6 hours", None, 500),
]


@contextmanager
def connect(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path):
    """Create tables and seed the 20 slots and default fee tiers once."""
    with connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS slots (
                slot_number INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'Free'
                    CHECK (status IN ('Free', 'Occupied'))
            );
            CREATE TABLE IF NOT EXISTS vehicles (
                plate TEXT PRIMARY KEY,
                entry_time TEXT NOT NULL,
                slot_number INTEGER NOT NULL UNIQUE,
                FOREIGN KEY (slot_number) REFERENCES slots(slot_number)
            );
            CREATE TABLE IF NOT EXISTS rates (
                rate_key TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                max_minutes INTEGER,
                amount INTEGER NOT NULL CHECK (amount >= 0)
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_method TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO slots (slot_number) VALUES (?)",
            [(number,) for number in range(1, SLOT_COUNT + 1)],
        )
        connection.executemany(
            """INSERT OR IGNORE INTO rates
               (rate_key, label, max_minutes, amount) VALUES (?, ?, ?, ?)""",
            DEFAULT_RATES,
        )


def get_slots(database_path):
    """A fixed slot table makes slot numbers and current states easy to query."""
    with connect(database_path) as connection:
        rows = connection.execute(
            """SELECT slots.slot_number,
                      CASE WHEN vehicles.plate IS NULL THEN 'Free' ELSE 'Occupied' END AS status
               FROM slots LEFT JOIN vehicles USING (slot_number)
               ORDER BY slots.slot_number"""
        ).fetchall()
    return [dict(row) for row in rows]


def add_vehicle(database_path, plate, entry_time):
    """Allocate the lowest-numbered free slot inside one write transaction."""
    with connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM vehicles WHERE plate = ?", (plate,)).fetchone():
            return {"status": "duplicate"}
        slot = connection.execute(
            """SELECT slots.slot_number FROM slots
               LEFT JOIN vehicles USING (slot_number)
               WHERE vehicles.plate IS NULL ORDER BY slots.slot_number LIMIT 1"""
        ).fetchone()
        if slot is None:
            return {"status": "full"}
        connection.execute(
            "INSERT INTO vehicles (plate, entry_time, slot_number) VALUES (?, ?, ?)",
            (plate, entry_time, slot["slot_number"]),
        )
    return {"status": "added", "slot_number": slot["slot_number"]}


def get_vehicle(database_path, plate):
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT plate, entry_time, slot_number FROM vehicles WHERE plate = ?",
            (plate,),
        ).fetchone()
    return dict(row) if row else None


def get_rates(database_path):
    with connect(database_path) as connection:
        rows = connection.execute(
            """SELECT rate_key AS key, label, max_minutes, amount FROM rates
               ORDER BY max_minutes IS NULL, max_minutes"""
        ).fetchall()
    return [dict(row) for row in rows]


def update_rates(database_path, amounts):
    with connect(database_path) as connection:
        connection.executemany(
            "UPDATE rates SET amount = ? WHERE rate_key = ?",
            [(amount, key) for key, amount in amounts.items()],
        )


def complete_transaction(database_path, plate, exit_time, duration_seconds, amount, payment_method):
    """Log payment and remove the active vehicle together, freeing its slot."""
    with connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        vehicle = connection.execute(
            "SELECT plate, entry_time FROM vehicles WHERE plate = ?", (plate,)
        ).fetchone()
        if vehicle is None:
            return False
        connection.execute(
            """INSERT INTO transactions
               (plate, entry_time, exit_time, duration_seconds, amount, payment_method)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (plate, vehicle["entry_time"], exit_time, duration_seconds, amount, payment_method),
        )
        connection.execute("DELETE FROM vehicles WHERE plate = ?", (plate,))
    return True


def get_transactions(database_path):
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM transactions ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]