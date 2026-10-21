# Technical Design — VueChoixGarde

**Document type:** Technical design (implementation concept)  
**Version:** 0.2 (draft)  
**Date:** 2026-10-16  
**Based on:** [Product Requirements (SRS) v0.6](requirements.md)  
**Decision record:** [ADR 0001 — Technology choice](adr/0001-technology-choice.md)

## 1. Purpose and scope

The SRS describes *what* VueChoixGarde must do and deliberately leaves the technology open (SRS 1.2). This document describes *how* Version 1 is built: the chosen technology stack, the architecture, data formats, the copy and removal procedures, platform-specific details, the tooling and the test and release strategy.

Requirement IDs (`FR-…`, `NFR-…`) refer to the SRS. Where this design deviates from or interprets the SRS, it says so explicitly (see Section 13).

Guiding constraints:

- Everything runs locally. No network access, no accounts, no update mechanism (NFR-005, SRS 3.2).
- Source files are never changed (NFR-001); uncertainty never leads to deletion or overwriting (NFR-003).
- The same behavior on Linux, Windows and macOS (NFR-040).

## 2. Evaluated variants

Four locally running variants were evaluated. Details and the reasoning behind the decision are recorded in [ADR 0001](adr/0001-technology-choice.md).

| Criterion | A: Python + PySide6 + Pillow | B: Electron + Vue + sharp | C: Tauri 2 + Vue + Rust | D: Browser app |
|---|---|---|---|---|
| HEIC/HEIF decoding (FR-004) | Yes, on all three platforms (via `pi-heif`) | No (prebuilt sharp has no HEVC decoder) | Possible (`libheif-rs`), build effort | No |
| Physical key + layout label (FR-081) | Position: yes. Label: needs native code per OS or a fallback | Yes (`KeyboardEvent.code` + `getLayoutMap()`) | Position: yes. Label: native code per OS | Chromium only |
| Identical behavior (NFR-040) | Good (one toolkit, Qt) | Very good (one engine) | Weaker (three different webviews) | Chromium only |
| Safe file operations (FR-046, NFR-002) | Full OS access | Full OS access | Full OS access | Not possible (no symlink resolution, no non-overwriting rename) |
| Testability without window (NFR-030) | Very good (pure Python core) | Good | Very good | Limited |
| Package size | ~80–150 MB | ~150–250 MB | ~10–20 MB | none |
| Team / language fit | Python | TypeScript | Rust + TypeScript | TypeScript |

**Decision: Variant A** — Python, PySide6 (Qt 6), Pillow with `pi-heif`, managed with `uv`, linted and formatted with `ruff`.

Main reasons: HEIC/HEIF support on all platforms is valued higher than a perfect key label on first start; Python is the preferred language; Qt provides native dialogs, application data paths, sound and a consistent widget toolkit on all three platforms. The accepted trade-off for FR-081 is described in Section 8.1.

## 3. Technology stack

| Area | Choice | Notes |
|---|---|---|
| Language / runtime | CPython 3.13 for development and releases; `requires-python >= 3.12` | 3.12 is the minimum because of `Path.is_junction()` (NFR-002) |
| Package and project manager | **uv** | `pyproject.toml`, `uv.lock` (committed), `.python-version`; dev tools in `[dependency-groups]` |
| Linter and formatter | **ruff** (`ruff check`, `ruff format`) | Configuration in `pyproject.toml`, see Section 11.2 |
| Static type checker | **pyright** (mode `standard`) | Development tool only, see Section 11.4 |
| GUI toolkit | PySide6 (Qt 6, Qt Widgets) | Widgets, not QML: simpler, fully keyboard-driven, easy to test with pytest-qt |
| Image decoding | Pillow | JPEG, PNG, GIF, BMP, TIFF, WebP; EXIF orientation via `ImageOps.exif_transpose` |
| HEIC/HEIF | `pi-heif` (decoder-only variant of `pillow-heif`) | Registered as a Pillow plugin; no encoder bundled, see Section 8.6 |
| Application data location | `platformdirs` | Per-user, non-roaming data directory (Section 6.1) |
| Single-instance lock | `filelock` | OS-level lock file in the application data (NFR-043) |
| Persistence | `sqlite3` (standard library) + JSON settings file | Section 6 |
| Hashing | `hashlib` SHA-256 (standard library) | Content hash for the copy register |
| Logging | `logging` (standard library) + own JSON Lines formatter + `RotatingFileHandler` | FR-091, FR-092 |
| Sound | `QSoundEffect` (QtMultimedia) with a bundled short WAV file | FR-057 |
| Tests | pytest, pytest-qt | Section 11.3 |
| Packaging | PyInstaller (one-folder mode) | Section 12 |
| CI / releases | GitHub Actions, GitHub Releases | NFR-044 |

No other runtime dependencies are planned. Every new dependency must be local-only (no network features used) and license-compatible (Section 12.4).

## 4. Architecture

### 4.1 Layers

The application is split into layers so that the application logic can be tested without a window and without real user images (NFR-030). Dependencies only point downwards: `ui` uses `app`; `app` uses `core` and the interfaces in `ports`; `fsops`, `store`, `imaging` and `applog` implement those interfaces; `bootstrap` wires everything together. The core knows neither Qt nor the real file system.

