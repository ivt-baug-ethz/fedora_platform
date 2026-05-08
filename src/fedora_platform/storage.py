"""Storage backends for FEDORA MTM Space components."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from fedora_platform.components import DataStorage, Message, MessageBus


@dataclass(frozen=True)
class StorageTemplate:
    """Blueprint for implementing a FEDORA storage backend."""

    name: str
    storage_type: str
    python_dependencies: tuple[str, ...]
    best_for: str
    notes: str


def available_storage_templates() -> dict[str, StorageTemplate]:
    """Return storage templates suitable for FEDORA pilots and MTM Spaces."""

    return {
        "in_memory": StorageTemplate(
            name="InMemoryDataStore",
            storage_type="process memory",
            python_dependencies=(),
            best_for="Unit tests, notebooks, and disposable experiments.",
            notes="Fast and simple, but all records disappear when the process exits.",
        ),
        "json_file": StorageTemplate(
            name="JSONFileDataStore",
            storage_type="local JSON files",
            python_dependencies=(),
            best_for="Readable experiment artifacts and small reproducibility bundles.",
            notes="One JSON document per key; useful before a database schema is stable.",
        ),
        "sqlite": StorageTemplate(
            name="SQLiteInteractionStore",
            storage_type="local SQLite database",
            python_dependencies=(),
            best_for="Local pilots that need durable records and full interaction logs.",
            notes="Uses Python's built-in sqlite3 package, so no server is required.",
        ),
        "duckdb": StorageTemplate(
            name="DuckDBAnalyticsStore",
            storage_type="embedded analytical database",
            python_dependencies=("duckdb",),
            best_for="Columnar analytics over simulation outputs and event logs.",
            notes="A good next step when SQLite is too row-oriented for analysis.",
        ),
        "postgresql": StorageTemplate(
            name="PostgreSQLDataStore",
            storage_type="server database",
            python_dependencies=("sqlalchemy", "psycopg"),
            best_for="Multi-user deployments and operational pilots.",
            notes="Use PostGIS extensions when spatial queries become first-class.",
        ),
        "object_store": StorageTemplate(
            name="ObjectStoreDataLake",
            storage_type="S3-compatible object storage",
            python_dependencies=("boto3",),
            best_for="Large simulation outputs, sensor archives, and model artifacts.",
            notes="Store metadata in a database and bulk payloads in object storage.",
        ),
    }


class InMemoryDataStore(DataStorage):
    """Small volatile store useful for pilots, tests, and notebooks."""

    def __init__(
        self,
        component_id: str = "storage.in_memory",
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__(component_id, bus)
        self.records: dict[str, Any] = {}
        self.configure()

    def step(self) -> None:
        for message in self.receive():
            self.handle_message(message)

    def read(self, key: str) -> Any:
        return self.records[key]

    def write(self, key: str, value: Any) -> None:
        self.records[key] = value
        self.publish("storage.record_written", {"key": key})


class JSONFileDataStore(DataStorage):
    """Append-free JSON file store with one file per logical record."""

    def __init__(
        self,
        root: Path | str,
        component_id: str = "storage.json_file",
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__(component_id, bus)
        self.root = Path(root)
        self.configure({"root": str(self.root)})

    def configure(self, configuration: Optional[Mapping[str, Any]] = None) -> None:
        super().configure(configuration)
        self.root.mkdir(parents=True, exist_ok=True)

    def step(self) -> None:
        for message in self.receive():
            self.handle_message(message)

    def read(self, key: str) -> Any:
        path = self._path_for_key(key)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, key: str, value: Any) -> None:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, default=str)
        self.publish("storage.record_written", {"key": key, "path": str(path)})

    def _path_for_key(self, key: str) -> Path:
        safe_key = key.strip("/").replace("\\", "/")
        return self.root.joinpath(*safe_key.split("/")).with_suffix(".json")


class SQLiteInteractionStore(DataStorage):
    """Local SQLite store for records and message-level interaction logs."""

    def __init__(
        self,
        path: Path | str = "fedora_interactions.sqlite3",
        component_id: str = "storage.sqlite_interactions",
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__(component_id, bus)
        self.path = Path(path)
        self.configure({"path": str(self.path)})

    def configure(self, configuration: Optional[Mapping[str, Any]] = None) -> None:
        super().configure(configuration)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    receiver TEXT,
                    correlation_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def step(self) -> None:
        for message in self.receive():
            self.record_interaction(message)

    def read(self, key: str) -> Any:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM records WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def write(self, key: str, value: Any) -> None:
        value_json = json.dumps(value, sort_keys=True, default=str)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO records (key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value_json),
            )
        self.publish("storage.record_written", {"key": key})

    def record_interaction(self, message: Message) -> None:
        payload_json = json.dumps(message.payload, sort_keys=True, default=str)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO interactions (
                    topic,
                    sender,
                    receiver,
                    correlation_id,
                    payload_json,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.topic,
                    message.sender,
                    message.receiver,
                    message.correlation_id,
                    payload_json,
                    message.timestamp.isoformat(),
                ),
            )

    def list_interactions(
        self,
        limit: int = 100,
        topic: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT id, topic, sender, receiver, correlation_id, payload_json, "
            "timestamp, recorded_at FROM interactions"
        )
        parameters: tuple[Any, ...] = ()
        if topic is not None:
            query += " WHERE topic = ?"
            parameters = (topic,)
        query += " ORDER BY id DESC LIMIT ?"
        parameters = (*parameters, limit)

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            {
                "id": row[0],
                "topic": row[1],
                "sender": row[2],
                "receiver": row[3],
                "correlation_id": row[4],
                "payload": json.loads(row[5]),
                "timestamp": row[6],
                "recorded_at": row[7],
            }
            for row in rows
        ]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path))
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
