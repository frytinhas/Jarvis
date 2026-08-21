"""SQLite persistence for M004 model records and profile associations."""
# ruff: noqa: E501

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from jarvis.foundation.clock import format_utc
from jarvis.models.errors import (
    ConcurrentModelModificationError,
    ModelNotFoundError,
    ModelUnavailableError,
)
from jarvis.models.models import (
    ModelAvailability,
    ModelId,
    ModelRecord,
    ModelRuntimeConfig,
    RuntimeLocationConfig,
)
from jarvis.profiles.errors import ProfileNotFoundError
from jarvis.profiles.models import ProfileId


def _config_to_json(config: ModelRuntimeConfig) -> str:
    return json.dumps(config.to_mapping(), sort_keys=True, separators=(",", ":"))


class ModelRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def _require_profile(self, profile_id: ProfileId) -> None:
        if (
            self._connection.execute(
                "SELECT 1 FROM profiles WHERE profile_id = ?", (str(profile_id),)
            ).fetchone()
            is None
        ):
            raise ProfileNotFoundError(safe_details={"reason": "not_found"})

    def get_runtime_location(self) -> RuntimeLocationConfig:
        row = self._connection.execute(
            "SELECT model_directories_json, llama_server_path, revision FROM installation_runtime_config WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return RuntimeLocationConfig()
        return RuntimeLocationConfig(
            tuple(Path(value) for value in json.loads(row[0])),
            Path(row[1]) if row[1] else None,
            int(row[2]),
        )

    def update_runtime_location(
        self, value: RuntimeLocationConfig, now: datetime
    ) -> RuntimeLocationConfig:
        self._connection.execute(
            """INSERT INTO installation_runtime_config (singleton, model_directories_json, llama_server_path, revision, updated_at_utc)
               VALUES (1, ?, ?, 1, ?)
               ON CONFLICT(singleton) DO UPDATE SET model_directories_json = excluded.model_directories_json,
                 llama_server_path = excluded.llama_server_path, revision = installation_runtime_config.revision + 1,
                 updated_at_utc = excluded.updated_at_utc""",
            (
                json.dumps([str(path) for path in value.model_directories]),
                str(value.llama_server_path) if value.llama_server_path else None,
                format_utc(now),
            ),
        )
        return self.get_runtime_location()

    def records(self) -> tuple[ModelRecord, ...]:
        rows = self._connection.execute(
            """SELECT models.model_id, model_paths.canonical_path, models.device, models.inode,
                      models.size_bytes, models.mtime_ns, models.metadata_json, models.fingerprint_sha256,
                      models.availability, models.availability_reason, models.last_scanned_at_utc
               FROM models JOIN model_paths ON model_paths.model_id = models.model_id
               ORDER BY model_paths.canonical_path, models.model_id"""
        ).fetchall()
        return tuple(
            ModelRecord(
                ModelId.parse(row[0]),
                Path(row[1]),
                int(row[2]),
                int(row[3]),
                int(row[4]),
                int(row[5]),
                json.loads(row[6]),
                row[7],
                ModelAvailability(row[8]),
                row[9],
                row[10],
            )
            for row in rows
        )

    def get_record(self, model_id: ModelId) -> ModelRecord:
        for record in self.records():
            if record.model_id == model_id:
                return record
        raise ModelNotFoundError()

    def reconcile(
        self, records: tuple[ModelRecord, ...], now: datetime, *, complete_scan: bool = True
    ) -> None:
        """Make this explicit scan authoritative, retaining old records as missing."""
        timestamp = format_utc(now)
        seen_paths = {str(record.canonical_path) for record in records}
        for record in records:
            path = str(record.canonical_path)
            old = self._connection.execute(
                """SELECT model_paths.model_id FROM model_paths
                   JOIN models ON models.model_id = model_paths.model_id
                   WHERE canonical_path = ?
                   ORDER BY (models.availability = 'available') DESC,
                            models.last_scanned_at_utc DESC, model_paths.model_id LIMIT 1""",
                (path,),
            ).fetchone()
            if old is not None and old[0] != str(record.model_id):
                self._connection.execute(
                    "UPDATE models SET availability = 'missing', availability_reason = 'replaced', last_scanned_at_utc = ? WHERE model_id = ?",
                    (timestamp, old[0]),
                )
            self._connection.execute(
                """INSERT INTO models (model_id, fingerprint_sha256, device, inode, size_bytes, mtime_ns, metadata_json, availability, availability_reason, last_scanned_at_utc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(model_id) DO UPDATE SET fingerprint_sha256 = excluded.fingerprint_sha256, device = excluded.device,
                     inode = excluded.inode, size_bytes = excluded.size_bytes, mtime_ns = excluded.mtime_ns,
                     metadata_json = excluded.metadata_json, availability = excluded.availability,
                     availability_reason = excluded.availability_reason, last_scanned_at_utc = excluded.last_scanned_at_utc""",
                (
                    str(record.model_id),
                    record.fingerprint_sha256,
                    record.device,
                    record.inode,
                    record.size_bytes,
                    record.mtime_ns,
                    json.dumps(record.metadata, sort_keys=True),
                    record.availability.value,
                    record.availability_reason,
                    timestamp,
                ),
            )
            self._connection.execute(
                """INSERT INTO model_paths (model_id, canonical_path) VALUES (?, ?)
                   ON CONFLICT(model_id) DO UPDATE SET canonical_path = excluded.canonical_path""",
                (str(record.model_id), path),
            )
        if complete_scan and seen_paths:
            placeholders = ",".join("?" for _ in seen_paths)
            self._connection.execute(
                f"UPDATE models SET availability = 'missing', availability_reason = 'not_seen', last_scanned_at_utc = ? WHERE model_id NOT IN (SELECT model_id FROM model_paths WHERE canonical_path IN ({placeholders}))",
                (timestamp, *seen_paths),
            )
        elif complete_scan:
            self._connection.execute(
                "UPDATE models SET availability = 'missing', availability_reason = 'not_seen', last_scanned_at_utc = ?",
                (timestamp,),
            )

    def associations(self, profile_id: ProfileId) -> tuple[dict[str, object], ...]:
        self._require_profile(profile_id)
        rows = self._connection.execute(
            "SELECT profile_models.model_id, profile_model_revision, selected, last_valid, runtime_config_json, availability FROM profile_models JOIN models ON models.model_id = profile_models.model_id WHERE profile_id = ? ORDER BY selected DESC, profile_models.model_id",
            (str(profile_id),),
        ).fetchall()
        return tuple(
            {
                "model_id": row[0],
                "revision": int(row[1]),
                "selected": bool(row[2]),
                "last_valid": bool(row[3]),
                "config": json.loads(row[4]),
                "availability": row[5],
            }
            for row in rows
        )

    def select(
        self,
        profile_id: ProfileId,
        model_id: ModelId,
        expected_revision: int,
        now: datetime,
        default_config: ModelRuntimeConfig,
    ) -> None:
        self._require_profile(profile_id)
        availability = self._connection.execute(
            "SELECT availability FROM models WHERE model_id = ?", (str(model_id),)
        ).fetchone()
        if availability is None:
            raise ModelNotFoundError()
        if availability[0] != ModelAvailability.AVAILABLE:
            raise ModelUnavailableError()
        existing = self._connection.execute(
            "SELECT profile_model_revision FROM profile_models WHERE profile_id = ? AND model_id = ?",
            (str(profile_id), str(model_id)),
        ).fetchone()
        if existing is not None and int(existing[0]) != expected_revision:
            raise ConcurrentModelModificationError("profile_model_revision_mismatch")
        self._connection.execute(
            "UPDATE profile_models SET selected = 0, last_valid = 0 WHERE profile_id = ?",
            (str(profile_id),),
        )
        timestamp = format_utc(now)
        self._connection.execute(
            """INSERT INTO profile_models (profile_id, model_id, profile_model_revision, selected, last_valid, runtime_config_json, created_at_utc, updated_at_utc)
            VALUES (?, ?, 1, 1, 1, ?, ?, ?) ON CONFLICT(profile_id, model_id) DO UPDATE SET
            profile_model_revision = profile_models.profile_model_revision + 1, selected = 1, last_valid = 1, updated_at_utc = excluded.updated_at_utc""",
            (
                str(profile_id),
                str(model_id),
                _config_to_json(default_config),
                timestamp,
                timestamp,
            ),
        )

    def get_config(self, profile_id: ProfileId, model_id: ModelId) -> dict[str, object]:
        self._require_profile(profile_id)
        row = self._connection.execute(
            "SELECT profile_model_revision, runtime_config_json FROM profile_models WHERE profile_id = ? AND model_id = ?",
            (str(profile_id), str(model_id)),
        ).fetchone()
        if row is None:
            raise ModelNotFoundError()
        return {"model_id": str(model_id), "revision": int(row[0]), "config": json.loads(row[1])}

    def update_config(
        self,
        profile_id: ProfileId,
        model_id: ModelId,
        config: ModelRuntimeConfig,
        expected_revision: int,
        now: datetime,
    ) -> None:
        self._require_profile(profile_id)
        cursor = self._connection.execute(
            "UPDATE profile_models SET runtime_config_json = ?, profile_model_revision = profile_model_revision + 1, updated_at_utc = ? WHERE profile_id = ? AND model_id = ? AND profile_model_revision = ?",
            (
                _config_to_json(config),
                format_utc(now),
                str(profile_id),
                str(model_id),
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise ConcurrentModelModificationError("profile_model_revision_mismatch")

    def clone_selected(self, source: ProfileId, target: ProfileId, now: datetime) -> None:
        row = self._connection.execute(
            "SELECT model_id, runtime_config_json, last_valid FROM profile_models WHERE profile_id = ? AND selected = 1",
            (str(source),),
        ).fetchone()
        if row is not None:
            timestamp = format_utc(now)
            self._connection.execute(
                "INSERT INTO profile_models (profile_id, model_id, profile_model_revision, selected, last_valid, runtime_config_json, created_at_utc, updated_at_utc) VALUES (?, ?, 1, 1, ?, ?, ?, ?)",
                (str(target), row[0], row[2], row[1], timestamp, timestamp),
            )
