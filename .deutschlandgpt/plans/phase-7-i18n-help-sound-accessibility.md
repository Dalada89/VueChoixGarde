# Phase 6 review and Phase 7 prompt

## Context

Phase 6 (Phase 5 review fixes, settings dialog, slot editor, profile management) was reviewed by reading `app/service.py`, `ui/settings_dialog.py`, the settings/profile callbacks in `ui/main_window.py` (lines ~200-430), `ui/texts.py`, `ui/style.py`, `core/language.py`, `pyproject.toml`, the handoff (section 13) and the test file list. Plan mode forbids running commands, so `ruff`, `pyright` and `pytest` were NOT re-run; the numbers in the handoff (324 passed, 1 skipped) are taken from it. The bodies of `tests/ui/test_settings_dialog.py`, `test_phase6_*.py`, `test_async_status.py` and the `store` profile reassign/replace transactions were not read. Re-run all checks before committing.

## Review result Phase 6

No blocking finding in the parts read. Positives: `SessionService` and `SessionView` moved to the Qt-free `app/service.py`; slot status is now loaded asynchronously and tagged with image name and generation (`slot_status`, `_dispatch_slot_status`, stale results discarded); `open_folder` logs a failing settings save and shows a warning; `learn_key` only returns a view when labels change; settings are saved before the in-memory state is replaced; profile deletion/reassignment is guarded by `_ensure_idle()`; the active profile cannot be deleted; confirmations default to Cancel.

### Findings (fix at the start of Phase 7)

1. **Bug, slot-editor color sample (medium)** `_SlotEditor._append_row` colors the sample label via an inline `setStyleSheet`, but `_choose_color` changes it with `setPalette` (`_button_palette`). A widget style sheet overrides the palette, so after choosing a color the sample keeps the old color (the stored `slotColor` property is right, so saving works, but the user sees the wrong preview). The handoff regression test covers the initial color only (verify). Fix: set the sample color with the same style-sheet call in both places (one helper), remove `_button_palette`, test the pixel after `_choose_color`.
2. **Bug, key conflict is not shown after capture (medium, FR-081-083)** `_KeyCaptureButton.keyPressEvent` changes `position` but emits nothing, and `_update_validation` is only connected to `key.clicked` (which fires when capturing STARTS). A duplicate key is therefore flagged only after the next unrelated edit, and Save stays enabled until then (`_save` re-validates, so no bad data is saved). Fix: add a `captured` signal on the button, connect it to `_update_validation`; Esc while capturing should cancel the capture instead of closing the dialog.
3. **Half-saved change (medium)** `save_preferences` in `main_window.py` first calls `service.save_preferences(...)` and then `save_profile_slots(...)` for target "profile". If the second step fails, the settings are already stored, but the error dialog leaves the settings dialog open as if nothing was saved. The Phase 6 requirement was "no half change". Fix: make this one service use case (`save_settings_and_profile_slots`) that validates first, stores the profile slots transaction and settings in a defined order, and reports which part failed; test with a failing fake store.
4. **Edits lost when switching the slot target (minor)** `_change_slot_target` replaces the editor with a fresh `_SlotEditor`; unsaved changes to the other target (template vs. profile) are dropped silently, as are keys learned by capture. Fix: keep one editor per target (two widgets in a `QStackedWidget`) and save both if valid, or ask before discarding.
5. **Profile action feedback (minor)** `profile_action` calls `dialog.refresh_profiles(...)` and then `dialog.accept()` (closes the dialog, refresh is pointless). On error, `_run_file` shows the error but the dialog message stays on "Updating profile data…". Fix: keep the dialog open after a profile action (refresh the table, set the done message), and reset the message on error via an error callback. Disable "Delete" for the active profile instead of raising `ValueError` (the service check stays as a safeguard).
6. **Language/sound still missing from the dialog (expected)** `Settings.language` and `sound_enabled` already exist in `ports/models.py`, `store/settings.py` (validated de/en/fr, default via `default_language`) and are carried through `_settings_with`; nothing reads them yet. This is Phase 7.
7. **Texts** `ui/texts.py` is still one English dict. Hard-coded text outside it: check `settings_dialog.py` (all keyed, good), `bootstrap.py`/`__main__.py` error messages, `app` warning keys (`service.py` returns keys like `"slot_status_failed"`, resolved in the UI, good). The slot stripe color is still an inline style sheet in `main_window.py:459` (acceptable because it is user data, but then the `dark.qss` claim in the handoff is only partly true).
8. **Tests to add or verify** Pixel test after `_choose_color`; capture conflict visible without extra edits; Esc cancels capture; failed second step of a combined save; profile action leaves the dialog open; read-only dialog (damaged settings declined) has all editors disabled including capture buttons.

## Roadmap: remaining phases

Phases 1-6 done. Two remain (7, 8); FR-071 stays deferred.

