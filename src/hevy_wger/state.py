"""Durable source inbox and write journal. Each statement commits before network I/O."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class State:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / "state.sqlite3", timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 1:
            self.db.close()
            raise ValueError("State schema is newer than this connector; do not downgrade")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS mappings (hevy_id TEXT PRIMARY KEY, wger_id INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (
                kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', error TEXT, deleted INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS resources (
                key TEXT PRIMARY KEY, owner TEXT NOT NULL, route TEXT NOT NULL,
                remote_id TEXT, expected TEXT, desired TEXT NOT NULL,
                status TEXT NOT NULL, marker_field TEXT, marker TEXT, match_fields TEXT NOT NULL);
            PRAGMA user_version=1;
        """)

    def close(self):
        self.db.close()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, encode(value)))

    def bind(self, identity):
        previous = self.get("identity")
        if previous is not None and previous != identity:
            raise ValueError("State belongs to a different source/destination account or URL; use a separate DATA_DIR")
        self.set("identity", identity)

    @contextmanager
    def lock(self):
        # OS locks release on process exit; the lock file itself is never deleted.
        with (self.directory / "writer.lock").open("a+b") as file:
            file.seek(0)
            if not file.read(1):
                file.write(b"0")
                file.flush()
            file.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("Another connector command is writing this state; retry when its sync finishes") from error
            try:
                yield
            finally:
                file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)

    def mapping(self, hevy_id):
        row = self.db.execute("SELECT wger_id FROM mappings WHERE hevy_id=?", (hevy_id,)).fetchone()
        return row[0] if row else None

    def map(self, hevy_id, wger_id):
        self.db.execute("INSERT OR REPLACE INTO mappings VALUES (?,?)", (hevy_id, int(wger_id)))

    def ingest(self, kind, payload):
        source_id = str(payload["id"])
        old = self.db.execute("SELECT * FROM sources WHERE kind=? AND id=?", (kind, source_id)).fetchone()
        # Keep completion status only when the full source payload is unchanged.
        status = old["status"] if old and old["payload"] == encode(payload) and not old["deleted"] else "pending"
        self.db.execute("INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,0)",
                        (kind, source_id, encode(payload), status, old["error"] if old and status != "pending" else None))

    def deleted(self, kind, source_id):
        self.db.execute("UPDATE sources SET deleted=1,status='pending',error=NULL WHERE kind=? AND id=?", (kind, source_id))

    def sources(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM sources ORDER BY kind,id")]

    def status(self, kind, source_id, status, error=None):
        self.db.execute("UPDATE sources SET status=?,error=? WHERE kind=? AND id=?", (status, error, kind, source_id))

    def resource(self, key):
        row = self.db.execute("SELECT * FROM resources WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None

    def resources(self, owner=None):
        query, args = ("SELECT * FROM resources", ()) if owner is None else ("SELECT * FROM resources WHERE owner=?", (owner,))
        return [dict(row) for row in self.db.execute(query, args)]

    def save_resource(self, key, **values):
        current = self.resource(key) or {"key": key, "remote_id": None, "expected": None,
            "status": "intent", "marker_field": None, "marker": None, "match_fields": "{}"}
        current.update(values)
        columns = ["key", "owner", "route", "remote_id", "expected", "desired", "status", "marker_field", "marker", "match_fields"]
        self.db.execute(f"INSERT OR REPLACE INTO resources ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                        tuple(current.get(name) for name in columns))

    def forget(self, key):
        self.db.execute("DELETE FROM resources WHERE key=?", (key,))

    def report(self):
        counts = {row["status"]: row["n"] for row in self.db.execute("SELECT status,count(*) n FROM sources GROUP BY status")}
        return {"counts": counts, "last_success": self.get("last_success"), "last_attempt": self.get("last_attempt"),
                "last_error": self.get("last_error"), "checkpoint": self.get("checkpoint"),
                "issues": [{k: r[k] for k in ["kind", "id", "status", "error"]}
                           for r in self.sources() if r["status"] not in {"imported", "deleted"}],
                "uncertain_writes": [{k: r[k] for k in ["key", "route", "status"]}
                                     for r in self.resources() if r["status"] in {"intent", "unknown"}]}
