# Finales Code-Review VueChoixGarde – 2026-10-21

Stand: Commit `8108ea6` (main) plus lokale Änderung `docs/requirements.md` v0.7.

## Automatische Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `uv sync --locked` | Umgebung aktuell |
| `ruff format --check` | 135 Dateien formatiert |
| `ruff check` | keine Befunde |
| `pyright` | 0 Fehler, 0 Warnungen |
| `pytest` (offscreen) | 354 passed, 1 skipped (Windows-only, `tests/integration/test_fsops.py:426`) |

Legende: **✔** selbst am Code nachgeprüft · ✱ vom Teil-Review belegt, nicht separat nachgeprüft · ✘ widerlegt.

## Hoch

| # | Ort | Befund | Status |
|---|---|---|---|
| H1 | `ui/main_window.py:379–398` | `save()` läuft im Datei-Worker und liest Qt-Widgets (`slot_editors[...].slots()`, `language_combo.currentData()`, `sound_checkbox.isChecked()`). Das ist nicht thread-sicher und widerspricht `technical-design.md:112`. Werte im UI-Thread kopieren. | ✔ |
| H2 | `app/service.py:~238–245`, `i18n/*.json` (`destination_renamed`) | Meldung „Zielordner wurde umbenannt“ ist eine Heuristik; physisch wird nichts umbenannt. Sie erscheint auch nach Slot-Entfernen bzw. Profil-Reset und bei jeder Navigation. → Plan `zielordner-umbenennen-loeschen.md` | ✔ |
| H3 | `app/service.py:227–232` | Nach einer Namensänderung legt der nächste Toggle einen neuen Ordner an; alte Kopien lassen sich nicht mehr abwählen, `selected_image_count` zählt sie weiter. → Plan | ✱ |
| H4 | `app/toggle.py:243–247`, `ui/main_window.py:846–862` | FR-049: Nach „Ja“ wird neu geplant, und `confirmed_modified=True` gilt dann für jede zu diesem Zeitpunkt geänderte Kopie, auch für Dateien, die im Dialog nicht angezeigt wurden. Bestätigte Namen und Hashes mitgeben, bei Abweichung erneut fragen. | ✔ |
| H5 | `store/state.py:164` | `except sqlite3.DatabaseError` fängt auch `OperationalError` („database is locked“, I/O) ab und meldet DAMAGED; `reset_damaged` schiebt dann eine gesunde DB samt `-wal` in Quarantäne. `OperationalError` getrennt behandeln, nur bei Integritätsfehlern DAMAGED. | ✔ |
| H6 | `store/settings.py:70` | `read_text(encoding="utf-8")` wirft bei ungültigen Bytes `UnicodeDecodeError`, gefangen wird nur `OSError` → Absturz statt DAMAGED (das `except UnicodeError` in Zeile 76 greift nie). | ✔ |
| H7 | `.github/workflows/release.yml:66` | `run: "${{ matrix.executable }}" --smoke-test` ist ungültiges YAML (Inhalt nach dem schließenden Anführungszeichen). Der Release-Workflow lädt nicht. Als Block-Skalar mit `shell: bash` schreiben. | ✔ |
| H8 | `.github/workflows/release.yml` Job `draft-release` | Ohne Checkout und ohne `GH_REPO`/`--repo` kennt `gh release create` kein Repository. `GH_REPO: ${{ github.repository }}` setzen. | ✔ |

## Mittel

