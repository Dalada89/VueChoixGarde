# Handoff – VueChoixGarde

Status: Phase 4 (`app` use cases and orchestration, `applog`, and FR-070 metadata reconciliation) implemented and verified; 284 tests passed and one Windows-only test was skipped on Linux. Phase 2 manual cross-platform keyboard validation remains pending. No commit was created.
Zweck: Fortsetzung der Arbeit auf einem anderen Rechner bzw. in einer neuen Sitzung.

## 1. Ziel des Projekts

VueChoixGarde soll gemäß `docs/requirements.md` (SRS v0.6) als **lokal laufende Desktop-App** umgesetzt werden.

## 2. Arbeitsweise / Präferenzen

- Kommunikation auf Deutsch; Projektdokumente (Requirements, Design, ADR) auf Englisch.
- Technische Vorschläge konkret, mit Vor-/Nachteilen und mindestens zwei Varianten.
- Anwendung bleibt vollständig lokal (keine Cloud-Abhängigkeit).
- Technische Konzepte werden in `docs/` dokumentiert.
- Erst Dokumentation, dann Entwicklung. Die Entwicklung läuft in kleinen Phasen; die Umsetzung übernimmt teils ein kostengünstigeres Modell anhand eines Phasen-Prompts, danach folgt ein Review.
- Projektanweisung beachten: keine geheimen Dateien (`.env`, Schlüssel, Tokens, Backups usw.) lesen oder verarbeiten.

## 3. Bisherige Ergebnisse

| Datei | Inhalt | Status |
|---|---|---|
| `docs/requirements.md` | SRS v0.6 (FR-081/Abnahmekriterium 14 angepasst) | committet (`3059d81`) |
| Projektgerüst + Paket `core` + Unit-Tests (Phase 1) | `pyproject.toml`, `uv.lock`, `src/vuechoixgarde/…`, `tests/unit/…` | committet (`b74c738`) |
| Tastatur-Prototyp (Phase 2) | `core/native_keys.py`, `core/keys.py`, `ui/keyboard.py`, `ui/keyboard_probe.py`, `docs/keyboard-test-checklist.md`, Tests | committet (`2b7d022`) |
| `.deutschlandgpt/plans/pre-development-readiness.md` | Readiness-Prüfung vor Entwicklungsbeginn | committet |
| `.deutschlandgpt/anweisungen.md` | Projektanweisung: Handoff aktuell halten | committet (`568ed2f`) |
| `docs/technical-design.md` | Technisches Umsetzungskonzept (Abschnitte 1–15) | committet (`423c161`) |
| `docs/adr/0001-technology-choice.md` | ADR zur Technologiewahl | committet (`423c161`) |
| `.deutschlandgpt/plans/technische-umsetzung-dokumentieren.md` | Plan aus der Planungsphase | nicht committet |
| `.deutschlandgpt/README.md` | – | nicht committet |

## 4. Getroffene Entscheidungen

**Variante A: Python-Desktop-App** (verglichen mit B Electron + Vue, C Tauri, D reine Browser-App).

- Python 3.13 (Minimum 3.12), **PySide6 / Qt Widgets** als UI.
- Bildverarbeitung: **Pillow**; HEIC/HEIF-Dekodierung über **`pi-heif`**
  (nicht `pillow-heif`, da dessen Wheels GPL-lizenzierten x265 enthalten).
- Paketmanager **`uv`** (`pyproject.toml`, `uv.lock`), Linter/Formatter **Ruff**.
- Tests: **pytest**, **pytest-qt**.
- Packaging: **PyInstaller** (One-Folder-Build), CI/Releases über **GitHub Actions / GitHub Releases**.
- Persistenz: **SQLite** für Profile, Kopierregister und Recovery-Protokoll; `settings.json` für Einstellungen.
- Kopieren (FR-046): temporäre Datei → Prüfsummenvergleich → atomare Finalisierung ohne Überschreiben (OS-spezifisch).
- Priorität: HEIC-Kompatibilität ist wichtiger als von Anfang an korrekte Tastenbeschriftung.

