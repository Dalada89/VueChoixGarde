# Plan: FileSystemPort.file_metadata for automatic reconciliation

## Context

- FR-070 requires reconciliation on every folder open (automatic) and as a manual command.
- technical-design.md §5.5: per register entry, `stat` the destination file. Missing -> remove entry. Size differs -> `modified`. If size and `mtime_ns` equal the values stored at finalization, the hash check MAY be skipped in automatic mode. Manual reconcile always hashes. FR-050 (toggle) always hashes, so the shortcut never influences a delete decision.
- Current `FileSystemPort` (`ports/filesystem.py`) offers only `fingerprint_file(source_root, path)`. It always streams the full SHA-256. With 10,000 images this makes automatic reconciliation read every copied file on every folder open, which breaks the performance intent (NFR-010/011, risk table in the design, "background reconciliation with `mtime_ns` shortcut").
- The port has no way to ask "does it exist, how large, what mtime" without hashing. Without one, the shortcut cannot be implemented in the `app` layer, which must not touch `os`/`pathlib.stat`.
- Instruction from the task: ask before adding a further port method. This plan is that request. Approval of the plan = approval of exactly one method.

## Decision

Add one read-only metadata method; do not change `fingerprint_file`.

```python
# ports/models.py
@dataclass(frozen=True)
class FileMetadata:
    size: int
    mtime_ns: int


# ports/filesystem.py (FileSystemPort)
def file_metadata(self, source_root: Path, path: Path) -> FileMetadata | None:
    """Return size and mtime_ns of a contained regular file without reading content; None if absent."""
```

Semantics:
- Missing file (`FileNotFoundError`) -> `None` (reconcile removes the entry).
- Outside root -> `FileSystemError(PATH_OUTSIDE_ROOT)`, same containment check as `fingerprint_file`.
- Symlink/junction or non-regular file -> `FileSystemError(IO_ERROR, "not a regular file")`. Use `lstat` plus the existing `_is_link_or_junction`, so a link is never treated as an unchanged copy (stricter than `fingerprint_file`, which uses `stat`).
- Other `OSError` -> `FileSystemError(IO_ERROR)`.
- No file contents are opened.

Alternatives rejected:
- Add a `hash: bool` flag to `fingerprint_file`: mixes two return shapes, makes `sha256` optional, weakens the type.
- `FileFingerprint` with optional hash: same problem.
- Do `stat` in `app`: violates layer rules (banned-import check).

## Affected files

- `src/vuechoixgarde/ports/models.py`: add `FileMetadata`.
- `src/vuechoixgarde/ports/filesystem.py`: add `file_metadata` to `FileSystemPort`.
- `src/vuechoixgarde/fsops/filesystem.py`: add module function `file_metadata` next to `fingerprint_file` (line ~243); expose it on `LocalFileSystem` the same way `fingerprint_file` is exposed (confirm the wrapper location first; tests call `LocalFileSystem.fingerprint_file`).
- `tests/integration/test_fsops.py`: new tests.
- `tests/fakes/` (Phase 4): the fault-injecting filesystem implements `file_metadata`.
- `src/vuechoixgarde/app/reconcile.py` (Phase 4): uses it.
- `.deutschlandgpt/plans/phase-4-app-applog.md`: add `FileMetadata`/`file_metadata` to the "Extend ports only where explicitly required" line.
- `.deutschlandgpt/handoff.md`: mention the additional port method.

## Steps

1. Implement `FileMetadata` and port method (type-only first, run pyright).
2. Implement in fsops with `lstat`, containment, link check; reuse `_raise_fs_error`.
3. Integration tests (`tmp_path`, source guard): returns correct size/mtime_ns; equals the values from `fingerprint_file`; missing -> `None`; outside root -> error; symlink -> error; directory -> error; file content is not read (monkeypatch `Path.open`/`_hash_stream` to raise and assert no call).
4. Reconciliation logic in `app/reconcile.py`, per register entry:
   - `metadata = fs.file_metadata(...)`; `None` -> remove entry.
   - `metadata.size != record.size` -> MODIFIED (no hash needed).
   - Automatic mode and `metadata.mtime_ns == record.mtime_ns` -> unchanged, no hash (E9 shortcut).
   - Otherwise (manual mode, or mtime differs) -> `fingerprint_file`; sha equals -> unchanged (optionally refresh stored mtime only if the state port already allows it; otherwise leave the register alone), differs -> MODIFIED.
   - Reconciliation never creates, changes or deletes image/sidecar files (FR-070).
5. Unit tests for reconcile with fake filesystem counting `fingerprint_file` calls: automatic + unchanged -> 0 hashes; manual + unchanged -> 1 hash per entry; automatic + mtime changed -> hashes; size changed -> no hash, MODIFIED; missing -> removed; error on one entry does not abort the others.
6. Update plan/handoff docs as listed.
7. Run: `uv sync --locked`, `ruff format`, `ruff check`, `pyright`, `pytest`, banned-import check for `app`/`applog`.

## Risks

- mtime shortcut can miss a same-size, same-mtime content change (a tool that restores mtime). Accepted by the design; only automatic mode, never used for delete decisions (FR-050 hashes).
- Coarse mtime resolution on some filesystems (FAT, 2 s): a change within the resolution window is missed in automatic mode; manual reconcile covers it.
- Phase 3 is still uncommitted (`main` ahead 1, many modified files): recommend committing Phase 3 separately before adding this change so the diff stays reviewable.
- Do not modify requirements/technical-design/ADRs: the design already allows this shortcut (§5.5), so no document change is needed.