| Package | Responsibility | Depends on Qt? |
|---|---|---|
| `core` | Domain types and pure rules: format list (FR-004), sidecar matching (FR-043), natural sort (FR-008), navigation and boundaries (FR-024/025), slot and folder-name validation (FR-033/034), key positions and allowed keys (FR-082), toggle decision (FR-044–FR-050), name comparison keys (NFR-041) | No |
| `ports` | `typing.Protocol` interfaces the application layer uses: file system, register, settings, image decoder, clock, log | No |
| `app` | Use cases and session state: open folder, refresh, navigate, toggle slot, reconcile, manage profiles; enforces “one operation at a time” (FR-051) | No |
| `fsops` | Directory scanning, hidden/symlink/junction detection, path containment checks, safe copy, non-overwriting finalization, deletion of verified copies | No |
| `store` | Settings file, SQLite database (profiles, copy register, operation journal), schema migrations, handling of damaged data | No |
| `imaging` | Decoding, EXIF orientation, first frame, downscaling, preload cache | No (returns raw RGB(A) buffers) |
| `applog` | JSON Lines formatter, rotation, event types | No |
| `ui` | Main window, slot bar, dialogs, keyboard handling, translations, styling, sound | Yes |
| `bootstrap` | Composition root: resolves paths, creates the concrete adapters, wires them into `app` and `ui` | Yes |

### 4.2 Planned repository layout

```
pyproject.toml          # project metadata, dependencies, ruff and pytest configuration
uv.lock                 # locked dependency versions (committed)
.python-version         # Python version used by uv
src/vuechoixgarde/
    __main__.py         # entry point (python -m vuechoixgarde)
    bootstrap.py
    core/
    ports/
    app/
    fsops/
    store/
    imaging/
    applog/
    ui/
    i18n/               # de.json, en.json, fr.json
    resources/          # sound, icons, Qt style sheet
tests/
    unit/
    integration/
    ui/
    data/               # small bundled test images (incl. one HEIC), with license notes
packaging/              # PyInstaller spec, platform notes
docs/
```

The `src` layout prevents tests from accidentally importing the working directory instead of the installed package.

### 4.3 Concurrency model

- **UI thread:** Qt event loop only; no file I/O or decoding (NFR-012). Settings values, including profile slots, rename intent, language, sound and learned labels, are copied into an immutable submission on the UI thread before a worker starts.
- **File operations:** exactly one worker (single-thread executor). The `app` layer holds an “operation running” flag; slot activations while it is set are ignored with brief feedback (FR-051). Workers receive immutable values and never read Qt widgets.
- **Image decoding:** a small thread pool (2 workers). Each request carries a generation number; results for an image that is no longer current or a neighbor are discarded (FR-026).
- **Reconciliation:** runs on the file-operation worker so it never overlaps with a toggle; shows a busy indicator after ~1 s (NFR-012).
- Results are passed back to the UI thread via Qt signals (queued connections).

## 5. Main flows

### 5.1 Opening a source folder (FR-001–FR-010, FR-040, FR-041, FR-070, NFR-043)

1. Folder chosen via `QFileDialog.getExistingDirectory` (native dialog) or from the “last folder” setting (FR-010).
2. Validate: exists, is a directory, is readable (FR-002).
3. Compute the **folder identity** (Section 8.4) and acquire the single-instance lock for it (Section 8.5). If the lock is held by another instance, refuse with a message (NFR-043).
4. Scan the top level (Section 8.3) and build the image list; sort (FR-008/009).
5. Load the destination profile for the folder identity; if none exists, copy the global slot template (FR-041).
6. Recover any interrupted destination-folder rename from `folder_renames` before copy recovery or reconciliation (Section 5.5).
7. Clean up own temporary files from interrupted runs using the copy-operation journal (FR-046, Section 5.4).
8. Run reconciliation in the background (FR-070); slot states are shown as “checking” until it finishes.

### 5.2 Toggle decision (FR-044–FR-050, FR-063)

When a slot key is pressed, the `app` layer captures the current image *at the time of the key press* (FR-052) and runs, on the file-operation worker:

1. **Guard:** ignore if an operation is running or the key event is an auto-repeat (FR-051).
2. **Name:** if the slot has no destination folder name, ask for one (FR-035). Cancelling ends the flow without any file operation.
3. **Resolve destination folder** (FR-036–FR-038): look for a direct subfolder whose comparison key (Section 8.2) equals the slot's name key.
   - Found and a real directory inside the source folder → use it.
   - Found but a file, a symbolic link, a junction, or resolving outside the source folder → slot is *faulty*, stop.
   - Not found → it will be created during toggle on.
4. **Determine the file set:** the image plus its sidecar files according to FR-043, determined from a fresh listing of the source folder.
5. **Check the actual state** (FR-050): for each file of the set, list the destination folder, match names case-insensitively and classify the target name as one of:

   | Class | Meaning |
   |---|---|
   | `absent` | No file with this name (case-insensitive) |
   | `verified` | Register entry exists, file present, size and SHA-256 match |
   | `modified` | Register entry exists, file present, size or hash differ |
   | `foreign` | File present but no register entry → conflict file |
   | `stale` | Register entry exists, file missing → entry is removed, then treated as `absent` |

   If the copy register is unavailable (FR-063), every present file is `foreign`.
