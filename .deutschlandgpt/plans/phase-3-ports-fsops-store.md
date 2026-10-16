# Phase 3 implementation plan — ports, fsops, store

## Scope and constraints

Implement only Phase 3: pure `core` additions, Qt keyboard regression coverage, `ports` protocols/data/errors, real `fsops` adapters, `store` settings/SQLite persistence, and unit/integration tests. Do not change `app`, `imaging`, `applog`, `i18n`, UI behavior beyond the requested Windows keyboard test, `bootstrap`, or any file in `docs/requirements.md`, `docs/technical-design.md`, or `docs/adr/`. Do not add dependencies or commit.

## Modules and public APIs

### Core

- `core.slots.ProfileIssue(error: ProfileError, slot_indexes: tuple[int, ...], name_error: FolderNameError | None = None)`; `validate_slot_profile(slots: Sequence[Slot]) -> tuple[ProfileIssue, ...]`. Collision issues identify every involved slot index; invalid destination names carry the exact `FolderNameError` and one slot index.
- `core.temp_names.temp_file_name(operation_id: str, index: int) -> str`; `is_reserved_temp_name(name: str) -> bool`. Accept canonical UUID4 hex operation IDs (32 lowercase hexadecimal characters), non-negative integer indexes (decimal, no leading zeros except zero); compare reserved patterns using `comparison_key`.
- `core.language.default_language(locale_name: str | None) -> Literal["de", "en", "fr"]`; map locale language prefixes and use English for missing/unsupported locales.
- Add a raw Windows keyboard test: scan code `0x11` maps to `KeyW`, regardless of the virtual-key value.

### Ports

- `ports.models`: frozen values `FileFingerprint(size, sha256, mtime_ns)`, `SourceScan(images, sidecar_candidates, directories)`, `DestinationStatus`, `DestinationFault`, `DestinationResolution(status, exact_name, reason)`, `ProfileRecord`, `CopyRecord`, `OperationFileRecord`, `OperationRecord`, and typed settings/state load results and settings values.
- `ports.errors`: stable `StrEnum` reason sets and `PortError` subclasses `FileSystemError`, `FolderLockError`, `SettingsStoreError`, and `StateStoreError`; each exposes a translatable reason and optional path/detail.
- `ports.filesystem`: `SourceFolderScanner.check_source_folder(path: Path) -> None`, `folder_identity(path: Path) -> str`, `scan_source_folder(path: Path) -> SourceScan`; `FileSystemPort` methods `resolve_destination_folder(source_root, destination_name) -> DestinationResolution`, `create_destination_folder(source_root, destination_name) -> Path`, `list_destination_names(source_root, destination_folder) -> tuple[str, ...]`, `fingerprint_file(source_root, path) -> FileFingerprint`, `copy_to_temp(source_root, destination_folder, source_name, temp_name) -> FileFingerprint`, `finalize_temp_file(source_root, destination_folder, temp_name, final_name) -> Path`, `delete_verified_file(source_root, destination_folder, name, expected_size, expected_sha256) -> None`, `delete_modified_copy(source_root, destination_folder, name) -> None`, and `delete_own_temp_file(source_root, destination_folder, name) -> None`.
- `ports.lock.FolderLock`: acquire, release, and context-manager protocol.
- `ports.clock.Clock.now_utc() -> datetime`.
- `ports.settings.SettingsStore`: `load(locale_name: str | None) -> SettingsLoadResult`, `save(settings: Settings) -> None`.
- `ports.state.StateStore`: `load() -> StateLoadResult`; `get_profile_by_identity(folder_identity: str) -> ProfileRecord | None`; `create_profile_from_template(folder_identity: str, display_path: str, slots: Sequence[Slot]) -> ProfileRecord`; `replace_profile_slots(profile_id: str, slots: Sequence[Slot]) -> ProfileRecord`; `orphaned_profiles(folder_exists: Callable[[str], bool]) -> tuple[ProfileRecord, ...]`; `reassign_profile(profile_id: str, folder_identity: str, display_path: str) -> ProfileRecord`; `copy_records(profile_id: str, destination_folder: str | None = None, source_name: str | None = None) -> tuple[CopyRecord, ...]`; `remove_copy_record(profile_id: str, destination_folder: str, destination_name: str) -> None`; `start_operation(operation_id: str, profile_id: str, destination_name: str, files: Sequence[OperationFileRecord]) -> OperationRecord`; `complete_operation(operation_id: str, copies: Sequence[CopyRecord]) -> None`; `mark_rolled_back(operation_id: str) -> None`; `mark_recovered(operation_id: str) -> None`; `unfinished_operations() -> tuple[OperationRecord, ...]`. The implementation gets timestamps from its injected `Clock` and serializes them as UTC ISO-8601.

### Filesystem adapters