### Tastaturkonzept (seit SRS v0.6 konform zu FR-081)

- Tasten werden von Anfang an über ihre **physische Position** erkannt (plattformspezifische Scancode-Tabellen) – die Aktion ist immer korrekt.
- Die **Beschriftung** zeigt zunächst das US-QWERTY-Zeichen und wird beim ersten Tastendruck durch das tatsächlich erzeugte Zeichen ersetzt.
- Neubelegung jederzeit in den Einstellungen per Tastendruck möglich.
- Folge: Auf Nicht-US-Layouts kann die Beschriftung bis zum ersten Drücken falsch sein. FR-081 und Abnahmekriterium 14 wurden in SRS v0.6 entsprechend angepasst; Hilfe und Doku müssen die Einschränkung erklären.
- Typprüfer: **pyright** im Modus „standard“ (technical-design 11.4).

## 5. Bekannte Risiken (Auswahl, Details in `docs/technical-design.md` Abschnitt 14)

- Scancode-Tabellen je Plattform → vor dem UI-Bau per Tastatur-Prototyp validieren.
- HEVC-Patentlage vor einer Veröffentlichung prüfen.
- Race Condition mit Fremdprogrammen zwischen Prüfung und Finalisierung (Finalisierung überschreibt nie; Restrisiko dokumentiert).
- Paketgröße / unsignierte Builds.
- Performance bei 10.000 Bildern und großen JPEGs (NFR-010/011).

## 6. Offene Punkte

Erledigt:

1. ~~SRS anpassen (FR-081, Abnahmekriterium 14)~~ → SRS v0.6.
2. ~~Typprüfer festlegen~~ → pyright, Modus „standard“.

Kann später entschieden werden:

3. **Projektlizenz:** muss mit LGPL-Komponenten (PySide6) vereinbar sein; MIT oder Apache-2.0 sind bei dynamischem Linken/One-Folder-Build möglich. Falls das GitHub-Repo öffentlich ist, früh festlegen.
4. **macOS-Intel-Build** ja/nein – relevant erst für Packaging/CI.
5. `.deutschlandgpt/` wird committet (bis auf die neue `anweisungen.md`).

### Review Phase 1 (Ergebnis)

Phase 1 checks passed: `ruff format --check`, `ruff check`, `pyright` (0 errors), `pytest` (136 tests). Ruff architecture rules are active (verified with `--show-settings` for `core`: PySide6 and network modules are blocked). No blocking findings. Review follow-ups:

- [x] Missing tests: refresh with no following image (fallback to the last image), refresh to an empty list, navigation on an empty list, and `register_available=False` with `modified` (completed in Phase 2).
- [x] `FolderSession.navigate` now exposes `boundary_reached` in its immutable read model for the FR-025 visual cue.
- [x] `validate_slot_profile` now identifies all colliding slot indexes and reports per-slot FR-034 `FolderNameError` values (Phase 3).
- [x] Key-label learning logic (Technical Design 8.1, steps 2 and 4) was added in Phase 2.
- Modules directly in the package root (`__main__.py`, later `bootstrap.py`) have no PySide6 import restriction; this is intentional because bootstrap may use Qt.

## 7. Empfohlene nächsten Schritte

1. ~~Offene Punkte 1 und 2~~ (erledigt).
2. ~~Projektgerüst + `core`~~ (Phase 1, erledigt).
3. ~~Phase 2 – Keyboard prototype~~ (implemented and automatically verified; pending manual platform tests are listed in Section 9).
4. ~~Phase 3 – `ports`, `fsops`, `store`, core follow-ups, and unit/integration tests~~ (completed; details in Section 10).
5. ~~Phase 4 – `app` use cases and orchestration, crash recovery, FR-070 reconciliation, fault-injection tests, and `applog`~~ (implemented and verified; details in Section 11).
6. Next: Phase 5 – image display (`imaging`), bootstrap, and the PySide6 main UI; preserve the documented exclusions and pending cross-platform keyboard validation.