- **Phase 7 (this prompt)**: Phase 6 review fixes; i18n catalogs de/en/fr with live language switch (FR-085); Help/F1 (FR-086, FR-081 limitation, dead keys); sound (FR-057); contrast/focus/non-color review (NFR-021-023); keyboard-only operation pass (FR-080).
- **Phase 8**: PyInstaller one-folder builds, GitHub Actions CI + release workflow, unsigned-app documentation (NFR-044), license decision and third-party notices (PySide6 LGPL, `pi-heif`/libheif, bundled sound file), real HEIC fixtures, README/user documentation (NFR-032), manual cross-platform validation (Linux X11/Wayland, Windows, macOS keyboard + paths), performance checks for 10,000 images.

## Prompt for Phase 7 (copy everything between the lines)

---

Du bist ein Implementierungsagent für das Projekt VueChoixGarde (`/home/robin/Dokumente/projects/image_sorter`). Kommunikation mit mir auf Deutsch, Code/Kommentare/Docs auf Englisch. Setze ausschließlich **Phase 7** um: Review-Korrekturen aus Phase 6, Mehrsprachigkeit (de/en/fr), Hilfe/F1, Ton, Barrierefreiheits-Durchgang. Nicht commiten, keine neuen Abhängigkeiten, `docs/requirements.md`, `docs/technical-design.md`, `docs/adr/` nicht ändern. Keine geheimen Dateien (`.env`, Schlüssel, Tokens) lesen.

### Pflichtlektüre

`.deutschlandgpt/handoff.md` (Abschnitte 9-13), `.deutschlandgpt/plans/phase-7-i18n-help-sound-accessibility.md` (Review-Befunde), `docs/technical-design.md` Abschnitte 8.1, 9.1-9.4, `docs/requirements.md` (FR-056, FR-057, FR-060, FR-064, FR-080-FR-088, NFR-021-023, Abnahmekriterien 14, 16, 17), `ui/texts.py`, `ui/main_window.py`, `ui/settings_dialog.py`, `ui/keyboard.py`, `app/service.py`, `core/language.py`, `resources/dark.qss`. Prüfe `.deutschlandgpt/skills/` auf einschlägige Skills und befolge sie.

### Schritt 0 - Review-Korrekturen (Phase 6)

Zuerst separat grün bekommen:

1. Farbvorschau im Slot-Editor: ein Helfer setzt die Farbe per Style-Sheet (initial und nach `_choose_color`), `_button_palette` entfernen; Pixeltest nach der Farbwahl.
2. `_KeyCaptureButton` meldet das Ende der Erfassung per Signal; Validierung (Konflikte, Speichern-Button) aktualisiert sich sofort; Esc bricht die Erfassung ab und schließt den Dialog nicht.
3. Kombiniertes Speichern (Einstellungen + Profil-Slots) als ein Use Case in `app/service.py`: erst alles validieren, dann in definierter Reihenfolge speichern; bei Fehler im zweiten Schritt klare Meldung, welcher Teil gespeichert wurde, und der Dialog bleibt offen. Test mit fehlschlagendem Fake-Store.
4. Bearbeitungen beider Slot-Ziele (Vorlage/Profil) bleiben beim Umschalten erhalten (zwei Editoren in einem `QStackedWidget`), gespeichert wird, was geändert und gültig ist.
5. Profilaktionen schließen den Dialog nicht; Tabelle aktualisieren, Meldung „erledigt“ bzw. Fehlermeldung (Meldung „Updating…“ darf nie hängen bleiben); „Profil löschen“ für das aktive Profil deaktivieren.
6. Tests: siehe Befund 8 der Datei `phase-7-i18n-help-sound-accessibility.md`.

### Schritt 1 - Mehrsprachigkeit (FR-085, Design 9.3)

