"""A small transactional SQLite store. Only save_approved creates family records."""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .models import canonical_json, fingerprint, normalize, search_terms, search_words


class StorageUnavailable(RuntimeError):
    pass


class SavedNoticeConflict(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._run(self._initialize)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _run(self, operation):
        # Two attempts total. Each transaction rolls back on failure.
        for attempt in range(2):
            try:
                with closing(self._connect()) as connection, connection:
                    return operation(connection)
            except sqlite3.OperationalError:
                if attempt == 1:
                    raise StorageUnavailable("Local storage failed after two attempts.") from None
            except sqlite3.DatabaseError:
                raise StorageUnavailable("Local storage could not complete the operation.") from None

    @staticmethod
    def _initialize(connection):
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                notice_key TEXT NOT NULL UNIQUE,
                content_json TEXT NOT NULL,
                approved_digest TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL REFERENCES notes(id),
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                evidence TEXT NOT NULL,
                UNIQUE(note_id, title, due_date)
            );
        """)

    @staticmethod
    def _task_signature(proposal):
        return sorted((normalize(task["title"]), task["due_date"]) for task in proposal["tasks"])

    def save_approved(self, proposal: dict, approved_digest: str) -> dict:
        if fingerprint(proposal) != approved_digest:
            raise PermissionError("Approval does not match the exact proposed content.")
        notice_key = fingerprint({"source": normalize(proposal["source_text"]),
                                  "event_date": proposal["event_date"]})

        def save(connection):
            # Serialize concurrent writers before checking uniqueness.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM notes WHERE notice_key = ?", (notice_key,)).fetchone()
            if existing:
                original = json.loads(existing["content_json"])
                if self._task_signature(original) != self._task_signature(proposal):
                    raise SavedNoticeConflict("This notice already has different saved tasks. No changes were made.")
                return {"status": "duplicate", "note_id": existing["id"],
                        "message": "This notice and these tasks were already saved; no extra records were created."}
            note_id = str(uuid4())
            connection.execute("INSERT INTO notes VALUES (?, ?, ?, ?, ?)",
                               (note_id, notice_key, canonical_json(proposal), approved_digest,
                                datetime.now(timezone.utc).isoformat()))
            for task in proposal["tasks"]:
                connection.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                                   (str(uuid4()), note_id, task["title"], task["due_date"], task["evidence"]))
            return {"status": "saved", "note_id": note_id,
                    "message": f"Saved one notice and {len(proposal['tasks'])} tasks."}

        result = self._run(save)
        # A separate connection proves the transaction persisted, not just an in-memory value.
        saved = self.get_note(result["note_id"])
        if saved is None:
            raise StorageUnavailable("The save could not be verified. Retry the same notice safely.")
        result["verified_record"] = saved
        return result

    def get_note(self, note_id: str) -> dict | None:
        def get(connection):
            row = connection.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            return self._note(row) if row else None
        return self._run(get)

    @staticmethod
    def _note(row):
        return {"note_id": row["id"], "approved_digest": row["approved_digest"],
                "saved_at": row["saved_at"], **json.loads(row["content_json"])}

    @staticmethod
    def _note_context(proposal):
        # Search family information, never JSON keys, hashes or internal record IDs.
        return " ".join([proposal["title"], proposal["source_text"], proposal["event_date"],
                         *proposal["clarifications"]])

    def search_notes(self, query: str) -> list[dict]:
        terms = search_terms(query)
        def search(connection):
            rows = connection.execute("SELECT * FROM notes ORDER BY saved_at DESC").fetchall()
            results = []
            for row in rows:
                proposal = json.loads(row["content_json"])
                text = self._note_context(proposal) + " " + " ".join(
                    f"{task['title']} {task['due_date']} {task['evidence']}" for task in proposal["tasks"])
                if terms and terms <= search_words(text):
                    results.append(self._note(row))
            return results[:10]
        return self._run(search)

    def lookup_tasks(self, query: str) -> list[dict]:
        terms = search_terms(query)
        def lookup(connection):
            rows = connection.execute("""
                SELECT tasks.*, notes.content_json FROM tasks
                JOIN notes ON notes.id = tasks.note_id ORDER BY due_date
            """).fetchall()
            matches = []
            for row in rows:
                proposal = json.loads(row["content_json"])
                task_words = search_words(f"{row['title']} {row['due_date']} {row['evidence']}")
                context_words = search_words(self._note_context(proposal))
                if terms and terms <= task_words | context_words:
                    record = {"task_id": row["id"], "note_id": row["note_id"], "title": row["title"],
                              "due_date": row["due_date"], "evidence": row["evidence"],
                              "source_text": proposal["source_text"], "clarifications": proposal["clarifications"]}
                    matches.append((len(terms & task_words), record))
            # Prefer tasks matching the requested action; context-only queries can return all related tasks.
            best_score = max((score for score, _ in matches), default=0)
            return [record for score, record in matches if score == best_score][:10]
        return self._run(lookup)

    def counts(self) -> tuple[int, int]:
        return self._run(lambda connection: (
            connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]))
