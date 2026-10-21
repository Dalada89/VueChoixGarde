"""SQLite profiles, copy register, and journal persistence (Technical Design 6.3)."""

import json
import sqlite3
import uuid
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from vuechoixgarde.core.slots import Slot, validate_slot_profile
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.ports.clock import Clock
from vuechoixgarde.ports.errors import SettingsStoreError, StateStoreError, StateStoreErrorReason
from vuechoixgarde.ports.models import (
    CopyRecord,
    FolderRenameRecord,
    FolderRenameState,
    LoadStatus,
    OperationFileRecord,
    OperationRecord,
    OperationState,
    ProfileRecord,
    StateLoadResult,
)
from vuechoixgarde.store.damage import quarantine_damaged
from vuechoixgarde.store.paths import prepare_application_data

_SCHEMA_VERSION = 2


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _migration_0_to_1(connection: sqlite3.Connection) -> None:
    """Create the initial profile, slot, copy-register, and operation-journal schema."""
    try:
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY,
                folder_identity TEXT NOT NULL UNIQUE,
                display_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE slots (
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                slot_order INTEGER NOT NULL,
                key_position TEXT NOT NULL,
                destination_name TEXT,
                color TEXT NOT NULL,
                PRIMARY KEY (profile_id, slot_order)
            );
            CREATE TABLE copies (
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                source_folder TEXT NOT NULL,
                source_name TEXT NOT NULL,
                destination_folder TEXT NOT NULL,
                destination_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                mtime_ns INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (profile_id, destination_folder, destination_name)
            );
            CREATE TABLE operations (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL REFERENCES profiles(id),
                destination_name TEXT NOT NULL,
                state TEXT NOT NULL CHECK (
                    state IN ('started', 'done', 'rolled_back', 'recovered')
                ),
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE operation_files (
                operation_id TEXT NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
                "index" INTEGER NOT NULL,
                temp_name TEXT NOT NULL,
                final_name TEXT NOT NULL,
                expected_size INTEGER NOT NULL,
                expected_sha256 TEXT NOT NULL,
                PRIMARY KEY (operation_id, "index"),
                UNIQUE (operation_id, temp_name)
            );
            CREATE INDEX copies_by_source ON copies(profile_id, source_name);
            PRAGMA user_version = 1;
            COMMIT;
            """
        )
    except sqlite3.Error:
        connection.rollback()
        raise


def _migration_1_to_2(connection: sqlite3.Connection) -> None:
    """Add the durable destination-folder rename journal."""
    try:
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE folder_renames (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                old_folder TEXT NOT NULL,
                new_folder TEXT NOT NULL,
                intermediate_folder TEXT,
                target_slots_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK (
                    state IN ('started', 'done', 'rolled_back', 'recovered')
                ),
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            PRAGMA user_version = 2;
            COMMIT;
            """
        )
    except sqlite3.Error:
        connection.rollback()
        raise