6. **Decide** based on the class of the **image** file:
   - `verified` → toggle off (Section 5.3).
   - `modified` → toggle off with confirmation (FR-049).
   - `absent` → toggle on (Section 5.4), unless any sidecar target is `foreign` or `modified` → conflict, nothing is copied (FR-044, FR-047). Sidecar targets that are `verified` (shared stem) are not copied again.
   - `foreign` → conflict (FR-047).
7. Report the result (FR-056/057/058, FR-090) and update the slot states (FR-073).

### 5.3 Toggle off (FR-048, FR-049, NFR-003)

1. Collect the `verified`/`modified` targets of the image and its sidecars. A sidecar copy that still belongs to another image which is selected in the same destination is kept (FR-048).
2. If any target is `modified`, show a confirmation dialog naming the affected files; the default button is “Cancel” (FR-049).
3. Immediately before deleting each file, re-check size and hash against the register (protects against changes between check and deletion). Then `os.unlink`.
4. Update the register in one transaction. If a deletion fails, the remaining files stay, the register reflects what actually exists, and the error is reported (FR-058).
5. The destination folder is never deleted (FR-039). No sound (FR-057).

### 5.4 Toggle on with the safe copy procedure (FR-036, FR-044–FR-047, FR-055)

1. **Create the destination folder** if needed with `os.mkdir` (never `makedirs`), then re-check that it resolves inside the source folder (NFR-002).
2. **Write a journal entry** in the SQLite database (state `started`) listing, per file, the temporary name, the final name and the expected size and hash. It is committed before any file is created, so temporary files are always identifiable as the application's own (FR-046).
3. For each file of the set (image first, then sidecars):
   1. Open the source for reading and create the temporary file in the destination folder with exclusive creation (`O_CREAT | O_EXCL`). Temporary names use a reserved prefix: `.vuechoixgarde-<operation-id>-<n>.tmp` (hidden on Linux/macOS; also excluded by the scanner on Windows because of the reserved prefix).
   2. Stream-copy in chunks while computing the SHA-256 of the source data; `flush` and `os.fsync` the temporary file.
   3. Re-read the temporary file and compute its SHA-256; compare with the source hash and size (FR-045, FR-046). Files are never decoded or re-encoded.
   4. Set the modification time from the source with `os.utime(..., ns=...)` (FR-055).
   5. Re-check case-insensitively that no file with the final name exists (FR-047), then **finalize without overwriting** (Section 8.7).
4. **Commit:** insert the register entries (source folder, source name, destination folder, destination name, size, hash, finalize time) and mark the journal entry `done` in one transaction.
5. **Failure in any step:** delete the temporary file, delete all files of this operation that were already finalized (they are known to be byte-identical own copies), mark the journal entry `rolled_back`, report the error (FR-046, FR-058).
6. **Crash recovery** on the next start or folder open: for every journal entry not in a final state, delete its temporary files if present and delete finalized files only if their size and hash match the journal; then close the entry. Files not listed in the journal are never touched.
7. On success: feedback with slot color, key and name, plus sound if enabled (FR-056, FR-057).

### 5.5 Destination-folder rename and deletion (FR-100–FR-104)

**Rename.** The profile slot editor retains each saved destination name as its origin value. A rename is emitted only for an existing profile row whose non-empty name changed; new/removed rows, emptying a name, template edits and profile reassignment do not rename folders. The UI copies all settings and rename intent into an immutable submission before dispatching the file worker (Section 4.3).

Before any write, the application validates all names and resolves every old folder without following links. It rejects faulty old folders, occupied targets (including comparison-key/case/Unicode collisions), duplicate targets and same-save name swaps. Missing old folders are allowed: only the profile name changes and stale register rows are removed. When the old and new names differ only by comparison key, the operation uses a journaled `.vcg-rename-<uuid>` intermediate name and two no-replace renames.

The SQLite `folder_renames` journal is committed before filesystem mutation and stores exact old/new path keys, the optional intermediate path, target profile slots and state. Successful completion moves register paths, replaces slots and closes journal rows in one transaction. An ordinary failure reverses completed operations and marks the journal rolled back; a failed rollback leaves the journal open and blocks folder management. On folder open, recovery runs before copy-journal recovery and reconciliation: untouched old folders close as rolled back; completed renames apply the target slots/register paths; intermediate names are returned to the old name; ambiguous states remain pending; missing folders have stale register rows removed while the target slot configuration is retained.

**Delete or detach.** Inspection classifies every direct child without following links, includes hidden entries, and verifies candidate managed files against the register by size and SHA-256. All unregistered, changed, linked, directory or other entries are foreign. An immutable check token hashes the sorted `(name, kind, size, sha256)` evidence. Execution reinspects immediately before acting; a changed case/token returns `CHECK_CHANGED` and nothing is deleted. A deletable folder loses only verified files and is removed only with `rmdir`; partial failure removes register rows only for copies already deleted and retains the slot. Foreign/faulty folders are never physically changed: confirmation can detach the slot and clear its register records. A missing folder clears metadata only. Destructive confirmation is shown in the UI thread and defaults to Cancel; the worker never reads widgets.

