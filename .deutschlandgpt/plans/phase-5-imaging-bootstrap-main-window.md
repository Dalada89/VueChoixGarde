# Phase 4 review and Phase 5 prompt

## Context

Phase 4 (`app`, `applog`, FR-070 reconciliation) was reviewed by reading the code (`app/toggle.py`, `session.py`, `reconcile.py`, `startup.py`) against `docs/technical-design.md` Sections 4–6 and the handoff. Plan mode forbids running commands, so the checks (`uv run ruff format --check`, `ruff check`, `pyright`, `pytest`) were NOT re-run; the numbers in the handoff (284 passed, 1 skipped) are taken from it. Re-run them before committing.

## Review result Phase 4

No blocking finding. The toggle design matches Sections 5.2–5.4: fresh reclassification before acting, journal before copy, no-overwrite finalize, rollback, confirmation before deleting modified copies, shared sidecars, `app` Qt-free.

### Findings (fix at the start of Phase 5)

1. **Bug (medium)** `FolderSession.slot_states` (`app/session.py`, `classes` dict): MODIFIED lookup is keyed only by `record.destination_name`. Two slots whose destination folders both hold `IMG_1.jpg` share one key, so a modified copy in slot A marks slot B as MODIFIED too (and the reverse). Key by `(destination_folder, destination_name)`. Add a test with two slots.
2. **Minor** `FolderSession.open`: `session.checking = True` is set after recovery errors, but `reconcile()` resets it to `False` in `finally`, so the "recovery pending" state is lost. Keep a separate `recovery_pending` flag in the snapshot, or drop the assignment.
3. **Minor** `app/reconcile.py::_safe_log` has an unused `event: str` parameter (always logs `LogEvent.RECONCILE`); the call sites pass the string `"reconcile"`. Remove the parameter.
4. **Minor** `FolderSession.set_sort_direction` mutates `navigation` before `settings_store.save`; if `save` raises, memory and file diverge. Save first or roll back.
5. **Design note for Phase 5** `plan_toggle`/`slot_states` list directories and hash files; they MUST run on the file-operation worker, not on the UI thread (NFR-012). `refresh`/`navigate` mutate session state, so the UI layer must serialize access to `FolderSession` (single owner thread or a lock). `plan_toggle` removes stale register rows (a write during planning); acceptable, but it must therefore also run under the gate.
6. **Design note** `CopyRecord.mtime_ns` stores the SOURCE mtime (copy gets it via utime, FR-055). On filesystems with coarser timestamp resolution (FAT/exFAT) the automatic shortcut simply falls back to hashing; correct, only slower. Document it; no change needed.
7. Test gap to consider: no test covers `startup.accept_damaged_data` when only the SQLite store is damaged and settings are fine (`register_available` handling). Check whether `tests/unit/test_app_phase4.py` covers it; add if not.

## Scope recommendation

Phase 5 as one prompt is too large. Split:

- **Phase 5** (below): review fixes, `imaging`, `ImageDecoder` port, `bootstrap`, worker infrastructure, minimal working main window (open folder, view, navigate, slot toggle with name prompt and modified-copy confirmation, feedback, error display).
- **Phase 6** (later): Settings dialog (General/Slots/Profiles), i18n catalogs de/en/fr, Help (F1), sound, final styling/contrast, orphaned-profile assignment, logging UI hooks, packaging/CI.

## Prompt for Phase 5 (copy everything between the lines)

---

Du bist ein Implementierungsagent für das Projekt VueChoixGarde (`/home/robin/Dokumente/projects/image_sorter`). Kommunikation mit mir auf Deutsch, Code/Kommentare/Docs auf Englisch. Setze ausschließlich **Phase 5** um: Review-Korrekturen aus Phase 4, `imaging`, `bootstrap`, Worker-Infrastruktur und ein minimal funktionsfähiges Hauptfenster. Nicht commiten, keine Abhängigkeiten hinzufügen, `docs/requirements.md`, `docs/technical-design.md` und `docs/adr/` nicht ändern. Keine geheimen Dateien (`.env`, Schlüssel, Tokens) lesen.

