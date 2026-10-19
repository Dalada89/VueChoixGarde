# Phase 5 review and Phase 6 prompt

## Context

Phase 5 (imaging, workers, bootstrap, minimal main window) was reviewed by reading `ui/main_window.py`, `ui/workers.py`, `bootstrap.py`, `imaging/cache.py`, parts of `app/session.py`, `ui/keyboard.py`, the Phase 5 handoff section and the test file list. Plan mode forbids running commands, so `uv run ruff format --check`, `ruff check`, `pyright` and `pytest` were NOT re-run; the numbers in the handoff (302 passed, 1 skipped) are taken from it. The test bodies of `tests/unit/test_imaging.py`, `tests/integration/test_phase5_*.py` and `tests/unit/test_ui_texts_style.py` were not read. Re-run all checks before committing.

## Review result Phase 5

No blocking finding. Worker design is sound (one serialized file worker, queued-signal delivery, `FolderSession` only touched on that worker), the Phase 4 review fixes are in (slot MODIFIED lookup keyed by `(destination_folder, destination_name)`, `recovery_pending`), the FR-084 guard now checks `activeModalWidget`/`activePopupWidget` (`ui/keyboard.py:78`), the modified-copy dialog defaults to Cancel, and shutdown waits for in-flight work.

### Findings (fix at the start of Phase 6)

1. **Performance (medium, NFR-010/012)** `SessionService._view()` (`bootstrap.py`) calls `session.slot_states()` and loads all `copy_records` after EVERY navigation, refresh and toggle. `slot_states` resolves and lists up to 12 destination folders plus SQLite queries (`app/session.py:235-300`). The UI only starts decoding after `_apply_view` receives that view, so image display waits for the slot state work, and held-arrow navigation queues behind it on the single file worker. The Phase 5 prompt asked for slot states to be requested asynchronously and stale results discarded. Fix: `navigate` returns a cheap snapshot first (image name, index, boundary); slot states + selected count follow as a second worker job tagged with the image name/generation; the UI discards stale results and shows "checking" meanwhile. Coalesce repeated navigation jobs if more than one is queued.
2. **Image quality (medium)** `_request_neighborhood` decodes at the current label size (`max_width/max_height = image_label.width()/height()`), ignoring `devicePixelRatio` (blurry on HiDPI) and the cache holds those reduced buffers. After enlarging the window, `resizeEvent` re-renders from the smaller cached buffer (no upscaling, so the image stays small/soft until the next navigation). The Phase 5 prompt said the cache keeps larger buffers and re-renders from them. Fix: decode to a screen-based bound (e.g. the largest available screen size x devicePixelRatio, capped) and scale in the UI; or invalidate and re-decode the current image (debounced) when the label grows beyond the cached size.
3. **Architecture (medium)** `SessionService` and `SessionView` live in `bootstrap.py`, a Qt-importing module, and `ui/main_window.py` imports `bootstrap` while `bootstrap` imports `ui.texts`. The use-case orchestration is therefore not testable without Qt and the layering is circular in spirit. Move `SessionService`/`SessionView` to `app/service.py` (Qt-free, covered by the ruff `app` import bans), keep only the composition in `bootstrap`, and move the damaged-data dialog behind a callback so `create_runtime` has no Qt import at module level. Drop the `object`-typed callbacks and the many `cast(SessionSnapshot, ...)` calls in `main_window.py` (`SessionView.snapshot` is already typed).
4. **Silent failures (medium, FR-090/091)** `SessionService.open_folder` swallows a failing settings save (`except Exception: pass`), `_view` sets `selected = 0` on any exception, and `slot_states` maps every exception to `FAULTY` without logging. Log these with the existing privacy-safe logger events and show a non-modal hint where the user would otherwise see wrong data.
5. **Minor** Learned key labels are persisted on each slot key press, but the slot tiles only refresh with the next view; trigger a re-render after `learn_key` returns. `learn_key` is also queued before `plan_slot`, so a slow disk delays the toggle; acceptable, but only enqueue when the label actually changes.
6. **Minor** UI strings and colors outside the central places: accessible name `"Selected in a destination"` in `main_window.py`, inline `setStyleSheet` colors (`#F2D06B`, `#FF8A80`, slot stripe). Move strings to `ui/texts.py` and the colors to `resources/dark.qss` (object names/properties) so Phase 7 localization and the contrast test cover them.
7. **Test gaps to check/add** (5 window tests exist): boundary cue at both ends (FR-025), auto-repeat and modifier combinations ignored, slot keys ignored while a dialog or popup is open (FR-084), `BUSY` feedback while a toggle is running (FR-051), CONFLICT message box, resize without re-decoding, stale decode/slot-state result discarded, second instance refused by the folder lock (NFR-043) through `bootstrap`. Verify navigation keys against FR-023-FR-025 (only Left/Right are bound; confirm whether Home/End or others are required by the SRS).
8. **Documentation/hygiene** `README`/handoff still say HEIC is validated only for the unavailable path; real HEIC fixture and manual keyboard checks remain open (unchanged).