### 5.6 Reconciliation (FR-070, FR-071)

For every register entry of the current profile: `stat` the destination file; missing → remove entry; size differs → `modified`; otherwise hash the file and compare. To keep opening fast with many entries, the register additionally stores the copy's `mtime_ns` at finalization; if size and `mtime_ns` are unchanged, the hash check may be skipped during automatic reconciliation. The manual “Reconcile” command always hashes. FR-050 always hashes the files involved before a toggle, so the shortcut never influences a delete decision.

FR-071 (adopting existing identical files, COULD) is not planned for V1; the register design allows adding it later.

## 6. Application data

### 6.1 Location

Resolved with `platformdirs.user_data_dir("VueChoixGarde", appauthor=False, roaming=False)`:

| Platform | Directory |
|---|---|
| Linux | `$XDG_DATA_HOME/VueChoixGarde` (default `~/.local/share/VueChoixGarde`) |
| Windows | `%LOCALAPPDATA%\VueChoixGarde` (local, not roaming: the register holds machine-specific absolute paths) |
| macOS | `~/Library/Application Support/VueChoixGarde` |

Content:

```
settings.json           # global settings and global slot template
state.sqlite3           # profiles, slots, copy register, operation journal
locks/                  # one lock file per open source folder
logs/                   # vuechoixgarde.jsonl + rotated files
```

Nothing is ever stored in source or destination folders except the managed copies, their temporary files and the destination folders themselves (FR-061, NFR-001).

### 6.2 `settings.json`

Small, human-readable, written atomically (temporary file in the same directory, `fsync`, `os.replace` — overwriting is fine inside the application data). Contents:

| Field | Purpose |
|---|---|
| `schema_version` | Integer, for migrations |
| `language` | `de`, `en` or `fr` (FR-085) |
| `sound_enabled` | FR-057 |
| `sort_direction` | `asc` / `desc` (FR-009) |
| `reopen_last_folder`, `last_folder` | FR-010 |
| `global_slot_template` | List of slots `{key_position, destination_name, color}` (FR-031, FR-042) |
| `learned_key_labels` | Map key position → last observed character (Section 8.1) |

### 6.3 `state.sqlite3`

SQLite (standard library, WAL mode, `PRAGMA user_version` as schema version 2, with a v1→v2 migration). Chosen over plain JSON because the copy register can grow to tens of thousands of entries and because journals and register updates must be transactional.

| Table | Content |
|---|---|
| `profiles` | id, folder identity (Section 8.4), display path, created/updated timestamps |
| `slots` | profile id, order, key position, destination name, color |
| `copies` | copy register: profile id, source folder, source name, destination folder, destination name, size, SHA-256, `mtime_ns` at finalization, created timestamp |
| `operations` | toggle-on journal header: id, profile id, destination name, state (`started`, `done`, `rolled_back`, `recovered`), timestamps |
| `operation_files` | ordered child rows for each copy journal: temporary name, final name, expected size and SHA-256 |
| `folder_renames` | folder-rename journal: exact old/new/intermediate folder path keys, target slot JSON, state (`started`, `done`, `rolled_back`, `recovered`) and timestamps |

`copies.destination_folder` and all rename-journal folder paths use the same `destination_folder_key(source_root, exact_name)` representation. Reassigning a profile to a moved folder (FR-042) updates the profile's folder identity and rewrites the source/destination folder paths of its register entries; reconciliation then checks them.

### 6.4 First start and damaged data (FR-062, FR-063)

- **Missing:** created with defaults without asking.
- **Unreadable** (`settings.json` cannot be parsed or validated, or SQLite fails to open or `PRAGMA integrity_check` fails): nothing is overwritten. The user is told what is damaged and offered to continue with defaults. On confirmation the damaged file is renamed to `<name>.damaged-<timestamp>` and a new one is created. With a new, empty register, all existing files in destinations are `foreign`, so no toggle off is possible for them (FR-063). If the user declines, the application stays usable for viewing but slot actions are disabled.

## 7. Image display (FR-020–FR-023, NFR-010, NFR-013)

- Decoding with Pillow in a worker thread: `Image.open`, frame 0 (first frame/page, FR-022), `ImageOps.exif_transpose` (FR-021), conversion to RGB/RGBA.
- For JPEG, `Image.draft()` lets the decoder produce a reduced size close to the display size, which keeps 20 MB JPEGs well below the 500 ms target (NFR-010).
- Downscale to the display area with a high-quality filter; never upscale beyond 100 % (FR-020). The buffer is wrapped into a `QImage` in the UI thread.
- Preload cache: current image ± 2 neighbors in the current direction, limited by count and total bytes; everything else is released (NFR-013). On resize, the visible image is re-rendered from the cached decoded image.
- Errors: missing file, decode failure or unsupported HEIC decoding produce a typed error that the UI shows in place of the image (FR-023, FR-090). The image stays in the list and slot actions remain available.
- Indicators (star, slot states, feedback) are drawn as separate widgets outside the central image area and are never written into files (FR-072, NFR-004).

## 8. Platform details

### 8.1 Keyboard: physical positions and labels (FR-031, FR-080–FR-084)

**Recognition (by physical position):**

