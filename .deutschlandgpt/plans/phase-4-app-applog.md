# Phase 4 implementation plan: app and applog

## Architecture

- Keep `app` synchronous and Qt-free. It imports only `core`, `ports`, and the standard library. A non-blocking `OperationGate` serializes toggles and reconciliation.
- Keep `applog` adapter-only: JSONL formatter and rotating `logging` handler depend on `ports` plus the standard library. Logger failures are contained.
- Extend ports only where explicitly required: `EventLogger`/log enums, `FolderLockFactory`, damaged-store reset methods, and `FileMetadata`/`FileSystemPort.file_metadata` for FR-070's automatic mtime shortcut. Add a concrete factory around `LocalFolderLock`.
- Retain all Phase 3 adapter safety behavior; use injected stores, filesystem, clock, lock factory, and logger throughout.

## Modules and public API sketch

- `ports/log.py`: `LogLevel`, `LogEvent`, `EventLogger.log(level, event, message, **fields)`.
- `ports/lock.py`: `FolderLockFactory.create(identity) -> FolderLock`.
- `store/settings.py`, `store/state.py`: `reset_damaged() -> Path | None`; quarantine the damaged primary (and SQLite WAL/SHM companions), then establish fresh defaults/schema.
- `fsops/lock.py`: `LocalFolderLockFactory`.
- `applog/jsonl.py`: `JsonlFormatter` and `JsonlEventLogger(log_dir, clock=..., max_bytes, backup_count)` using only the injected clock for timestamps; `close()`.
- `app/results.py`: frozen result, snapshot, plan, report, and UI-neutral reason/status values.
- `app/startup.py`: load startup settings/state; explicit accept/decline damaged data.
- `app/recovery.py`, `app/reconcile.py`: journal-only recovery and automatic/manual reconciliation.
- `app/toggle.py`: `plan_toggle` and `execute_toggle` with fresh classification, confirmation, rollback, and gate behavior.
- `app/session.py`: `FolderSession` for lock lifecycle, folder open/close, navigation, refresh, sorting, read-model derivation, naming, and manual reconciliation.
- `app/keys.py`: persist changed learned labels through the settings store only when allowed.
- `tests/fakes/`: protocol-conforming in-memory stores, fake logger/lock factory, and fault-injecting filesystem.

## Tests

- Unit: app result/read-model classifications; operation-gate busy/repeat; navigation boundaries, sort and refresh; empty session; naming and profile validation; two-phase toggle state changes and confirmation; startup damaged/created/loaded matrix; learned-label persistence only on changes; recovery/reconciliation classifications.
- Integration: JSONL format/rotation/Unicode/write errors/privacy; damaged settings and SQLite quarantine; real-adapter folder locking/session lifecycle; byte-exact toggle on/off, sidecars, conflict and modified-copy handling; stale records; rollback and recovery under fault injection and simulated crashes; automatic-vs-manual reconciliation; faulty destinations and profile isolation. All file tests use `tmp_path` and the source guard.

## Verification

Run `uv sync --locked`, Ruff format/check, pyright, pytest, package `ruff check --show-settings` for `app` and `applog`, and a temporary banned-import regression check. Do not modify requirements, technical design, ADRs, or commit changes. Update `.deutschlandgpt/handoff.md` with Phase 4 outcomes and remaining UI/imaging work.