- `fsops.filesystem.LocalFileSystem` implements both scanner and filesystem protocols. Public module functions: `is_inside(path: Path, root: Path) -> bool`, `extended_path(path: Path) -> Path`, `check_source_folder(path: Path) -> None`, `folder_identity(path: Path) -> str`, `scan_source_folder(path: Path) -> SourceScan`, `fingerprint_file(source_root: Path, path: Path) -> FileFingerprint`, and the methods listed on `FileSystemPort`.
- Every write is containment-checked. Scans use one `os.scandir` pass and retain exact directory-entry names. Symlink/junction inclusion requires a regular-file target resolving inside the source root. Exclude all hidden and reserved-temp entries.
- Copy creates with exclusive `os.open`, hashes while streaming, fsyncs, re-reads and verifies, then applies source `mtime_ns`; all failures remove the newly-created temp file and raise a port error. Finalize conflicts leave the temp file intact for caller cleanup.
- Finalize with `os.rename` on Windows; `os.link` then unlink on POSIX; only these unsupported-link errors trigger the no-replace ctypes fallback: `EPERM`, `EOPNOTSUPP`/`ENOTSUP`, `EMLINK`, `EXDEV`. Linux uses `renameat2(AT_FDCWD=-100, ..., RENAME_NOREPLACE=1)`; macOS uses `renamex_np(..., RENAME_EXCL=0x4)`. Constants checked against Linux kernel UAPI/man-pages and Apple XNU `bsd/sys/stdio.h`. No overwriting fallback; unavailable primitives raise `FINALIZE_UNSUPPORTED`.
- `fsops.lock.LocalFolderLock` uses `filelock.FileLock(timeout=0)` under `locks/` and SHA-256(identity), supports explicit release and `with`.
- `fsops.clock.SystemClock.now_utc() -> datetime` returns an aware UTC datetime.

### Store adapters

- `store.paths.application_data_dir(root: Path | None = None) -> Path`; `prepare_application_data(root: Path) -> None` ensures root, `locks/`, and `logs/`.
- `store.settings.JsonSettingsStore(root: Path, clock: Clock)` implements `load(locale_name: str | None = None) -> SettingsLoadResult`, `save(settings: Settings) -> None`, and `validate_settings(settings: Settings) -> None`. Defaults use `DEFAULT_SLOTS` plus injected locale. Atomic write is same-directory temp + flush/fsync + `Path.replace` (the app-data overwrite is allowed).
- `store.state.SQLiteStateStore(root: Path, clock: Clock)` implements `StateStore`, schema version 1/WAL/foreign keys, 0→1 migration, and a child `operation_files` table. `operations` stores operation state/timestamps only. Database damage is reported without mutating the existing file.
- `store.damage.quarantine_damaged(path: Path, clock: Clock) -> Path` chooses `.damaged-<UTC timestamp>` then numbered suffixes without replacing an existing file; returns the chosen path.

## Error reasons

Filesystem reasons: `SOURCE_MISSING`, `SOURCE_NOT_DIRECTORY`, `SOURCE_NOT_READABLE`, `PATH_OUTSIDE_ROOT`, `DESTINATION_FILE`, `DESTINATION_LINK`, `DESTINATION_OUTSIDE`, `AMBIGUOUS`, `INVALID_NAME`, `NAME_CONFLICT`, `INVALID_TEMP_NAME`, `COPY_FAILED`, `FILE_CHANGED`, `DELETE_REFUSED`, `FINALIZE_UNSUPPORTED`, and `IO_ERROR`. Lock errors use `FolderLockErrorReason.FOLDER_LOCKED`/`LOCK_IO_ERROR`; settings/state errors separately distinguish malformed/invalid JSON/settings, SQLite open/integrity/version/schema failures, missing profile/operation, and generic storage I/O. Load results distinguish `LOADED`, `CREATED_DEFAULTS`, and `DAMAGED` without overwriting damaged data.

## Test plan

- Unit: profile collision indexes and per-slot folder-name errors; UUID temp-name validation/comparison; supported default locales and fallback; settings field/type/language/sort/color/slot/learned-label validation; Windows raw-key scan-code selection.
- Integration under `tmp_path`: source snapshot guard (relative names + SHA-256; only approved destination directories may be added); exact EXIF JPEG copy and mtime preservation; fault injection for writes/fsync/temp reread mismatch/utime/missing source; finalize exact/casefold conflict, Linux link-fallback to renameat2, unsupported finalization and no overwrite; scanner hidden/unsupported/temp/folder/symlink cases; destination `FOUND`/`NOT_FOUND`/faults/ambiguous casefold names; verified/modified/temp deletion safeguards; lock contention in a child process; Windows long paths conditionally.
- Store integration under `tmp_path`: new defaults, settings/state round-trip, schema migration/WAL, damaged JSON and SQLite non-mutation, quarantine collisions, profile template copy/slot update/orphan filtering/reassignment transaction, copy-register remove operations, journal completion rollback atomicity and unfinished states.
- Run required command sequence: `uv sync --locked`; `uv run ruff format --check`; `uv run ruff check`; `uv run pyright`; `uv run pytest`; and verify per-file Ruff PySide6 bans for `fsops`, `store`, and `ports`.

## Explicit interpretation choices

- A destination with multiple immediate subdirectories sharing one `comparison_key` resolves as `FAULTY(AMBIGUOUS)`.
- Journal per-file rows live in `operation_files`; `operations` has one row per operation and state/timestamps.
- Hardlink fallback catches only the four platform errors listed above; other I/O errors propagate as typed failures rather than trying a different primitive.