- Slot keys are stored as platform-neutral position names following the W3C UI Events `code` values, e.g. `KeyW`, `KeyA`, `Digit1`, `Minus`, `BracketLeft`, `Semicolon`, `IntlBackslash`. The allowed set is the main character block (FR-082); defaults are `KeyW`, `KeyA`, `KeyS`, `KeyD` (FR-031).
- A Qt event filter on the main window maps each `QKeyEvent` to a position with one static table per platform:

  | Platform | Source value | Example for `KeyW` |
  |---|---|---|
  | Windows | `nativeScanCode()` (PC/AT set 1) | `0x11` |
  | Linux (X11 and Wayland) | `nativeScanCode()` (XKB keycode = evdev code + 8) | `25` |
  | macOS | `nativeVirtualKey()` (hardware key code `kVK_*`) | `0x0D` |

  The tables only cover the allowed keys; anything else is never a slot key. The exact values Qt delivers per platform are verified in the keyboard prototype (Section 14).
- A slot is triggered only if no modifier is active: Shift, Ctrl, Alt, Meta/Cmd/Win, and AltGr (Windows reports it as Ctrl+Alt, Linux as `GroupSwitchModifier`/Level-3) (FR-082).
- `isAutoRepeat()` events are ignored for slot keys (FR-051) and accepted for arrow keys (FR-026).
- The filter is inactive while a dialog is open or a text input has focus (FR-084). Fixed keys (`←`, `→`, `F1`, `F5`, `Esc`) use Qt key codes, since they are layout-independent (FR-083).

**Displayed label (accepted simplification):**

V1 does not query the operating system's keyboard layout. Instead the label of a position is *learned*:

1. Initially, every position shows its US-QWERTY character (defaults: `W A S D`).
2. Whenever a key at an allowed position is pressed without modifiers and Qt reports a printable `text()`, that character (upper-cased) is stored in `learned_key_labels` and from then on displayed for that position. On AZERTY, pressing the first default slot key once changes its label from `W` to `Z`.
3. In the settings dialog, a slot key is assigned by pressing it (“press the new key”); this records the position and its label at the same time.
4. Dead keys or positions without a printable character keep the last known label.

Consequence: before a key has been pressed once on a non-US layout, its label can be wrong, while the *action* is already correct, because recognition is position-based. The user can always reassign keys in the settings. This is the behavior specified in FR-081 (SRS v0.6); the help view explains it (FR-086). An exact label from the first start can be added later without changing stored data, by implementing a `KeyLabelProvider` per platform (Windows `ToUnicodeEx`, Linux `xkbcommon`, macOS `UCKeyTranslate`).

### 8.2 Name comparison and Unicode (FR-033, FR-036, FR-047, NFR-041)

- Comparison key for file and folder names: `NFC(casefold(NFC(name)))`. The same function is used on all platforms, regardless of whether the file system is case-sensitive.
- Names on disk are never changed; operations always use the exact name returned by the directory listing (macOS may return decomposed forms).
- Natural sort (FR-008): the name is split into digit and non-digit runs; key = tuple of `(0, int)` for digits and `(1, comparison key)` for text, with the exact name as final tie-breaker. Implemented in `core`, no extra library.

### 8.3 Scanning the source folder (FR-003–FR-005, NFR-002, NFR-011)

- `os.scandir` on the top level only; one pass collects images, sidecar candidates and subfolders.
- Hidden: name starting with `.`; on Windows `FILE_ATTRIBUTE_HIDDEN` from `stat().st_file_attributes`; on macOS the `UF_HIDDEN` flag from `stat().st_flags`.
- Symbolic links and Windows junctions: detected with `is_symlink()` / `Path.is_junction()`. A link is kept only if it points to a regular file and its resolved path (`Path.resolve(strict=True)`) lies inside the resolved source folder; otherwise it is ignored.
- Windows shortcuts (`.lnk`) are not on the format list and are therefore ignored automatically. macOS Finder aliases that carry an image extension cannot be distinguished cheaply; they fail to decode and are shown as unreadable images (known limitation).
- The extension check uses the fixed list from FR-004 and never the file content.
- Temporary files with the reserved prefix are always excluded.

### 8.4 Folder identity (FR-040)

The identity of a source folder is its resolved absolute path (`Path.resolve(strict=True)`), with each path component replaced by the exact name found in its parent directory listing, and normalized to NFC. This gives the same identity regardless of how the user typed or selected the path, without merging two different folders on case-sensitive file systems.

### 8.5 Single instance per folder (NFR-043)

A lock file `locks/<sha256-of-folder-identity>.lock` in the application data is held with `filelock` (OS-level lock via `fcntl`/`msvcrt`) as long as the folder is open. The OS releases the lock automatically if the process crashes, so there are no stale locks. Nothing is written into the source folder.

### 8.6 HEIC/HEIF (FR-004)

- `pi-heif` is the decoder-only variant of `pillow-heif`. It bundles `libheif` with the `libde265` decoder but no encoders. Its plugin is registered at start (`register_heif_opener()`).
- Binary wheels exist for the release targets (Windows x64, macOS x86_64 and arm64, Linux x86_64 and aarch64); availability is checked for each release.
- If the import fails on a platform, `.heic`/`.heif` files remain in the image list and show the message “This format cannot be displayed on this platform” (FR-004, FR-023). Copying works regardless, since copies are byte-level.
- EXIF orientation: HEIF stores rotation/mirroring as container transforms, which libheif applies while decoding. A bundled test image checks that HEIC files are not rotated twice.
- Why not `pillow-heif`: its binary wheels additionally bundle the GPL-licensed `x265` encoder, which is not needed for viewing.