- Neue JSON-Kataloge `src/vuechoixgarde/i18n/{en,de,fr}.json` (Schlüssel = bisherige Schlüssel aus `ui/texts.py`, benannte Platzhalter). `ui/texts.py` bleibt als dünne Lookup-Funktion `text(key, **values)` mit `set_language(code)`; fehlender Schlüssel in `de`/`fr` fällt auf `en` zurück und wird einmal geloggt; fehlt er auch in `en`, ist das ein Testfehler. Kataloge über `importlib.resources` laden (auch im späteren PyInstaller-Build lauffähig); prüfe, dass `uv_build` die JSON-Dateien ins Wheel aufnimmt.
- Test (ohne Qt): alle drei Kataloge haben dieselben Schlüssel und dieselben Platzhalter je Schlüssel; kein ungenutzter und kein fehlender Schlüssel gegenüber den im Code verwendeten (`text("...")` per `ast` oder Regex im Test einsammeln).
- Sprache beim Start: `settings.language` (Default kommt bereits aus `default_language(QLocale.system().name())` im Store, Nachweis per Test). Qt-Standarddialoge (Datei-Dialog, Farbdialog, Buttons) per `QTranslator` mit `qtbase_<lang>` aus `QLibraryInfo.TranslationsPath` laden; fehlt die Datei, wird das ohne Fehler übergangen.
- Einstellungen → Allgemein: Sprachauswahl (Deutsch / English / Français, Sprachnamen in der eigenen Sprache, nicht übersetzt). Wirkt „sofort nach dem Speichern“ (FR-064): nach erfolgreichem Speichern `set_language`, Qt-Translator wechseln und das Hauptfenster neu beschriften (`retranslate()` für Top-Bar, Info-Zeile, Slot-Kacheln, Statusleiste, Tooltips; Settings-Dialog wird ohnehin neu geöffnet). Keine Neustart-Pflicht.
- Alle Meldungen aus `app`/`ports` bleiben schlüssel- bzw. enum-basiert; kein übersetzter Text in `core`/`app`/`store`. `FolderNameError`, `ProfileError`, `DecodeFailure`-Gründe, Fehlerdialoge, Lock-Fehler (NFR-043), Damaged-Data-Dialog, Konflikt-/Modified-Dialoge: alles über Kataloge. Technische Details im Fehlerdialog bleiben unübersetzt im aufklappbaren Detailbereich.
- Übersetzungen: gute, knappe Texte; DE mit „Sie“-freier, neutraler Formulierung (Infinitiv/Imperativ), FR formell neutral. Begriffe konsistent (Zielordner / dossier de destination / destination folder; Profil; Slot → in DE „Slot“, in FR „emplacement“ nur falls konsistent; entscheide einmal und halte es durch).

### Schritt 2 - Hilfe / F1 (FR-086, FR-081, FR-083)

- `ui/help_dialog.py`: nicht-modaler oder modaler Dialog (modal ist einfacher und FR-084-konform), geöffnet per `F1` und über den bisher deaktivierten Hilfe-Button. Inhalt: feste Tasten (→ ← F1 F5 Esc) , aktuelle Slot-Tasten mit Beschriftung, Zielname (oder „kein Name“) und Farbe samt Textzustand (nicht nur Farbe, NFR-021), Erklärung des Umschaltverhaltens (Kopie anlegen/entfernen, Quelldateien werden nie verändert), Hinweis auf geänderte Kopien (Bestätigung), Hinweis zu Beschriftung auf Nicht-US-Layouts (FR-081-Einschränkung: Taste einmal drücken, damit die Beschriftung stimmt; Tote Tasten/Akzente können kurz eine falsche Beschriftung lernen, korrigiert sich beim nächsten Druck - Phase-2-Follow-up), Erreichbarkeit der Log-Ordner-Aktion (FR-092).
- Esc schließt die Hilfe; der FR-084-Guard (`activeModalWidget`) muss Slot-/Navigationstasten im Hauptfenster währenddessen sperren (Test). `F1`/`F5` dürfen nicht durch Textfelder blockiert werden, wo sie nicht gebraucht werden, aber in Dialogen mit Textfeld nicht auslösen.
- Der Hilfetext wird aus den aktuellen Daten (Profil, gelernte Labels, Sprache) gebaut, nicht aus einem statischen String; `help_text` in `texts.py` entfällt. Tests: Inhalt für 4 und 12 Slots, Sprachwechsel, Slot ohne Namen.

### Schritt 3 - Ton (FR-057, Design 9.4)

- Kurze, leise, selbst erzeugte WAV-Datei (Skript oder Python-Einmalcode, kein Fremdmaterial, Lizenzvermerk „selbst erzeugt, CC0/Projektlizenz“ in einer kurzen Textdatei neben der WAV und im Handoff) in `resources/sounds/`. Erzeugung reproduzierbar (kleines Skript unter `tools/` oder Test, das die Datei bytegleich erzeugt), < 50 KB.
- `ui/sound.py` mit `QSoundEffect`, Lautstärke ca. 0.4; Schnittstelle `SoundPlayer.play_added()`. Abspielen nur nach erfolgreichem **Hinzufügen** (nicht beim Entfernen, nicht bei Konflikt, Abbruch, Fehler, BUSY). Ist `settings.sound_enabled` falsch oder das Audio-Backend nicht verfügbar (`QSoundEffect` Status Error, offscreen/CI), einmal loggen und sonst ignorieren; nie eine Ausnahme nach oben.
- Einstellungen → Allgemein: Checkbox „Ton“; wirkt sofort nach dem Speichern.
- Test mit Fake-Player: Aufrufe nur bei ADDED, nicht bei REMOVED/CONFLICT/CANCELLED/Fehler; deaktiviert → keine Aufrufe; Backend-Fehler wird geschluckt.