### Pflichtlektüre vor dem Start

`.deutschlandgpt/handoff.md` (insb. Abschnitte 9–11), `docs/technical-design.md` Abschnitte 4, 5, 7, 8.1, 9, 10, `docs/requirements.md` (FR-001–FR-010, FR-020–FR-029, FR-035, FR-049, FR-051–FR-058, FR-072/073, FR-084, FR-087/088/090, NFR-010–013, NFR-021–023, NFR-030), die vorhandenen `ports`, `app`, `ui/keyboard.py`, `ui/keyboard_probe.py`. Prüfe `.deutschlandgpt/skills/` auf einschlägige Skills und befolge sie.

### Schritt 0 – Review-Korrekturen (Phase 4)

1. `app/session.py::slot_states`: MODIFIED-Zuordnung nach `(destination_folder, destination_name)` statt nur `destination_name`; Test mit zwei Slots, deren Zielordner gleichnamige Dateien enthalten.
2. Verlust des Recovery-Pending-Zustands beheben (`checking` wird in `reconcile()` zurückgesetzt): eigenes Feld im `SessionSnapshot`, getestet.
3. Unbenutzten Parameter `event` in `app/reconcile.py::_safe_log` entfernen.
4. `FolderSession.set_sort_direction`: erst speichern, dann Zustand ändern (oder bei Fehler zurückrollen); Test mit fehlschlagendem `SettingsStore`.
5. Test für `accept_damaged_data` bei nur beschädigter SQLite-Datei ergänzen, falls noch nicht vorhanden.

### Schritt 1 – `ports/imaging.py` und `imaging`

- Port `ImageDecoder.decode(path: Path, max_width: int, max_height: int) -> DecodedImage` und frozen `DecodedImage(width, height, has_alpha, data: bytes)` (RGB/RGBA-Rohpuffer, kein Qt); typisierte `ImageDecodeError` mit `StrEnum`-Gründen (`MISSING`, `UNSUPPORTED`, `CORRUPT`, `TOO_LARGE`, `HEIC_UNAVAILABLE`), analog zu `ports/errors.py`.
- `imaging/decoder.py` (`PillowImageDecoder`): Pillow, `pi-heif` registrieren (Fehlschlag → `HEIC_UNAVAILABLE` nur für HEIC/HEIF, restliche Formate bleiben nutzbar), erster Frame (FR-022), `ImageOps.exif_transpose` (FR-021), `Image.draft()` für JPEG, hochwertiger Downscale, niemals hochskalieren (FR-020), Konvertierung nach RGB/RGBA, Dekompressionsbomben-Limit explizit behandeln. Dekodierung verändert nie die Quelldatei und loggt weder Bildinhalt noch EXIF/GPS.
- `imaging/cache.py`: Preload-Cache (aktuelles Bild ± 2 Nachbarn in Navigationsrichtung, begrenzt nach Anzahl und Gesamtbytes, alles andere freigeben, NFR-013), reine Logik ohne Qt und Threads testbar; Generationsnummer verwirft veraltete Ergebnisse (FR-026). Der Cache hält die dekodierten Originalgrößen; Re-Render bei Resize erfolgt aus dem Cache.
- Tests: kleine Testbilder unter `tests/data/` (JPEG mit EXIF-Orientierung, PNG mit Alpha, animiertes GIF/WebP, eine HEIC-Datei mit Lizenzhinweis, defekte Datei, 0-Byte-Datei), Cache-Eviction, Generationsverwurf, kein Upscaling, Fehlerarten.

### Schritt 2 – Worker-Infrastruktur (Qt erlaubt nur in `ui`/`bootstrap`)