### 8.7 Finalizing without overwriting (FR-046, FR-047)

The final name must never replace an existing file. Per platform:

| Platform | Primary method | Fallback |
|---|---|---|
| Windows | `os.rename(tmp, final)` — on Windows it fails if `final` exists | none needed |
| Linux | `os.link(tmp, final)` (fails with `FileExistsError`), then `os.unlink(tmp)` | `renameat2(..., RENAME_NOREPLACE)` via `ctypes` for file systems without hard links (e.g. exFAT, some network shares) |
| macOS | `os.link(tmp, final)`, then `os.unlink(tmp)` | `renamex_np(..., RENAME_EXCL)` via `ctypes` |

If neither method is supported, the operation fails with a clear error. There is never a fallback to an overwriting rename.

On case-sensitive file systems the OS does not detect `IMG_1.JPG` vs. `img_1.jpg`, so the case-insensitive check (Section 5.4, step 3.5) is done immediately before finalizing. A remaining race with *other* programs writing the same name in that instant is accepted and documented.

### 8.8 Folder name rules (FR-034)

Implemented once in `core` and applied identically on all platforms: not empty, not only spaces/dots, not `.`/`..`, no path separators, not absolute, none of `< > : " / \ | ? *` or control characters (U+0000–U+001F), no trailing space or dot, not a Windows reserved device name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`, including the superscript-digit variants), also when followed by an extension (`CON.txt`).

### 8.9 Long paths on Windows

Paths longer than 260 characters work only if the system setting “LongPathsEnabled” is active or `\\?\` prefixes are used. `fsops` uses extended-length paths internally on Windows; this is covered by an integration test.

### 8.10 Destination-folder filesystem operations

Folder renames use direct-child validation with `lstat`, containment checks and no-follow link/junction rejection. The operation never merges directories or replaces a target: Windows uses `Path.rename` semantics that fail when the target exists; Linux uses `renameat2(RENAME_NOREPLACE)` and macOS uses `renamex_np(RENAME_EXCL)`. POSIX filesystems without a supported no-replace primitive fail closed. A case-only rename uses a journaled unique intermediate child and rechecks directory names after the move. Deletion uses only `rmdir` after verified managed files have been unlinked; recursive removal is never used.

## 9. User interface

### 9.1 Main window

| Area | Content | Requirements |
|---|---|---|
| Top bar | Active profile (folder name, full path as tooltip), open folder, sort direction toggle, refresh, reconcile, settings, help | FR-001, FR-007, FR-009, FR-040, FR-070, FR-086 |
| Center | Image view (scaled, no upscaling); error or empty state in place of the image; subtle boundary cue at list ends | FR-006, FR-020, FR-023, FR-025 |
| Info line | Filename (elided, full name as tooltip), star if selected anywhere, “12 of 80”, progress bar, selection count | FR-027, FR-028, FR-029, FR-072 |
| Slot bar | Up to 12 slot tiles in one or two rows, each with key label, destination name, color stripe and a state symbol plus text (none / ready / selected / modified / conflict / faulty) | FR-073, FR-087, NFR-021 |
| Feedback | Short notification in the slot bar area with slot color, key and name, “added”/“removed” | FR-056 |

- Styling with a Qt style sheet: background `#2B2B2B`, panels `#383838`, light grey text, one accent color, system sans-serif font, slightly rounded corners (FR-088). All text/background pairs are checked for ≥ 4.5:1 contrast (NFR-022); focus is shown with a visible outline (NFR-023).
- Slot colors come from a predefined palette of 12 distinguishable colors; a custom color can be picked with `QColorDialog`.

### 9.2 Dialogs

- **Settings** (FR-064): tabs *General* (language, sound, sort direction, reopen last folder, open log folder), *Slots* (add/remove 1–12 slots, assign key by pressing it, name, color; duplicate keys and names are flagged inline and block saving, FR-032/033; saved profile destinations can be renamed or inspected for deletion), *Profiles* (save as template, reset template, reset profile, assign an orphaned profile, FR-042).
- **Destination deletion:** inspect and confirm in the UI thread; default and Escape are Cancel. The informative text lists foreign entries. Workers receive the immutable check token and return `CHECK_CHANGED` when the inspected state is stale.
- **Name prompt** (FR-035) with live validation (FR-034).
- **Confirmation for modified copies** (FR-049): lists the files; default button “Cancel”.
- **Errors** (FR-090): `QMessageBox` with a plain-language text naming the file/folder and a hint; technical details in the expandable details section.
- **Help** (FR-086, `F1`): fixed keys, current slot keys with names and colors, short explanation of toggle behavior and that source files are never changed.

### 9.3 Translations (FR-085)