class SQLiteStateStore:
    """A short-lived-connection SQLite implementation of `StateStore`."""

    def __init__(self, root: Path, clock: Clock) -> None:
        self.root = root
        self.path = root / "state.sqlite3"
        self.clock = clock
        prepare_application_data(root)

    def _connect(self, *, create: bool = False) -> sqlite3.Connection:
        if create:
            connection = sqlite3.connect(self.path)
        else:
            if not self.path.exists():
                raise StateStoreError(
                    StateStoreErrorReason.IO_ERROR, path=self.path, detail="database is missing"
                )
            connection = sqlite3.connect(f"{self.path.as_uri()}?mode=rw", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _timestamp(self) -> str:
        try:
            return _iso_utc(self.clock.now_utc())
        except (TypeError, ValueError, OverflowError) as error:
            raise StateStoreError(
                StateStoreErrorReason.INVALID_DATA,
                detail=f"clock returned invalid time: {error}",
            ) from error

    def load(self) -> StateLoadResult:
        """Create first-run state or verify/migrate existing state without repairing damage."""
        was_missing = not self.path.exists()
        try:
            connection = self._connect(create=was_missing)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or integrity[0] != "ok":
                    return StateLoadResult(
                        LoadStatus.DAMAGED,
                        False,
                        StateStoreErrorReason.INTEGRITY_FAILURE,
                        str(integrity[0] if integrity else "no integrity result"),
                    )
                version_row = connection.execute("PRAGMA user_version").fetchone()
                version = int(version_row[0]) if version_row is not None else -1
                if version > _SCHEMA_VERSION or version < 0:
                    return StateLoadResult(
                        LoadStatus.DAMAGED,
                        False,
                        StateStoreErrorReason.UNSUPPORTED_VERSION,
                        f"user_version={version}",
                    )
                if version == 0:
                    _migration_0_to_1(connection)
                    version = 1
                if version == 1:
                    _migration_1_to_2(connection)
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA foreign_keys = ON")
            finally:
                connection.close()
        except StateStoreError as error:
            return StateLoadResult(
                LoadStatus.DAMAGED,
                False,
                StateStoreErrorReason(error.reason.value),
                str(error),
            )
        except sqlite3.DatabaseError as error:
            reason = (
                StateStoreErrorReason.INVALID_DATABASE
                if not was_missing
                else StateStoreErrorReason.MIGRATION_FAILURE
            )
            return StateLoadResult(LoadStatus.DAMAGED, False, reason, str(error))
        except OSError as error:
            return StateLoadResult(
                LoadStatus.DAMAGED, False, StateStoreErrorReason.IO_ERROR, str(error)
            )
        status = LoadStatus.CREATED_DEFAULTS if was_missing else LoadStatus.LOADED
        return StateLoadResult(status, True)

    def reset_damaged(self) -> Path | None:
        """Quarantine damaged SQLite files and create a clean version-one database."""
        result = self.load()
        if result.status is LoadStatus.LOADED:
            return None
        if result.status is LoadStatus.CREATED_DEFAULTS:
            return None

        quarantined: Path | None = None
        try:
            for companion in (
                self.path.with_name(f"{self.path.name}-wal"),
                self.path.with_name(f"{self.path.name}-shm"),
            ):
                if companion.exists() or companion.is_symlink():
                    quarantine_damaged(companion, self.clock)
            if self.path.exists() or self.path.is_symlink():
                quarantined = quarantine_damaged(self.path, self.clock)
        except (OSError, ValueError, SettingsStoreError) as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

        fresh = self.load()
        if fresh.status not in {LoadStatus.CREATED_DEFAULTS, LoadStatus.LOADED}:
            raise StateStoreError(
                fresh.reason or StateStoreErrorReason.MIGRATION_FAILURE,
                path=self.path,
                detail=fresh.detail,
            )
        return quarantined

    @staticmethod
    def _validate_slots(slots: Sequence[Slot]) -> tuple[Slot, ...]:
        frozen_slots = tuple(slots)
        issues = validate_slot_profile(frozen_slots)
        if issues:
            raise StateStoreError(
                StateStoreErrorReason.INVALID_DATA, detail=f"invalid slot profile: {issues!r}"
            )
        return frozen_slots

    @staticmethod
    def _insert_slots(
        connection: sqlite3.Connection, profile_id: str, slots: Sequence[Slot]
    ) -> None:
        connection.executemany(
            "INSERT INTO slots(profile_id, slot_order, key_position, destination_name, color) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (profile_id, index, slot.key_position, slot.destination_name, slot.color)
                for index, slot in enumerate(slots)
            ],
        )

    def _replace_slots(
        self,
        connection: sqlite3.Connection,
        profile_id: str,
        slots: tuple[Slot, ...],
        timestamp: str,
    ) -> ProfileRecord:
        changed = connection.execute(
            "UPDATE profiles SET updated_at = ? WHERE id = ?", (timestamp, profile_id)
        ).rowcount
        if not changed:
            raise StateStoreError(StateStoreErrorReason.PROFILE_NOT_FOUND, detail=profile_id)
        connection.execute("DELETE FROM slots WHERE profile_id = ?", (profile_id,))
        self._insert_slots(connection, profile_id, slots)
        row = connection.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        assert row is not None
        return self._read_profile(connection, row)

    @staticmethod
    def _read_profile(connection: sqlite3.Connection, row: sqlite3.Row) -> ProfileRecord:
        rows = connection.execute(
            "SELECT key_position, destination_name, color FROM slots "
            "WHERE profile_id = ? ORDER BY slot_order",
            (row["id"],),
        ).fetchall()
        slots = tuple(
            Slot(slot["key_position"], slot["destination_name"], slot["color"]) for slot in rows
        )
        return ProfileRecord(
            id=row["id"],
            folder_identity=row["folder_identity"],
            display_path=row["display_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            slots=slots,
        )

    def get_profile_by_identity(self, folder_identity: str) -> ProfileRecord | None:
        """Find a profile by canonical source-folder identity."""
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM profiles WHERE folder_identity = ?", (folder_identity,)
                ).fetchone()
                return None if row is None else self._read_profile(connection, row)
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def list_profiles(self) -> tuple[ProfileRecord, ...]:
        """Return all profiles in creation order."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM profiles ORDER BY created_at, id"
                ).fetchall()
                return tuple(self._read_profile(connection, row) for row in rows)
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def delete_profile(self, profile_id: str) -> None:
        """Delete profile metadata and register rows without touching source/destination files."""
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                profile = connection.execute(
                    "SELECT 1 FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
                if profile is None:
                    raise StateStoreError(
                        StateStoreErrorReason.PROFILE_NOT_FOUND, detail=profile_id
                    )
                pending = connection.execute(
                    "SELECT 1 FROM operations WHERE profile_id = ? AND state = 'started' LIMIT 1",
                    (profile_id,),
                ).fetchone()
                if pending is not None:
                    raise StateStoreError(
                        StateStoreErrorReason.INVALID_DATA,
                        detail="profile has unfinished recovery entries",
                    )
                connection.execute("DELETE FROM operations WHERE profile_id = ?", (profile_id,))
                connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def create_profile_from_template(
        self, folder_identity: str, display_path: str, slots: Sequence[Slot]
    ) -> ProfileRecord:
        """Create an independent profile copy from template slots (FR-041)."""
        frozen_slots = self._validate_slots(slots)
        timestamp = self._timestamp()
        profile_id = uuid.uuid4().hex
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO profiles(id, folder_identity, display_path, created_at, "
                    "updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (profile_id, folder_identity, display_path, timestamp, timestamp),
                )
                self._insert_slots(connection, profile_id, frozen_slots)
                row = connection.execute(
                    "SELECT * FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
                assert row is not None
                return self._read_profile(connection, row)
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def replace_profile_slots(self, profile_id: str, slots: Sequence[Slot]) -> ProfileRecord:
        """Replace a profile's slot rows as one transaction."""
        frozen_slots = self._validate_slots(slots)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                return self._replace_slots(connection, profile_id, frozen_slots, self._timestamp())
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    @staticmethod
    def _slots_json(slots: Sequence[Slot]) -> str:
        return json.dumps(
            [
                {
                    "key_position": slot.key_position,
                    "destination_name": slot.destination_name,
                    "color": slot.color,
                }
                for slot in slots
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _slots_from_json(value: str) -> tuple[Slot, ...]:
        try:
            decoded = json.loads(value)
            if not isinstance(decoded, list):
                raise ValueError("slot data must be a list")
            slots = tuple(
                Slot(item["key_position"], item["destination_name"], item["color"])
                for item in decoded
                if isinstance(item, dict)
            )
            if len(slots) != len(decoded):
                raise ValueError("slot data contains an invalid entry")
            return slots
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise StateStoreError(
                StateStoreErrorReason.INVALID_DATA, detail="invalid target slots in rename journal"
            ) from error

    def start_folder_renames(
        self, profile_id: str, records: tuple[FolderRenameRecord, ...]
    ) -> None:
        """Insert a set of started folder-rename records in one transaction."""
        timestamp = self._timestamp()
        if any(
            record.profile_id != profile_id or record.state is not FolderRenameState.STARTED
            for record in records
        ):
            raise StateStoreError(
                StateStoreErrorReason.INVALID_DATA, detail="invalid rename record"
            )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.executemany(
                    "INSERT INTO folder_renames("
                    "id, profile_id, old_folder, new_folder, intermediate_folder, "
                    "target_slots_json, state, started_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'started', ?, ?)",
                    [
                        (
                            record.id,
                            profile_id,
                            record.old_folder,
                            record.new_folder,
                            record.intermediate_folder,
                            self._slots_json(record.target_slots),
                            record.started_at or timestamp,
                            record.updated_at or timestamp,
                        )
                        for record in records
                    ],
                )
                connection.commit()
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def complete_folder_renames(
        self,
        profile_id: str,
        rename_ids: tuple[str, ...],
        folder_updates: tuple[tuple[str, str], ...],
        removed_folders: tuple[str, ...],
        slots: tuple[Slot, ...],
    ) -> None:
        """Atomically update copy paths and slots and close the rename journal."""
        frozen_slots = self._validate_slots(slots)
        timestamp = self._timestamp()
        if len(set(rename_ids)) != len(rename_ids):
            raise StateStoreError(StateStoreErrorReason.INVALID_DATA, detail="duplicate rename ID")
        if len({new for _, new in folder_updates}) != len(folder_updates):
            raise StateStoreError(
                StateStoreErrorReason.INVALID_DATA, detail="duplicate target folder"
            )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for old_folder, new_folder in folder_updates:
                    if old_folder == new_folder:
                        continue
                    target = connection.execute(
                        "SELECT 1 FROM copies WHERE profile_id = ? AND destination_folder = ? "
                        "LIMIT 1",
                        (profile_id, new_folder),
                    ).fetchone()
                    if target is not None:
                        raise StateStoreError(
                            StateStoreErrorReason.INVALID_DATA,
                            detail=f"copy records already exist for target folder: {new_folder}",
                        )
                    connection.execute(
                        "UPDATE copies SET destination_folder = ? WHERE profile_id = ? "
                        "AND destination_folder = ?",
                        (new_folder, profile_id, old_folder),
                    )
                for folder in removed_folders:
                    connection.execute(
                        "DELETE FROM copies WHERE profile_id = ? AND destination_folder = ?",
                        (profile_id, folder),
                    )
                self._replace_slots(connection, profile_id, frozen_slots, timestamp)
                for rename_id in rename_ids:
                    changed = connection.execute(
                        "UPDATE folder_renames SET state = 'done', updated_at = ? "
                        "WHERE id = ? AND profile_id = ? AND state = 'started'",
                        (timestamp, rename_id, profile_id),
                    ).rowcount
                    if not changed:
                        raise StateStoreError(
                            StateStoreErrorReason.INVALID_DATA,
                            detail=f"rename is missing or not started: {rename_id}",
                        )
                connection.commit()
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def _mark_folder_renames(self, rename_ids: tuple[str, ...], state: FolderRenameState) -> None:
        timestamp = self._timestamp()
        if len(set(rename_ids)) != len(rename_ids):
            raise StateStoreError(StateStoreErrorReason.INVALID_DATA, detail="duplicate rename ID")
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for rename_id in rename_ids:
                    changed = connection.execute(
                        "UPDATE folder_renames SET state = ?, updated_at = ? "
                        "WHERE id = ? AND state = 'started'",
                        (state.value, timestamp, rename_id),
                    ).rowcount
                    if not changed:
                        raise StateStoreError(
                            StateStoreErrorReason.INVALID_DATA,
                            detail=f"rename is missing or not started: {rename_id}",
                        )
                connection.commit()
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def mark_folder_renames_rolled_back(self, rename_ids: tuple[str, ...]) -> None:
        """Mark rename journal entries as rolled back atomically."""
        self._mark_folder_renames(rename_ids, FolderRenameState.ROLLED_BACK)

    def mark_folder_rename_recovered(self, rename_id: str) -> None:
        """Mark one started rename journal entry as recovered."""
        self._mark_folder_renames((rename_id,), FolderRenameState.RECOVERED)

    def unfinished_folder_renames(self) -> tuple[FolderRenameRecord, ...]:
        """Return started folder-rename records in deterministic order."""
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    "SELECT * FROM folder_renames WHERE state = 'started' ORDER BY started_at, id"
                ).fetchall()
            return tuple(
                FolderRenameRecord(
                    id=row["id"],
                    profile_id=row["profile_id"],
                    old_folder=row["old_folder"],
                    new_folder=row["new_folder"],
                    intermediate_folder=row["intermediate_folder"],
                    state=FolderRenameState(row["state"]),
                    started_at=row["started_at"],
                    updated_at=row["updated_at"],
                    target_slots=self._slots_from_json(row["target_slots_json"]),
                )
                for row in rows
            )
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def remove_destination_folder_records(
        self, profile_id: str, destination_folder: str, slots: tuple[Slot, ...]
    ) -> int:
        """Delete all register entries for a folder while replacing profile slots."""
        frozen_slots = self._validate_slots(slots)
        timestamp = self._timestamp()
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                removed = connection.execute(
                    "DELETE FROM copies WHERE profile_id = ? AND destination_folder = ?",
                    (profile_id, destination_folder),
                ).rowcount
                self._replace_slots(connection, profile_id, frozen_slots, timestamp)
                connection.commit()
                return removed
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def remove_copy_records(
        self, profile_id: str, destination_folder: str, names: tuple[str, ...]
    ) -> None:
        """Remove selected copy records for one destination folder atomically."""
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.executemany(
                    "DELETE FROM copies WHERE profile_id = ? AND destination_folder = ? "
                    "AND destination_name = ?",
                    [(profile_id, destination_folder, name) for name in names],
                )
                connection.commit()
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def orphaned_profiles(self, folder_exists: Callable[[str], bool]) -> tuple[ProfileRecord, ...]:
        """Return profiles whose canonical source folder fails the caller's existence check."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM profiles ORDER BY created_at, id"
                ).fetchall()
                profiles = tuple(self._read_profile(connection, row) for row in rows)
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error
        return tuple(profile for profile in profiles if not folder_exists(profile.folder_identity))

    def reassign_profile(
        self,
        profile_id: str,
        folder_identity: str,
        display_path: str,
        *,
        replace_profile_id: str | None = None,
    ) -> ProfileRecord:
        """Reassign profile identity and register paths in one transaction (FR-042)."""
        timestamp = self._timestamp()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                profile = connection.execute(
                    "SELECT folder_identity FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
                if profile is None:
                    raise StateStoreError(
                        StateStoreErrorReason.PROFILE_NOT_FOUND, detail=profile_id
                    )
                target = connection.execute(
                    "SELECT id FROM profiles WHERE folder_identity = ?", (folder_identity,)
                ).fetchone()
                if target is not None and target["id"] != profile_id:
                    if target["id"] != replace_profile_id:
                        raise StateStoreError(
                            StateStoreErrorReason.INVALID_DATA,
                            detail="target folder already has a profile",
                        )
                    target_id = target["id"]
                    has_copies = connection.execute(
                        "SELECT 1 FROM copies WHERE profile_id = ? LIMIT 1", (target_id,)
                    ).fetchone()
                    has_pending = connection.execute(
                        "SELECT 1 FROM operations WHERE profile_id = ? "
                        "AND state = 'started' LIMIT 1",
                        (target_id,),
                    ).fetchone()
                    if has_copies is not None or has_pending is not None:
                        raise StateStoreError(
                            StateStoreErrorReason.INVALID_DATA,
                            detail="target profile contains register or recovery data",
                        )
                    connection.execute("DELETE FROM operations WHERE profile_id = ?", (target_id,))
                    connection.execute("DELETE FROM profiles WHERE id = ?", (target_id,))
                elif replace_profile_id is not None:
                    raise StateStoreError(
                        StateStoreErrorReason.INVALID_DATA,
                        detail="replacement profile is not assigned to the target folder",
                    )
                old_root = Path(profile["folder_identity"])
                new_root = Path(folder_identity)
                copies = connection.execute(
                    "SELECT destination_folder, destination_name FROM copies WHERE profile_id = ?",
                    (profile_id,),
                ).fetchall()
                connection.execute(
                    "UPDATE profiles SET folder_identity = ?, display_path = ?, updated_at = ? "
                    "WHERE id = ?",
                    (folder_identity, display_path, timestamp, profile_id),
                )
                for copy in copies:
                    old_destination = Path(copy["destination_folder"])
                    try:
                        relative_destination = old_destination.relative_to(old_root)
                    except ValueError:
                        relative_destination = Path(copy["destination_name"]).parent
                    new_destination = new_root / relative_destination
                    connection.execute(
                        "UPDATE copies SET source_folder = ?, destination_folder = ? "
                        "WHERE profile_id = ? AND destination_folder = ? AND destination_name = ?",
                        (
                            folder_identity,
                            str(new_destination),
                            profile_id,
                            copy["destination_folder"],
                            copy["destination_name"],
                        ),
                    )
                row = connection.execute(
                    "SELECT * FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
                assert row is not None
                return self._read_profile(connection, row)
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def copy_records(
        self,
        profile_id: str,
        destination_folder: str | None = None,
        source_name: str | None = None,
    ) -> tuple[CopyRecord, ...]:
        """Read copy entries by profile and optional destination-folder/source-name filter."""
        clauses = ["profile_id = ?"]
        values: list[str] = [profile_id]
        if destination_folder is not None:
            clauses.append("destination_folder = ?")
            values.append(destination_folder)
        if source_name is not None:
            clauses.append("source_name = ?")
            values.append(source_name)
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    f"SELECT * FROM copies WHERE {' AND '.join(clauses)} "
                    "ORDER BY destination_folder, destination_name",
                    values,
                ).fetchall()
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error
        return tuple(
            CopyRecord(
                profile_id=row["profile_id"],
                source_folder=row["source_folder"],
                source_name=row["source_name"],
                destination_folder=row["destination_folder"],
                destination_name=row["destination_name"],
                size=row["size"],
                sha256=row["sha256"],
                mtime_ns=row["mtime_ns"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def remove_copy_record(
        self, profile_id: str, destination_folder: str, destination_name: str
    ) -> None:
        """Remove one missing or successfully unlinked copy-register record."""
        try:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM copies WHERE profile_id = ? AND destination_folder = ? "
                    "AND destination_name = ?",
                    (profile_id, destination_folder, destination_name),
                )
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def start_operation(
        self,
        operation_id: str,
        profile_id: str,
        destination_name: str,
        files: Sequence[OperationFileRecord],
    ) -> OperationRecord:
        """Commit a started operation and every expected file before filesystem writes (FR-046)."""
        timestamp = self._timestamp()
        try:
            temp_file_name(operation_id, 0)
        except ValueError as error:
            raise StateStoreError(
                StateStoreErrorReason.INVALID_DATA, detail="operation ID must be UUID4 hex"
            ) from error
        ordered_files = tuple(sorted(files, key=lambda item: item.index))
        for index, item in enumerate(ordered_files):
            simple_final_name = (
                bool(item.final_name)
                and item.final_name not in {".", ".."}
                and Path(item.final_name).name == item.final_name
                and "/" not in item.final_name
                and chr(92) not in item.final_name
            )
            valid_digest = len(item.expected_sha256) == 64 and all(
                character in "0123456789abcdefABCDEF" for character in item.expected_sha256
            )
            if (
                item.index != index
                or item.temp_name != temp_file_name(operation_id, item.index)
                or not simple_final_name
                or item.expected_size < 0
                or not valid_digest
            ):
                raise StateStoreError(
                    StateStoreErrorReason.INVALID_DATA,
                    detail="operation file names, indexes, or fingerprints are invalid",
                )
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO operations(id, profile_id, destination_name, state, "
                    "started_at, updated_at) "
                    "VALUES (?, ?, ?, 'started', ?, ?)",
                    (operation_id, profile_id, destination_name, timestamp, timestamp),
                )
                connection.executemany(
                    'INSERT INTO operation_files(operation_id, "index", temp_name, final_name, '
                    "expected_size, expected_sha256) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (
                            operation_id,
                            file.index,
                            file.temp_name,
                            file.final_name,
                            file.expected_size,
                            file.expected_sha256,
                        )
                        for file in ordered_files
                    ],
                )
                return OperationRecord(
                    operation_id,
                    profile_id,
                    destination_name,
                    OperationState.STARTED,
                    timestamp,
                    timestamp,
                    ordered_files,
                )
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def complete_operation(self, operation_id: str, copies: Sequence[CopyRecord]) -> None:
        """Atomically insert managed-copy rows and close the operation as done."""
        timestamp = self._timestamp()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                operation = connection.execute(
                    "SELECT profile_id, state FROM operations WHERE id = ?", (operation_id,)
                ).fetchone()
                if operation is None:
                    raise StateStoreError(
                        StateStoreErrorReason.OPERATION_NOT_FOUND, detail=operation_id
                    )
                if operation["state"] != OperationState.STARTED.value:
                    raise StateStoreError(
                        StateStoreErrorReason.INVALID_DATA, detail="operation is not started"
                    )
                for copy in copies:
                    if copy.profile_id != operation["profile_id"]:
                        raise StateStoreError(
                            StateStoreErrorReason.INVALID_DATA, detail="copy profile mismatch"
                        )
                    connection.execute(
                        "INSERT INTO copies("
                        "profile_id, source_folder, source_name, destination_folder, "
                        "destination_name, size, sha256, mtime_ns, "
                        "created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            copy.profile_id,
                            copy.source_folder,
                            copy.source_name,
                            copy.destination_folder,
                            copy.destination_name,
                            copy.size,
                            copy.sha256,
                            copy.mtime_ns,
                            timestamp,
                        ),
                    )
                connection.execute(
                    "UPDATE operations SET state = 'done', updated_at = ? WHERE id = ?",
                    (timestamp, operation_id),
                )
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def _mark_operation(self, operation_id: str, state: OperationState) -> None:
        timestamp = self._timestamp()
        try:
            with self._connect() as connection:
                changed = connection.execute(
                    "UPDATE operations SET state = ?, updated_at = ? "
                    "WHERE id = ? AND state = 'started'",
                    (state.value, timestamp, operation_id),
                ).rowcount
                if not changed:
                    exists = connection.execute(
                        "SELECT 1 FROM operations WHERE id = ?", (operation_id,)
                    ).fetchone()
                    reason = (
                        StateStoreErrorReason.OPERATION_NOT_FOUND
                        if exists is None
                        else StateStoreErrorReason.INVALID_DATA
                    )
                    raise StateStoreError(reason, detail=operation_id)
        except StateStoreError:
            raise
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error

    def mark_rolled_back(self, operation_id: str) -> None:
        """Close a failed operation as rolled back."""
        self._mark_operation(operation_id, OperationState.ROLLED_BACK)

    def mark_recovered(self, operation_id: str) -> None:
        """Close a crash-recovered operation."""
        self._mark_operation(operation_id, OperationState.RECOVERED)

    def unfinished_operations(self) -> tuple[OperationRecord, ...]:
        """Return all started journal records with their file rows, ordered by start time."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM operations WHERE state = 'started' ORDER BY started_at, id"
                ).fetchall()
                result: list[OperationRecord] = []
                for row in rows:
                    file_rows = connection.execute(
                        'SELECT "index", temp_name, final_name, expected_size, expected_sha256 '
                        'FROM operation_files WHERE operation_id = ? ORDER BY "index"',
                        (row["id"],),
                    ).fetchall()
                    files = tuple(
                        OperationFileRecord(
                            index=file_row["index"],
                            temp_name=file_row["temp_name"],
                            final_name=file_row["final_name"],
                            expected_size=file_row["expected_size"],
                            expected_sha256=file_row["expected_sha256"],
                        )
                        for file_row in file_rows
                    )
                    result.append(
                        OperationRecord(
                            row["id"],
                            row["profile_id"],
                            row["destination_name"],
                            OperationState(row["state"]),
                            row["started_at"],
                            row["updated_at"],
                            files,
                        )
                    )
                return tuple(result)
        except sqlite3.Error as error:
            raise StateStoreError(
                StateStoreErrorReason.IO_ERROR, path=self.path, detail=str(error)
            ) from error