| # | Ort | Befund | Status |
|---|---|---|---|
| M1 | `ui/main_window.py:855`, `i18n/de.json:110` | FR-049-Dialog: Die Dateinamen stehen nur im eingeklappten `detailedText`, der Hinweis auf Datenverlust fehlt. | ✱ |
| M2 | `ui/main_window.py:766–776` | Slot-Aktionen während eines Abgleichs/Refresh werden eingereiht statt mit BUSY abgewiesen (FR-051); `OperationGate` ist praktisch nie belegt. | ✱ |
| M3 | `ui/main_window.py:915ff` u. a. | Fehlerdialoge zeigen `str(error)` mit englischen, technischen Texten (FR-085/FR-090). Stabile Fehlercodes → i18n. | ✱ |
| M4 | `ui/main_window.py:~815–827` | FR-056: Erfolgsmeldung ohne Slot-Farbe. | ✱ |
| M5 | `fsops/filesystem.py:225–232, 388–409, 517, 578` | TOCTOU: Containment wird am Pfad geprüft, danach wird per Pfadstring gearbeitet; ein zwischenzeitlich eingesetzter Symlink führt nach außen. POSIX: `dir_fd`/`O_NOFOLLOW`. | ✱ |
| M6 | `fsops/filesystem.py:573–578` mit `:244–259` | Verifiziertes Löschen: Hash über `open()` (folgt Symlinks), danach `unlink` am Pfad → Austausch zwischen Hash und Löschen möglich. `st_ino`/`st_dev` vergleichen. | ✱ |
| M7 | `fsops/filesystem.py:544–547` | Finalisierung erfolgreich, aber Temp-Datei nicht entfernbar → `IO_ERROR`, obwohl die Zieldatei existiert. | ✱ |
| M8 | `store/state.py` (alle `with self._connect()` außer `load`) | SQLite-Verbindungen werden nie geschlossen (der Kontextmanager committet nur). `contextlib.closing`. | ✱ |
| M9 | `store/settings.py:88–99` | Settings-Reset auch bei bloßem `IO_ERROR` → intakte Datei wird ersetzt. | ✱ |
| M10 | `store/settings.py:129–133` | Surrogates in `last_folder` → `UnicodeEncodeError`; Temp-Datei bleibt liegen, untypisierter Fehler. Außerdem kein Verzeichnis-`fsync` nach `replace`. | ✱ |
| M11 | `store/state.py:443` | `reassign_profile`: Fallback `Path(destination_name).parent` = `"."` schreibt falsche Registerpfade; abbrechen statt raten. Außerdem werden offene Operationen des eigenen Profils nicht geprüft (`:410`). | ✱ |
| M12 | `store/state.py:188–195` | Quarantäne verschiebt zuerst `-wal`/`-shm`, dann die DB; scheitert Letzteres, ist die WAL getrennt. | ✱ |
| M13 | `imaging/decoder.py:41–42` | `warnings.catch_warnings()` ist prozessweit, also nicht thread-sicher. Die Decompression-Bomb-Prüfung kann bei parallelen Decodes ausfallen. Pixelzahl selbst prüfen. | ✱ |
| M14 | `__main__.py:44–62` | Excepthook öffnet `QMessageBox` auch bei Ausnahmen aus Nicht-GUI-Threads; Traceback wird doppelt ausgegeben. | ✱ |
| M15 | `.github/workflows/ci.yml:27` | `astral-sh/setup-uv@v5` ungepinnt (im Release auf SHA gepinnt). | ✱ |
| M16 | `release.yml:52–57` | Tag-Prüfung mit `uv run` ohne `--locked` vor `uv sync --locked`. | ✱ |
| M17 | `release.yml` | Release-Build ohne ruff/pyright/pytest; ein Tag auf einem roten Commit wird gebaut. | ✱ |
| M18 | `release.yml:66`, `packaging/vuechoixgarde.spec:131` | Windows-GUI-Exe (`console=False`): Ob der Exit-Code des Smoke-Tests ausgewertet wird, ist unbelegt. | ✱ |
| M19 | `packaging/vuechoixgarde.spec:68–81` | QtWebSockets, QtHttpServer, QtNetworkAuth, QtWebChannel, QtWebView fehlen in `_excludes` (werden erst von `check_bundle.py` erkannt). | ✱ |
| M20 | `tools/check_bundle.py:38, 49` | Versionierte `.so.N`-Dateien ohne Ausführungsbit werden nicht auf x265-Symbole gescannt. | ✱ |
| M21 | `docs/adr/0002-…md` | Offene Produktentscheidung: QML/Quick- und FFmpeg-`ssl`/`crypto`-Stubs als transitive Multimedia-Abhängigkeiten. Laut ADR noch nicht entschieden, keine sauberen Bundle-Scans auf allen Plattformen belegt. | ✔ |

## Niedrig (Auswahl)

