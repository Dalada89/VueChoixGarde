# Handoff – VueChoixGarde

Status: Phase 2 (keyboard prototype) implemented and automatically verified; manual cross-platform validation remains pending.
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
| `.deutschlandgpt/plans/pre-development-readiness.md` | Readiness-Prüfung vor Entwicklungsbeginn | committet |
| `.deutschlandgpt/anweisungen.md` | Projektanweisung: Handoff aktuell halten | nicht committet |
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
- [ ] `navigate` does not signal “boundary reached” (FR-025 requires a visual cue); add this in `app` at the latest.
- [ ] `validate_slot_profile` does not identify colliding slots and does not validate destination names against FR-034; address before the settings dialog.
- [x] Key-label learning logic (Technical Design 8.1, steps 2 and 4) was added in Phase 2.
- Modules directly in the package root (`__main__.py`, later `bootstrap.py`) have no PySide6 import restriction; this is intentional because bootstrap may use Qt.

## 7. Empfohlene nächsten Schritte

1. ~~Offene Punkte 1 und 2~~ (erledigt).
2. ~~Projektgerüst + `core`~~ (Phase 1, erledigt).
3. ~~Phase 2 – Keyboard prototype~~ (implemented and automatically verified; pending manual platform tests are listed in Section 9).
4. Phase 3 – Dateisystem und Speicherung: Ordner-Scan, sicheres Kopieren (FR-046), SQLite-Register, Symlink-Erkennung (NFR-002), Einzelinstanz je Ordner (NFR-043) – mit Tests.
5. Danach UI auf Basis von PySide6.

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
- Remaining Phase 1 items are unchanged: provide an FR-025 boundary-reached signal/cue in `app`; improve `validate_slot_profile` collision details and destination-name validation against FR-034 before the settings dialog.
- After manual review approval, proceed with Phase 3 file-system and persistence work described above.