## Roadmap: remaining phases

Phases 1-5 are done. Three phases remain (6, 7, 8); FR-071 stays deferred.

- **Phase 6 (this prompt)**: Phase 5 review fixes; Settings dialog (general options), slot editor with key remapping, color and destination name for the global template and the current profile, profile management incl. orphaned profiles (FR-042), "open log folder".
- **Phase 7**: i18n catalogs de/en/fr (migrate `ui/texts.py` to JSON, language switch, `default_language`), Help/F1 incl. keyboard-label and dead-key explanations (FR-086), sound (`QSoundEffect`, FR-057), final visual/contrast/focus review, accessibility pass.
- **Phase 8**: PyInstaller one-folder builds, GitHub Actions CI + release workflow, unsigned-app documentation (NFR-044), license decision and third-party notices (PySide6 LGPL, `pi-heif`/libheif), HEIC fixtures with license note, manual cross-platform validation (Linux X11/Wayland, Windows, macOS keyboard + paths), performance checks for 10,000 images.

## Prompt for Phase 6 (copy everything between the lines)

---

Du bist ein Implementierungsagent für das Projekt VueChoixGarde (`/home/robin/Dokumente/projects/image_sorter`). Kommunikation mit mir auf Deutsch, Code/Kommentare/Docs auf Englisch. Setze ausschließlich **Phase 6** um: Review-Korrekturen aus Phase 5, Einstellungsdialog, Slot-Editor und Profilverwaltung. Nicht commiten, keine neuen Abhängigkeiten, `docs/requirements.md`, `docs/technical-design.md`, `docs/adr/` nicht ändern. Keine geheimen Dateien (`.env`, Schlüssel, Tokens) lesen.

### Pflichtlektüre

`.deutschlandgpt/handoff.md` (Abschnitte 9-12), `.deutschlandgpt/plans/phase-6-settings-profiles.md` (Review-Befunde), `docs/technical-design.md` Abschnitte 4, 6, 7, 8, 9, `docs/requirements.md` (FR-030-FR-042, FR-060-FR-066, FR-080-FR-088, FR-091/092, NFR-021-023), `app/`, `ports/`, `ui/main_window.py`, `ui/keyboard.py`. Prüfe `.deutschlandgpt/skills/` auf einschlägige Skills und befolge sie.

### Schritt 0 - Review-Korrekturen (Phase 5)

1. Slot-Zustände asynchron: `navigate`/`refresh` liefern zuerst einen leichten Snapshot; Slot-Zustände und Auswahlanzahl folgen als zweiter Worker-Job, gekennzeichnet mit Bildname/Generation; veraltete Ergebnisse verwerfen, währenddessen „prüfe…“. Mehrfache wartende Navigationsjobs zusammenfassen. Test mit Fake-Session, die Zustandsabfragen künstlich verzögert (Anzeige des Bildes darf nicht darauf warten).
2. Dekodiergröße: bildschirmbasiert und `devicePixelRatio`-bewusst dekodieren, Cache hält die größere Fassung; Vergrößern des Fensters liefert wieder ein scharfes Bild ohne Hochskalieren über Originalgröße. Test (reine Logik der Größenberechnung ohne Qt).
3. `SessionService`/`SessionView` nach `app/service.py` verschieben (Qt-frei), `bootstrap` nur Komposition; Rückfrage bei beschädigten Daten per Callback statt Qt-Import auf Modulebene; `object`-Callbacks und überflüssige `cast(...)` in `main_window.py` entfernen. Banned-Import-Probe `app -> PySide6` und `app -> ui` danach wieder entfernen.
4. Stille Ausnahmen (`open_folder`-Speichern, `_view`-Auswahlzählung, `slot_states`-Catch-all) loggen und, wo die Anzeige sonst falsch wäre, einen dezenten Hinweis zeigen (FR-090/091). Keine Pfade oder Bildmetadaten ins Log.
5. Nach `learn_key` Slot-Kacheln neu zeichnen; `learn_key` nur einreihen, wenn sich das Label ändert.
6. Feste Strings in `ui/texts.py`, Inline-Farben nach `resources/dark.qss`; Kontrasttest erweitern.
7. Testlücken schließen (Rand-Cue, Auto-Repeat/Modifier, Tasten bei offenem Dialog/Popup, BUSY, CONFLICT-Meldung, verworfene veraltete Ergebnisse, zweite Instanz durch Lock). Navigationstasten gegen FR-023-FR-025 prüfen und ggf. ergänzen.