- `ui/workers.py`: Ein-Thread-Executor für Dateioperationen (`QThreadPool` mit `maxThreadCount=1` oder eigener `QThread`) und Pool mit 2 Threads für Dekodierung; Ergebnisse per Qt-Signal (queued) an den UI-Thread. Der `FolderSession`-Zugriff läuft ausschließlich auf dem Datei-Worker; die UI bekommt nur unveränderliche `SessionSnapshot`s. `navigate`/`refresh`/`set_sort_direction`/`slot_states`/`plan_toggle`/`execute_toggle`/`reconcile` laufen dort, damit FR-051 und NFR-012 (kein File-I/O im UI-Thread) halten. Busy-Indikator erst nach ca. 1 s.
- Zustandsabfragen (`slot_states`) nach jedem Wechsel des Bildes asynchron anstoßen; ein veraltetes Ergebnis (anderes Bild) verwerfen.
- Sauberes Herunterfahren: laufende Operation abwarten, dann `FolderSession.close()` (Lock freigeben), Logger schließen, `stop_application`.

### Schritt 3 – `bootstrap.py` und `__main__.py`

- Composition Root: `platformdirs`-Pfad (Technical Design 6.1), `store`-Adapter, `fsops`-Adapter, `LocalFolderLockFactory`, `JsonlEventLogger`, System-Clock, `PillowImageDecoder`; `load_startup` aufrufen; bei beschädigten Daten Dialog „Mit Standardwerten fortfahren / Beschädigte Daten unverändert lassen“ (FR-062/063, Design 6.4): bei Ablehnung nur Ansicht, Slot-Aktionen deaktiviert (`register_available=False`). Beim Start `app.start`-Event, beim Ende `app.stop`.
- `__main__.main()` startet `QApplication`, bootstrap und Event-Loop; unbehandelte Ausnahmen werden geloggt und dem Nutzer als verständlicher Fehlerdialog (FR-090) gezeigt.
- Gemäß Design 9.3 ist die Sprache der Standardwert aus `default_language`; da die i18n-Kataloge erst in Phase 6 kommen, lege nur eine minimale englische Textquelle `ui/texts.py` als einzigen Ort für UI-Strings an (benannte Schlüssel, benannte Platzhalter), damit Phase 6 sie nach JSON migrieren kann. Keine Strings verstreut im Code.

### Schritt 4 – Hauptfenster (`ui/main_window.py` u. a.)

Gemäß Design 9.1, Dark-Style `#2B2B2B`/`#383838`, sichtbarer Fokus (NFR-023), Kontrast ≥ 4.5:1 (NFR-022) – als Qt Style Sheet in `resources/`:

- Top-Bar: Profilname (Tooltip voller Pfad), Ordner öffnen (`QFileDialog.getExistingDirectory`, FR-001/002), Sortierrichtung, Aktualisieren, Abgleichen (manuell, hasht immer), Einstellungen/Hilfe als deaktivierte Platzhalter-Buttons (Phase 6).
- Bildansicht: skaliert, kein Upscaling, Fehler-/Leerzustand anstelle des Bildes (FR-006/023), dezenter Rand-Hinweis über `boundary_reached` (FR-025), Neuzeichnen bei Resize aus dem Cache.
- Infozeile: Dateiname (elided, Tooltip), Stern wenn irgendwo ausgewählt (FR-072), „12 von 80“, Fortschrittsbalken, Anzahl ausgewählter Bilder (FR-027–029).
- Slot-Leiste: bis zu 12 Kacheln mit Tastenlabel, Zielname, Farbstreifen und Zustand als **Symbol plus Text** (none/ready/selected/modified/conflict/faulty, FR-073, FR-087); „prüfe…“ während Recovery/Abgleich.
- Feedback-Bereich: kurze Meldung mit Slotfarbe, Taste, Name, „hinzugefügt/entfernt“ (FR-056). Kein Sound in dieser Phase.
- Tastatur: `ui/keyboard.py` wiederverwenden (physische Positionen, Auto-Repeat und Modifier blockiert, FR-084-Guard). Zusätzlich `QApplication.activeModalWidget()` und `activePopupWidget()` im Guard berücksichtigen (offener Punkt aus Review Phase 2). Pfeiltasten/Pos1/Ende o. Ä. gemäß SRS-Navigation. Gelernte Tastenlabels über `app/keys.py` persistieren und beim Start anwenden.
- Slot-Aktivierung: Bild zum Zeitpunkt des Tastendrucks erfassen (FR-052) → `plan_toggle` auf dem Worker → bei `NAME_REQUIRED` Namensdialog mit Live-Validierung (`validate_folder_name`, FR-034/035; Abbruch = keine Dateioperation, sonst `set_destination_name` und erneut planen) → bei `MODIFIED_CONFIRMATION_REQUIRED` Bestätigungsdialog mit Dateiliste, Standardschaltfläche „Abbrechen“ (FR-049) → `execute_toggle` → Feedback und Slot-Zustände aktualisieren. `BUSY` zeigt kurzes Feedback (FR-051), Fehler/Konflikte als `QMessageBox` mit Klartext und Details (FR-090).
- Beim Schließen während einer Operation: warten, nicht abbrechen.