### Schritt 4 - Barrierefreiheit und Darstellung (NFR-021-023, FR-088, FR-080)

- Kontrast: Test über alle Text/Hintergrund-Paare aus `dark.qss` (Paare aus der Datei lesen oder eine kleine Tabelle im Test pflegen) ≥ 4,5:1, auch für Fokus-, Hover-, Disabled-Zustände von Text. Standardfarben der 12 Slot-Paletten-Farben gegen Kachelhintergrund prüfen; Slot-Text niemals in Slot-Farbe auf Kachelhintergrund setzen, wenn der Kontrast < 4,5:1 ist (Stripe/Symbol statt Text).
- Fokus: sichtbarer Fokusrahmen für Buttons, Eingaben, Tabellen, Tabs, Checkboxen, ComboBoxen in `dark.qss`; Screenshot-Prüfung (offscreen) von Hauptfenster, Einstellungen (alle Reiter), Hilfe, Modified-Dialog.
- Nicht nur Farbe: jede Slot-Kachel zeigt Taste, Name, Symbol + Text für den Zustand (NFR-021); Test, dass jeder `SlotState` ein Symbol und einen Text in allen drei Sprachen hat.
- Accessible Names/Descriptions für Bild, Slot-Kacheln, Fortschritt, Buttons (`setAccessibleName`), alles über Kataloge. Tab-Reihenfolge in den Dialogen sinnvoll; Mnemonics nur, wenn sie nicht mit Slot-Tasten kollidieren (Hauptfenster ohne Mnemonics).
- Tastaturbedienung (FR-080): Prüfe gegen FR-083 und Abnahmekriterium; Öffnen von Ordner und Einstellungen ist per Maus oder Tastatur möglich (Standardkürzel, in Hilfe aufgeführt); keine Funktion nur per Maus. Fenstermindestgröße so, dass 12 Slots ohne Verdeckung sichtbar sind (FR-087); Test mit 12 Slots und langen Zielnamen (Elide + Tooltip).
- Bekannte Phase-6-Altlast prüfen: Slot-Streifen-Farbe als Inline-Style in `main_window.py` (~Zeile 459) ist wegen Nutzerfarbe akzeptabel, aber die Aussage im Handoff „per `QFrame#slotStripe` im QSS“ korrigieren.

### Tests und Prüfungen

Qt-freie Tests für Katalog-Konsistenz und Sprachwahl, `pytest-qt`-Tests für Sprachwechsel zur Laufzeit (Texte im Hauptfenster ändern sich ohne Neustart), Hilfe-Dialog, Ton-Aufrufe, Fokus-/Kontrastpaare. Pflichtläufe: `uv sync --locked`, `uv run ruff format --check`, `uv run ruff check`, `uv run pyright`, `uv run pytest`; Offscreen-Start `QT_QPA_PLATFORM=offscreen uv run python -m vuechoixgarde` mit Testordner, je ein Screenshot in de/en/fr (Hauptfenster + Hilfe + Einstellungen) prüfen und Konsole kontrollieren; Ergebnis kurz beschreiben. Testdaten und Vorschaubilder danach wieder löschen.

### Nicht Teil von Phase 7

Packaging/CI, Lizenzentscheidung, README/Benutzerdoku (Phase 8), echte HEIC-Fixtures, manuelle Plattformtests, FR-071. Keine Änderungen an `core`, `fsops`, `store` außer zwingenden, begründeten Korrekturen (z. B. neue Settings-Felder sind nicht nötig).

### Abschluss

`.deutschlandgpt/handoff.md` aktualisieren (Abschnitt „Phase 7 results“: Umsetzung, Entscheidungen inkl. Terminologie-Entscheidungen und Herkunft/Lizenz der WAV, Verifikation, offene Punkte inkl. weiterhin ausstehender manueller Tastaturtests und echter HEIC-Prüfung; Verweis auf Phase 8). Melde: geänderte Dateien, Testergebnisse, bewusste Abweichungen.

---

## Risks

- Live-Sprachwechsel berührt viele Widgets: ein zentrales `retranslate()` im Hauptfenster und ein Test, der alle sichtbaren Texte vor/nach dem Wechsel vergleicht, verhindert „vergessene“ Labels. Fallback bei Zeitnot: Wechsel wirkt nach Neustart (dann Hinweistext) - das wäre eine Abweichung von FR-064 und muss gemeldet werden.
- Audio ist in CI/offscreen oft nicht verfügbar: Tests nur mit Fake-Player; echtes Abspielen bleibt manueller Test (Phase 8 Checkliste).
- Übersetzungsqualität: DE/FR sollten vor Release von einer Muttersprachlerin bzw. einem Muttersprachler gelesen werden.
- Schritt 0 zuerst und separat grün; Hilfe, Ton und Barrierefreiheit sind unabhängig und können bei Überlauf als 7b folgen.