### Schritt 1 - Einstellungen (`ui/settings_dialog.py`)

Modaler Dialog, per Schaltfläche und Standardkürzel erreichbar (Button in der Top-Bar aktivieren). Reiter: **Allgemein** (zuletzt geöffneten Ordner wieder öffnen, Standard-Sortierrichtung, „Log-Ordner öffnen“ über `QDesktopServices`), **Slots** (globale Vorlage), **Profile**. Sprache und Ton erst in Phase 7 (nicht anlegen oder deaktiviert mit Hinweis über `texts`). Speichern über die bestehenden Settings-/State-Ports in `app` (neue Use Cases Qt-frei, mit Fake-Ports testbar); bei Speicherfehler keine halbe Änderung (erst speichern, dann Zustand übernehmen). Wenn Einstellungen beschädigt und abgelehnt wurden, ist der Dialog schreibgeschützt.

### Schritt 2 - Slot-Editor

Für globale Vorlage und aktuelles Profil: bis zu 12 Slots, Zielname (Live-Validierung mit `validate_folder_name`, Duplikate über `validate_slot_profile`, FR-034/035), Farbe (`QColorDialog`, Kontrast zur Kachel prüfen), Taste per „Taste drücken“-Erfassung über die physische Position (`ui/keyboard.py`, nur erlaubte Positionen, Konflikte mit anderen Slots sichtbar, FR-081-FR-083). Änderungen am Profil wirken auf bereits kopierte Dateien nicht (Register bleibt), umbenannte Zielordner werden als solche gemeldet, nicht verschoben (siehe Design 5/6). Änderungen an der Vorlage ändern bestehende Profile nie (FR-041). Während einer Dateioperation ist Speichern gesperrt (Gate).

### Schritt 3 - Profilverwaltung (FR-042)

Liste der bekannten Profile mit Quellordner, Existenz-Status (verwaist, wenn der Ordner fehlt), Zeitstempel. Aktionen: Profil für den aktuellen Ordner auf die Vorlage zurücksetzen (mit Bestätigung), Profil löschen (nur Profil und Register, nie Bilddateien, Bestätigung, Standard „Abbrechen“), verwaistes Profil einem neuen Ordner zuordnen (Ziel darf kein vorhandenes Profil haben; Journal-/Recovery-Einträge mit übernehmen, atomar in einer Transaktion). Alle Datenbankzugriffe auf dem Datei-Worker. Kein automatisches Anwenden eines fremden Profils (Abnahmekriterium 15).

### Tests und Prüfungen

Qt-freie Use-Case-Tests (Vorlage vs. Profil, Zuordnung verwaister Profile inkl. Abbruch/Rollback, Löschen lässt Dateien unberührt), `pytest-qt`-Tests für Dialoge (Validierung, Tastenerfassung, Konflikte, schreibgeschützter Modus, Bestätigung Default = Abbrechen). Pflichtläufe: `uv sync --locked`, `uv run ruff format --check`, `uv run ruff check`, `uv run pyright`, `uv run pytest`; Offscreen-Start `QT_QPA_PLATFORM=offscreen uv run python -m vuechoixgarde` mit Testordner, Screenshot und Konsole prüfen, Ergebnis kurz beschreiben.

### Nicht Teil von Phase 6

i18n-Kataloge, Hilfe/F1, Sound, finales Styling, Packaging/CI, FR-071. Keine Änderungen an `core`, `fsops`, `store` außer zwingenden, begründeten Korrekturen (z. B. Profil-Zuordnung in `store`, dann mit Integrationstest).

### Abschluss

`.deutschlandgpt/handoff.md` aktualisieren (Abschnitt „Phase 6 results“: Umsetzung, Entscheidungen, Verifikation, offene Punkte inkl. weiterhin ausstehender manueller Tastaturtests und echter HEIC-Prüfung; Verweis auf Phase 7 und 8). Melde: geänderte Dateien, Testergebnisse, bewusste Abweichungen.

---

## Risks

- Phase 6 ist groß: Schritt 0 zuerst und separat grün bekommen; bei Überschreitung Schritt 3 (Profilverwaltung) als 6b abspalten.
- Profil-Zuordnung berührt `store` (Transaktion über Profile, Register, Journal): Integrationstest mit simuliertem Abbruch Pflicht.
- Tastenerfassung im Dialog muss mit dem FR-084-Guard zusammenspielen (Hauptfenster-Shortcuts aus, solange der Dialog offen ist).