UI strings live in simple JSON catalogs (`i18n/de.json`, `en.json`, `fr.json`) with message keys and named placeholders. A small lookup function is used instead of Qt Linguist: catalogs are easy to edit, testable without Qt (a test checks that all three catalogs have the same keys and placeholders). Qt's own standard dialog strings are translated by loading the `qtbase_<lang>.qm` files shipped with PySide6. On first start the OS language (`QLocale.system()`) is used if it is German, English or French, otherwise English.

### 9.4 Sound (FR-057)

`QSoundEffect` with a short, quiet bundled WAV file, played only after a successful toggle on and only if enabled. If audio output is unavailable, the failure is logged and otherwise ignored.

## 10. Logging (FR-091, FR-092)

- Standard `logging` with a `RotatingFileHandler` at `logs/vuechoixgarde.jsonl`, 10 MB per file, 4 backups (≤ 5 files).
- Own formatter: one JSON object per line with `ts` (ISO 8601 with time zone), `level`, `event` (e.g. `app.start`, `folder.open`, `copy.done`, `copy.failed`, `conflict`, `delete.done`, `reconcile.result`, `error`), `msg` and optional structured fields (paths, counts, durations).
- The image decoder and EXIF data are never passed to the logger; a unit test asserts that log records only contain allowed fields (no image content, no metadata such as GPS).
- “Open log folder” uses `QDesktopServices.openUrl` with a local file URL.

## 11. Development tooling

### 11.1 uv

- `uv sync` creates the virtual environment from `pyproject.toml` and `uv.lock`.
- Runtime dependencies in `[project.dependencies]`; development tools (pytest, pytest-qt, ruff, pyright, pyinstaller) in `[dependency-groups] dev`.
- All commands run through uv: `uv run vuechoixgarde`, `uv run pytest`, `uv run ruff check`, `uv run ruff format`, `uv run pyright`.
- `uv.lock` is committed; CI uses `uv sync --locked` so builds are reproducible.
- The Python version is pinned in `.python-version` and installed by uv if missing.

### 11.2 ruff

- `ruff format` is the only formatter; `ruff check` the only linter. Both run in CI and must pass.
- Planned rule sets: pycodestyle (`E`, `W`), Pyflakes (`F`), isort (`I`), pyupgrade (`UP`), bugbear (`B`), simplify (`SIM`), pathlib usage (`PTH`), naming (`N`), ruff-specific (`RUF`) and banned imports (`TID`).
- Banned-import rules (`TID251`) enforce two architecture rules:
  - no network modules anywhere (`socket`, `urllib`, `http`, `ssl`, `PySide6.QtNetwork`, …) (NFR-005),
  - no `PySide6` imports in `core`, `ports`, `app`, `fsops`, `store`, `imaging`, `applog` (NFR-030, via per-file configuration).
- Target version `py312`, line length 100.
- Static type checking is done with pyright (Section 11.4).

### 11.3 Tests (SRS Section 8)

| Level | Tooling | Scope |
|---|---|---|
| Unit | pytest | format filter, sidecar matching (shared stems, case variants), natural sort both directions, navigation and boundaries, name and slot validation, key conflicts, allowed keys and modifiers, profile/template handling, toggle decision table, comparison keys, i18n catalog consistency, log formatter |
| Integration | pytest with `tmp_path` | byte-identical copy incl. EXIF camera/date/GPS, safe copy with injected failures in every step (fault-injecting file system adapter), crash recovery from journal, toggle off, shared sidecars, conflicts with case variants, symlinks/junctions pointing outside, externally deleted/modified copies, reconciliation without changes, damaged/missing application data, lock between two instances, long paths on Windows; every test asserts at the end that the source folder is unchanged (content hashes) |
| UI | pytest-qt (offscreen platform) | keyboard routing (slot keys vs. dialogs/text fields), auto-repeat handling, slot bar states, settings validation |
| Manual per platform | checklist in `docs/` | keyboard layouts QWERTY/QWERTZ/AZERTY, key repeat, all formats incl. HEIC, EXIF orientation, sound, languages, help, appearance |

Test images are generated with Pillow at test time (including EXIF with GPS and orientation tags) or bundled under `tests/data` with a documented license; personal images are never used.

### 11.4 pyright

- **pyright** in mode `standard` is the static type checker; mypy was considered but is slower and less precise with the PySide6 type stubs.
- Installed as a development dependency from PyPI (`pyright[nodejs]`, so no system-wide Node.js is required). It is a development tool only and is never part of a release build.
- Configuration in `[tool.pyright]` in `pyproject.toml`: `typeCheckingMode = "standard"`, `pythonVersion = "3.12"`, checked paths `src` and `tests`, the virtual environment created by uv.
- `core`, `ports` and `app` are fully annotated; the `Protocol` interfaces in `ports` are what makes the adapters (`fsops`, `store`, `imaging`, `applog`) and the test doubles interchangeable (NFR-030), so type checking protects these boundaries.
- Stricter checks (e.g. mode `strict` for `core`) can be enabled later per directory without changing the code structure.
- `uv run pyright` runs in CI and must pass (Section 12.1).

## 12. Build and release (NFR-044)

### 12.1 CI

GitHub Actions matrix on Linux, Windows and macOS: `uv sync --locked`, `ruff format --check`, `ruff check`, `pyright`, `pytest` (Qt offscreen). Releases are built from tags.