### Tests und Prüfungen

- Reine Logik (Cache, Decoder, Style-/Kontrastrechnung, Textquelle) ohne Qt testbar halten.
- `pytest-qt` UI-Tests in `tests/ui/`: Fenster mit Fake-Ports/-Session aus `tests/fakes/`, Navigation + Rand-Cue, Slot-Taste → Namensdialog → Toggle on/off, Bestätigungsdialog Default = Abbrechen, Tasten werden bei offenem Dialog ignoriert, Auto-Repeat ignoriert, Busy-Verhalten, Fehleranzeige bei defektem Bild, Schließen mit laufender Operation. Alle Dateitests nutzen `tmp_path` und die Source-Guard-Hilfen.
- Integration: echter `bootstrap` gegen `tmp_path`-Datenverzeichnis (Offscreen-Plattform `QT_QPA_PLATFORM=offscreen`), Ordner öffnen, Bild anzeigen, Toggle on/off Byte-genau, Lock verhindert zweite Instanz (NFR-043).
- Performance-Smoke (nicht blockierend): Dekodierung eines großen JPEG und Scan von 10.000 Dateien – Messwerte ins Handoff, keine harten Grenzwerte in CI.
- Pflichtläufe: `uv sync --locked`, `uv run ruff format --check`, `uv run ruff check`, `uv run pyright`, `uv run pytest`; `ruff check --show-settings` für `imaging` (PySide6-Verbot aktiv) und temporärer Banned-Import-Test (`imaging -> PySide6`, `app -> ui`), danach entfernen. Starte die App einmal per `uv run python -m vuechoixgarde` mit einem Testordner (Offscreen oder nach Möglichkeit sichtbar), prüfe Screenshot und Konsole.

### Nicht Teil von Phase 5

Settings-Dialog, Slot-Editor, Profilverwaltung/Orphan-Zuordnung (FR-042), JSON-Kataloge de/en/fr, Hilfe (F1), Sound, QColorDialog, „Log-Ordner öffnen“, PyInstaller/CI, FR-071. Keine Änderungen an `core`, `fsops`, `store` außer zwingenden, begründeten Fehlerkorrekturen.

### Abschluss

Aktualisiere `.deutschlandgpt/handoff.md` (neuer Abschnitt „Phase 5 results“: Umsetzung, Entscheidungen, Verifikation, Performance-Messwerte, offene Punkte inkl. weiterhin ausstehender manueller Tastaturtests auf Linux X11/Wayland, Windows, macOS; Verweis auf Phase 6). Melde am Ende: geänderte Dateien, Testergebnisse, bewusste Abweichungen.

---

## Risks

- Qt-Threading: `FolderSession` ist nicht thread-sicher; ein einziger Besitzer-Thread ist Pflicht.
- Große Phase: bei Überschreitung lieber Schritt 4 in 5a (Anzeige/Navigation) und 5b (Slots/Dialoge) teilen.
- HEIC-Dekodierung und Tastaturereignisse sind nur auf der Entwicklungsplattform verifizierbar.