- `app/toggle.py:232–242`: Der Zweig `fresh.action is CONFLICT` ist unerreichbar, Konflikte werden deshalb nie geloggt. ✔ (Zeile 230 kehrt vorher zurück)
- `main_window.py:~790`: `_handle_plan` prüft auf `MODIFIED_CONFIRMATION_REQUIRED`, das `plan_toggle` nie liefert. `auto_repeat` wird nie übergeben (`service.py:167–185`). ✱
- `settings_dialog.py:153–159`: Nur der letzte Slot ist entfernbar, ohne Rückfrage. Speichern lässt sich während der Worker-Ausführung erneut auslösen (N4). ✱
- `fsops/filesystem.py:346–367`: `create_destination_folder` prüft vor `mkdir` keine Namensvarianten (Linux: `auswahl` neben `Auswahl`). ✱
- `fsops/filesystem.py:408`: Kopien entstehen mit Modus `0o600`. ✱
- `store/state.py:625`: `complete_operation` ohne Behandlung doppelter Schlüssel. Neuere `user_version` führt zur Quarantäne (`:144–150`). Quarantäne braucht Hardlinks (`damage.py:26`, FAT/exFAT). ✱
- `applog/jsonl.py`: Keine Feld-Positivliste gegen Metadaten (`:61–63`). Logger ohne Handler bei Anlagefehler (`:117–119`). `absolute()` statt `resolve()` (`:86`). ✱
- `bootstrap.py:39–45`: `shutdown()` ohne `try/finally`; Startfehler vor dem Logger werden nicht protokolliert (`bootstrap.py:58–63`). ✱
- `core/folder_names.py:23–32`: `CONIN$`/`CONOUT$` fehlen, keine Längengrenze. ✱
- `imaging/decoder.py:47`: Fehlerhafte EXIF-Orientierung macht das ganze Bild zu CORRUPT. ✱
- `release.yml:24`: `windows-latest` ungepinnt. `version_info.txt` hat eine feste Version ohne Prüfung. `check_bundle.py:70` prüft gegen den vollen Pfad, ein leeres Bundle besteht. ✱

## Widerlegte Teil-Befunde

- ✘ „Fremde Sidecars werden beim Ausschalten gelöscht“ (`core/toggle.py:52–58`): `app/toggle.py` `_toggle_off` überspringt alles außer VERIFIED/MODIFIED.
- ✘ „`runtime.shutdown()` läuft im Normalbetrieb nicht“: `MainWindow.closeEvent` übergibt es dem Worker (`ui/main_window.py:1049–1055`).
- ✘ „`PySide6.QtNetwork` in `hiddenimports` verstößt gegen NFR-005“: Das ist laut ADR 0002 bewusst so entschieden.

## Testbefunde

- `tests/integration/test_phase6_profiles.py:120–136` prüft nichts Wirksames: Das Profil zeigt auf `/source`, das Bild liegt woanders, die Assertion ist immer wahr.
- `tests/ui/test_settings_dialog.py:175–185`: `rowCount()==1` ist durch einen No-op-Callback immer wahr.
- `tests/ui/test_main_window.py:168` vergleicht den Default-Button über den Text `"Cancel"` statt über die Rolle.
- Nicht getestet sind: Slot-Entfernen, direktes `replace_profile_slots`, die UI-Anzeige von `destination_renamed`. `source_guard` wird in den phase6-Tests nicht genutzt. `runtime.shutdown()` steht in mehreren Tests nicht im `finally`.

## Nicht geprüft

Vollständig gelesen wurden weder `ui/keyboard.py`, `ui/keyboard_probe.py`, `app/keys.py`, `core/keys.py` und `core/native_keys.py` (FR-084, Auto-Repeat) noch `app/startup.py`, `app/recovery.py` (nur Struktur), `ui/help_dialog.py`, `ui/sound.py`, `ui/style.py`, `core/sorting.py`, `core/navigation.py`, `core/formats.py`. Hinweis: Ein Teil-Agent hatte die `*key*`-Dateien irrtümlich als gesperrt behandelt; die Projektregel sperrt nur `*.key` sowie `*private-key*`/`*private_key*`.