## 8. Einstieg in der neuen Sitzung

Vorschlag für die erste Nachricht:

> Lies `.deutschlandgpt/handoff.md`, `docs/technical-design.md` und `docs/adr/0001-technology-choice.md` und mach mit den offenen Punkten in Abschnitt 6 weiter.

Hinweis: Diese Datei und `.deutschlandgpt/` müssen committet und gepusht werden, damit sie auf dem anderen Rechner verfügbar sind.

## 9. Phase 2 results

Implemented the manual keyboard prototype and the outstanding Phase 1 test review items. No new dependencies were added, and `docs/requirements.md`, `docs/technical-design.md`, and `docs/adr/` were not changed.

### Decisions and implementation

- Added immutable Windows, Linux, and macOS native-code lookup tables for exactly the allowed W3C slot positions. The Linux table uses Chromium's XKB values (evdev + 8); the Windows values are PC/AT Set 1; the macOS values are `kVK_*` hardware codes.
- Source: Chromium `ui/events/keycodes/dom/dom_code_data.inc` (official mirror: `https://github.com/chromium/chromium/blob/main/ui/events/keycodes/dom/dom_code_data.inc`). Its reference notes identify the platform-specific source data. The macOS ISO Backquote/IntlBackslash swap is documented, not normalized.
- Added pure label learning: single printable characters are upper-cased unless upper-casing expands to multiple characters; invalid/dead-key text, modifiers, and disallowed positions retain prior labels. Labels are in-memory only in the probe.
- Added a Qt event-data adapter and an FR-084 guard that disables main-window shortcuts while a dialog is visible or a text editor has focus. Slot auto-repeat and Shift/Ctrl/Alt/Meta/GroupSwitch are blocked; KeypadModifier is not treated as a modifier.
- Added `uv run python -m vuechoixgarde.ui.keyboard_probe` and the English manual checklist at `docs/keyboard-test-checklist.md`.

### Verification

- `uv sync --locked`: passed; no dependency changes.
- `uv run ruff format --check`: passed (43 files formatted).
- `uv run ruff check`: passed.
- `uv run pyright`: passed (0 errors, warnings, or informations).
- `uv run pytest`: passed (182 tests).
- Probe startup: `uv run python -m vuechoixgarde.ui.keyboard_probe` stayed running with no stdout/stderr until stopped; interactive hardware/layout testing remains pending.

### Open validation and next actions

- Manually test actual Qt native event values with the probe on Linux X11 and Wayland, then Windows and macOS, following `docs/keyboard-test-checklist.md`. The automated Qt tests use synthetic Linux native scan code 25; they do not establish physical-device values on other systems.
- On Linux, test QWERTY, QWERTZ, and AZERTY; check the `IntlBackslash` ISO key, AltGr, dead accents, and held-key repeat. Record each result in the checklist.
- Phase 3 addressed the `validate_slot_profile` collision-index and FR-034 destination-name gaps. The remaining Phase 1 follow-up is an FR-025 boundary-reached signal/cue in `app`.
- Phase 3 is complete; its results and the Phase 4 handoff are in Section 10. Manual keyboard validation remains relevant before the main-window UI work.

### Review Phase 2 (Ergebnis)

Checks re-run in review: `uv sync --locked`, `ruff format --check`, `ruff check`, `pyright` (0 errors), `pytest` (182 tests) – all passed. Native tables spot-checked (Linux evdev+8 incl. Backquote 49, Backslash 51, IntlBackslash 94, punctuation 47/48/59/60/61; macOS `kVK_*` digits/punctuation/ISO_Section 0x0A; Windows Set 1 incl. 0x29/0x2B/0x56) – consistent. No blocking findings. Follow-ups:

- [ ] Dead keys: after `´` + `e`, the composed `é` arrives on the `KeyE` event and is learned as the label of `KeyE` (`É`). Self-corrects on the next plain press; accept and mention in help (FR-086), or revisit with the manual test results.
- [ ] FR-084 guard (`main_window_key_filter_enabled`) only checks visible top-level `QDialog`s and text widgets; when building the main window also respect `QApplication.activeModalWidget()` and `activePopupWidget()` (menus, combo popups).
- [x] Added a Windows raw-key test: scan code `0x11` maps to `KeyW` while `native_virtual_key` is ignored (Phase 3).
- AltGr: Qt xcb maps AltGr to `GroupSwitchModifier` (qtbase `qxcbkeyboard.cpp`), Windows reports Ctrl+Alt by default – both are blocked. Wayland still needs the manual check.
- `ui` imports `core` directly in the probe; acceptable. In the main window, label learning and persistence (FR-060) should go through `app` and the settings store.
- `docs/keyboard-test-checklist.md` results are still empty; Phase 3 does not depend on them, the main-window UI phase does.

## 10. Phase 3 results

Phase 3 (ports, filesystem operations, and persistence) is implemented. No new dependencies were added, no commit was created, and `docs/requirements.md`, `docs/technical-design.md`, and `docs/adr/` were not changed.

### Implementation

- Extended `core.slots.validate_slot_profile` to return immutable `ProfileIssue` values with all conflicting slot indexes and the exact `FolderNameError` for each invalid configured destination name.
- Added UUID4-hex reserved temp-name generation/recognition and the pure `default_language(locale_name)` resolver. Added the Windows raw-key regression test (`scan code 0x11` -> `KeyW`, virtual key ignored).
- Added typed `ports` Protocols, immutable transfer values, and translatable `StrEnum`-reason exceptions for filesystem, lock, settings, and state failures.
- Added `fsops` source validation, exact-spelling/NFC folder identity, one-pass top-level scan, hidden/symlink/junction filtering, containment checks, destination resolution/creation/listing, streamed fingerprints, exclusive verified temp-copy, no-overwrite finalize, verified/confirmed deletion, reserved-temp cleanup, Windows extended paths, a `filelock`-based folder lock, and an aware UTC system clock.
- Added `store` app-data path preparation, strict atomic `settings.json`, SQLite WAL/schema version 1 and 0-to-1 migration, profile/slot/copy/journal repositories, and explicit no-overwrite damaged-file quarantine.
- Integration source guards snapshot file names, file SHA-256, symlink targets/content where local to `tmp_path`, and directory names after setup; only approved destination subfolders are excluded from the source snapshot.

### Decisions and verified platform details

- On case-sensitive filesystems, more than one real immediate subfolder with the same `comparison_key` yields `FAULTY(AMBIGUOUS)`. A matching file/link is reported as its own fault; no destination is selected when entries conflict.
- Journal metadata is split into `operations` and child rows in `operation_files(operation_id, index, temp_name, final_name, expected_size, expected_sha256)`. `operations` stores the operation ID, profile/destination, state (`started`, `done`, `rolled_back`, `recovered`), and UTC timestamps. There is no `modified` column in `copies`.
- The hardlink fallback is attempted only for `EPERM`, `EOPNOTSUPP`/`ENOTSUP`, `EMLINK`, and `EXDEV`. Other hardlink errors do not try a different primitive. A fallback that is unavailable/unsupported raises `FINALIZE_UNSUPPORTED`; no POSIX overwrite-capable rename is used. `FileExistsError` is a conflict and deliberately leaves the temp file intact for the caller to clean up.
- Constants were checked against official sources: Linux UAPI `include/uapi/linux/fcntl.h` (`AT_FDCWD=-100`, no-replace flag value `0x0001`, exposed there as `AT_RENAME_NOREPLACE`) and Linux `rename(2)` man-pages (`RENAME_NOREPLACE` semantics); Apple XNU `bsd/sys/stdio.h` defines `RENAME_EXCL=0x00000004`. References: `https://github.com/torvalds/linux/blob/master/include/uapi/linux/fcntl.h`, `https://man7.org/linux/man-pages/man2/rename.2.html`, and `https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/stdio.h`.
- Ruff's nested `ruff.toml` files were confirmed active: `ruff check --show-settings` reports the `PySide6` ban separately for `fsops`, `ports`, and `store`.