### 12.2 Packaging

PyInstaller in **one-folder** mode (not one-file): faster start, fewer false positives from virus scanners for unsigned builds, and the Qt libraries remain separately replaceable (LGPL, Section 12.4).

| Platform | Artifact | Build runner |
|---|---|---|
| Linux x86_64 | `.tar.gz` with the application folder | Ubuntu 22.04 runner (Qt 6.12 wheels require glibc 2.34+) |
| Windows x64 | `.zip` with the application folder | Windows runner |
| macOS arm64 | `.app` in `.zip` | Apple-silicon macOS 14 runner |

QtMultimedia is retained for optional WAV feedback. QtNetwork is bundled only because QtMultimedia imports it; application code never imports or uses it (enforced by Ruff TID251 and an AST test). Qt's TLS plugins and OpenSSL libraries are not shipped. The Linux Multimedia FFmpeg plugin also links to native QtQml/QtQuick libraries and Qt FFmpeg SSL/crypto stubs; a probe without them had no Multimedia backend. These transitive native dependencies remain pending product-owner approval. QtQml/QtQuick Python bindings, QtWebEngine, QtPdf, QtSvg, QtOpenGL and QtSql remain excluded. Release builds scan the bundle: unexplained network modules, TLS components and x265 fail the build.

### 12.3 Unsigned builds

Releases are unsigned and macOS builds are not notarized (SRS 3.2). User documentation explains Windows SmartScreen, macOS Gatekeeper approval in Privacy & Security, and Linux executable permissions. Release publication is a maintainer-reviewed GitHub draft; signing and publication remain manual.

### 12.4 Licenses

- PySide6/Qt and shiboken6: the selected LGPL-3.0-only terms are retained, with replaceable shared libraries in a one-folder distribution. Distribution metadata is copied into the bundle; consult the official [Qt licensing page](https://www.qt.io/licensing/open-source-lgpl-obligations) for full terms.
- Pillow (MIT-CMU), `pi-heif` (BSD-3-Clause), `filelock` and `platformdirs`: release notices are generated from locked distribution metadata; bundled native `libheif`/`libde265` license texts are carried by the `pi-heif` distribution metadata where present.
- The project license is MIT; dependency licenses remain unchanged. The release includes `LICENSE` and `THIRD_PARTY_NOTICES.md`.
- HEVC patent rights may apply in some jurisdictions; this is listed as a risk (Section 14), not as legal advice.

### 12.5 Minimum OS versions (NFR-040)

The current packaging baseline is constrained by the PySide6/Qt 6.12 binary wheels: Windows 10 version 1809 or Windows 11 (x86_64), macOS 14.4 or later (Apple silicon arm64), and Linux x86_64 with glibc 2.34 or later. Qt platform/plugin dependencies and graphics/audio drivers must also be present. See the official [Qt 6.12 supported platforms](https://doc.qt.io/qt-6/supported-platforms.html) and [Linux glibc requirements](https://doc.qt.io/qt-6/linux.html). Verify these constraints against every release wheel and smoke test; they are not claims of manual OS acceptance.

## 13. Deviations from and interpretations of the SRS

| Item | Decision | Status |
|---|---|---|
| FR-081 / acceptance criterion 14: label shows the character of the active layout | Recognition is position-based from the start; the label is learned on first key press and initially shows the US-QWERTY character (Section 8.1) | Accepted by the product owner; SRS FR-081 and acceptance criterion 14 adjusted in v0.6. Exact labels from the first start (native label providers) remain a possible later enhancement |
| FR-071 adopting existing identical files (COULD) | Not in V1 | Deferred |
| FR-004 HEIC/HEIF | Supported on all release platforms via `pi-heif`; unsupported platforms show the required error | Goes beyond the SRS minimum |
| FR-046 temporary files “identified by the copy register” | Identification via the operation journal, which is part of the application data next to the register | Interpretation |

## 14. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Native key codes delivered by Qt differ from expectations (especially macOS, Wayland, ISO keyboards) | Slot keys not recognized | Small keyboard prototype first; scan code tables tested on all three platforms with QWERTY/QWERTZ/AZERTY |
| Labels wrong until first key press | Users confused on non-US layouts | Help view explains it; assignment by key press in settings; optional native label providers later |
| `pi-heif` wheel missing for a platform/Python version | No HEIC display there | Required behavior (error message) is already defined; check wheel availability before each release |
| HEVC patent situation | Legal uncertainty for distribution | Assess before the first public release; HEIC support can be dropped from builds without code changes |
| File systems without hard links and without no-replace rename | Copy not possible | Clear error; document supported file systems |
| Race with other programs between check and finalization | A foreign file could be created in the same instant | Finalization itself never overwrites; remaining race documented |
| Large package and unsigned builds | Download size, warnings | One-folder build, excluded Qt modules, documentation (Section 12.3) |
| Performance with 10,000 images and large JPEGs | Slow opening or navigation | Single-pass scan, `draft()` decoding, preload cache, background reconciliation with `mtime_ns` shortcut; measured against NFR-010/011 |

## 15. Resolved release decisions

- The repository and application are MIT-licensed; dependency notices and terms are retained.
- Release builds target macOS arm64 only. macOS Intel is not part of the V1 release matrix.