### Verification

- `uv sync --locked`: passed; 30 packages resolved, 26 checked; no dependency changes.
- `uv run ruff format --check`: passed (66 files already formatted).
- `uv run ruff check`: passed.
- `uv run pyright`: passed (0 errors, warnings, or informations).
- `uv run pytest`: passed (260 collected; 259 passed, 1 skipped). The skipped test is the Windows-only extended-length-path test, skipped on Linux.
- `ruff check --show-settings` confirmed `PySide6` bans apply in all three adapter packages (`fsops`, `ports`, `store`).

### Open points and next step

- No unresolved Phase 3 design questions remain. Runtime validation of Windows extended paths, Windows/macOS no-replace behavior, macOS hidden flags, and cross-platform keyboard events still requires those platforms; the Windows long-path test was skipped on this Linux run.
- FR-025's `boundary_reached` signal is implemented in the Phase 4 folder-session read model. Phase 2 follow-ups for dead-key label learning and respecting `QApplication.activeModalWidget()`/`activePopupWidget()` remain for help/main-window UI work; manual keyboard checklist results are still pending.
- Next: Phase 5 – imaging, bootstrap, and the PySide6 UI. FR-071 remains deferred; UI/Qt, workers, imaging, i18n, sound, and profile/template administration were outside Phase 4 scope.

## 11. Phase 4 results

Phase 4 (`app` orchestration and `applog`) is implemented and verified. The FR-070 automatic metadata shortcut was unblocked by the approved `FileMetadata`/`FileSystemPort.file_metadata` addition. No new dependencies were added, no commit was created, and `docs/requirements.md`, `docs/technical-design.md`, and `docs/adr/` were not changed.

### Implementation

- Added immutable `FileMetadata(size, mtime_ns)` and a `LocalFileSystem.file_metadata` operation using `lstat`, containment checks, and link/non-regular-file rejection without opening file contents.
- Added synchronous Qt-free `app` use cases: nonblocking operation gate; startup load plus explicit damaged-data accept/decline; folder lock/session lifecycle; navigation boundary signal, sorting, refresh, slot read models, destination naming, and persistent eligible key labels.
- Added fresh toggle preflight and execution with ABSENT/VERIFIED/MODIFIED/FOREIGN classification, full hashes before toggle decisions, no-overwrite finalization, journal-before-copy, atomic register completion, confirmation before deleting modified managed copies, conflict preservation, shared-sidecar retention, and exception-only rollback.
- Added profile-scoped journal recovery before folder-open reconciliation; recovery touches only journal-listed temps/finals and leaves modified or ambiguous files pending. Reconciliation removes stale register rows, skips automatic hashing only for matching size/mtime, always hashes in manual mode, and never changes image files.
- Added clock-injected UTF-8 JSONL logging with bounded rotation, reference-counted close, privacy-safe app events, and failures contained from the application. Added protocol fakes and fault-injection/crash coverage under `tests/fakes/`.

### Verification

- `uv sync --locked`: passed; dependencies unchanged.
- `uv run ruff format --check`: passed (83 files already formatted).
- `uv run ruff check`: passed.
- `uv run pyright`: passed (0 errors, warnings, or informations).
- `uv run pytest`: passed (285 collected; 284 passed, 1 skipped). The skipped case is the Windows-only extended-length-path test on Linux.
- Nested Ruff settings for `app` and `applog` were inspected: TID251 is active and preserves the parent network bans. Temporary forbidden-import probes were rejected for `app -> store` and `applog -> core` as expected, then removed.

### Remaining work

- Runtime validation of Windows/macOS path/finalization behavior and manual cross-platform keyboard events remains platform-dependent.
- Phase 5 starts with imaging/bootstrap/UI; do not fold the excluded Phase 4 UI, worker, imaging, i18n, sound, or profile/template work into the completed app layer.
