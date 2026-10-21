# Plan: Zielordner umbenennen und löschen (FR-100 – FR-104)

Stand: 2026-10-21 · Grundlage: `docs/requirements.md` v0.7, Abschnitt 5.10 sowie FR-032, FR-037, FR-039, NFR-001, NFR-003, Akzeptanzkriterien 21–24.

**Für den Implementierungsagenten:** `docs/requirements.md` ist bereits angepasst und wird NICHT geändert. Lies vor dem Start Abschnitt 5.10 vollständig. Keine versteckten Dateien außer den hier genannten lesen; `.env*`, `.git/` und Dateien mit secret/token/password/credential im Namen sind tabu. Ausgangslage: `ruff format --check`, `ruff check`, `pyright` und `pytest` sind grün (354 passed, 1 skipped) – das muss am Ende wieder so sein.

## 0. Ausgangslage (verifiziert)

- Ändert man im Einstellungsdialog den Zielordnernamen eines Slots, ersetzt `SQLiteStateStore.replace_profile_slots` (`src/vuechoixgarde/store/state.py:335`) nur die Slot-Zeilen. Ordner und Copy-Register bleiben unverändert. `SessionService.slot_status` (`src/vuechoixgarde/app/service.py:209–249`, Warnung bei ~238–245) meldet daraufhin heuristisch `destination_renamed` („Zielordner wurde umbenannt“), obwohl nichts umbenannt wurde.
- Slots haben keine stabile ID (PK `(profile_id, slot_order)`, `state.py:47–53`). Das Register verweist über den Pfad-String `copies.destination_folder` (`state.py:55`) auf den Ordner; `operations` kennt nur `destination_name` (`state.py:67`).
- `save()` in `ui/main_window.py:379–398` liest Qt-Widgets im Worker-Thread (Review-Befund H1). Da genau dieser Pfad umgebaut wird, wird H1 hier mitbehoben.
- Bausteine:
  - `fsops/filesystem.py`: `_ctypes_no_replace` (`:446–477`, Linux `renameat2`/macOS `renamex_np`, für Verzeichnisse nutzbar), `is_inside` (`:74`), `_is_link_or_junction` (`:98`), `_contained_destination` (`:225`), `_destination_names` (`:284`), `resolve_destination_folder` (`:310`), `delete_verified_file` (`:565`). Ein `rmdir` gibt es nicht.
  - `core/folder_names.py:35`: `validate_folder_name`
  - `core/comparison.py:6`: `comparison_key`
  - `core/slots.py:56`: `validate_slot_profile`
  - `core/slots.py:12`: `Slot` (frozen)
  - `ui/settings_dialog.py:481–494`: `SettingsDialog._confirm`, Default „Abbrechen“; Muster auch in `main_window.py:846–862`
  - `app/recovery.py:12`: `recover_operations`, aufgerufen in `app/session.py:138` und `app/service.py:381`

## 1. Designentscheidungen

1. **Slot-Identität für das Umbenennen:** Jede Zeile in `_SlotEditor` (`ui/settings_dialog.py:97`) merkt sich ihren beim Öffnen gespeicherten Namen (`origin_name`; `None` für neu hinzugefügte Zeilen). Beim Speichern erzeugt der UI-Thread daraus explizit `renames: tuple[FolderRename, ...]` mit `(old_name, new_name)`, aber nur für Zeilen des Editors `"profile"` mit `origin_name is not None`, `new_name is not None` und `old_name != new_name` (exakter Stringvergleich, damit auch reine Groß-/Kleinschreibungs-Änderungen erfasst werden). Entfernte Zeilen und das Zurücksetzen bzw. Zuweisen von Profilen erzeugen nie Renames (FR-032, FR-100). Wird ein Name zu leer/`None` geändert, ist das kein Rename und kein Löschen: nur der Profilname ändert sich.
2. **H1 mitbeheben:** Alle Werte (Slots beider Editoren, Sprache, Sound, Labels, Renames) werden im UI-Thread in `SettingsDialog._save` (`settings_dialog.py:501`) in ein unveränderliches `SettingsSubmission` (Dataclass) kopiert. Der Worker bekommt nur dieses Objekt.
3. **Reihenfolge beim Speichern:** Zuerst Renames und Profil-Slots als eine Einheit, danach die globalen Einstellungen. Scheitert ein Rename, wird nichts gespeichert und der Dialog bleibt offen (FR-101).
4. **Journal:** Eine eigene Tabelle `folder_renames` statt Erweiterung von `operations`. `operations` und `start_operation` sind auf Kopier-Temp-Dateien zugeschnitten (CHECK, `temp_name`-Schema). Das erfordert Schemaversion 2 mit Migrationskette.
5. **Rename nur mit sauberem Zustand:** Kein Rename und kein Löschen, solange `session.recovery_pending` gesetzt ist, das Register nicht verfügbar ist (FR-063) oder eine Dateioperation läuft (FR-051, `_ensure_idle` `service.py:406`). Daraus folgt: „eigene temporäre Dateien“ (FR-102) sind praktisch immer null. Eine Datei mit Temp-Namensmuster ohne Journal-Eintrag gilt als fremder Eintrag.
6. **Gleicher Ordner, nur andere Schreibweise** (`comparison_key(old) == comparison_key(new)`): zweistufig über einen eindeutigen Zwischennamen `.vcg-rename-<uuid4hex>` im Quellordner, beide Schritte No-Replace. Der Zwischenname steht im Journal, damit die Wiederherstellung ihn findet. Grund: `RENAME_EXCL`/`RENAME_NOREPLACE` kann auf case-insensitiven Dateisystemen mit `EEXIST` scheitern.
7. **Fehler mit stabilen Codes:** Neue Exception `FolderManagementError(reason: FolderManagementReason, *, old_name, new_name, names)` in `app/results.py`. Die UI bildet `reason` auf i18n-Schlüssel ab und zeigt **nie** `str(error)` (verhindert neue Fälle von Review-Befund M3).

## 2. Umsetzungsschritte

### Schritt 1 – Dateisystem-Port und `LocalFileSystem`

`src/vuechoixgarde/ports/filesystem.py` (Protocol) und `src/vuechoixgarde/fsops/filesystem.py` (inklusive Bindung in `LocalFileSystem`, `:603–618`) erweitern:

- `rename_destination_folder(source_root: Path, old_exact_name: str, new_name: str) -> Path`
  - `old_exact_name` muss ein existierender direkter Unterordner sein: per `lstat` prüfen, kein Link und keine Junction (`_is_link_or_junction`), `is_inside`, Verzeichnis. Sonst `FileSystemError(DESTINATION_LINK | DESTINATION_OUTSIDE | DESTINATION_FILE)`.
  - `new_name`: `validate_folder_name` muss `None` liefern, sonst `INVALID_NAME`.
  - Konfliktprüfung über `_destination_names(source_root)`: Gibt es einen Eintrag `e != old_exact_name` mit `comparison_key(e) == comparison_key(new_name)`, wird `NAME_CONFLICT` geworfen.
  - Schreibweisen-Fall (Entscheidung 6): `old → .vcg-rename-<uuid>` und dann `.vcg-rename-<uuid> → new`. Der Zwischenname wird vom Aufrufer übergeben (eigener Parameter `intermediate_name: str | None`), damit er vorher im Journal steht.
  - Rename ohne Ersetzen:
    - POSIX: `_ctypes_no_replace(extended old, extended new)`. Bei `ENOSYS`/`EINVAL` (Dateisystem ohne Unterstützung) **kein** Fallback auf `os.rename` (der würde auf POSIX ein leeres Zielverzeichnis ersetzen), sondern `FINALIZE_UNSUPPORTED`.
    - Windows: `os.rename` (MoveFileExW ohne REPLACE_EXISTING, schlägt bei existierendem Ziel fehl).
  - `EEXIST`/`ENOTEMPTY`/`FileExistsError` werden zu `NAME_CONFLICT`, sonstige `OSError` zu `IO_ERROR`. Rückgabe: neuer Pfad.
  - Nach dem Erfolg erneut `_destination_names` prüfen. Ist eine Kollision entstanden (Race auf case-sensitivem FS), sofort zurückbenennen und `NAME_CONFLICT` werfen.
- `list_destination_entries(source_root: Path, destination_folder: Path) -> tuple[DestinationEntry, ...]` mit neuem `DestinationEntry(name: str, kind: EntryKind)` in `ports/models.py`, wobei `EntryKind` = FILE / DIRECTORY / LINK / OTHER. Ermittlung per `os.scandir` und `entry.is_symlink()`/Junction-Check vor `is_dir`/`is_file`; versteckte Dateien werden mitgelistet. Containment über `_contained_destination`. `OSError` wird zu `IO_ERROR` (Review-Befund fsops #9 hier nicht wiederholen).
- `remove_empty_destination_folder(source_root: Path, exact_name: str) -> None`: dieselben Containment-, Link- und Verzeichnis-Prüfungen, dann ausschließlich `os.rmdir` (nie `shutil.rmtree`). `ENOTEMPTY`/`EEXIST` werden zu neuem Grund `FileSystemErrorReason.FOLDER_NOT_EMPTY` (Enum in `ports/errors.py:7` ergänzen), sonst `IO_ERROR`.
- Rollback: Kein eigener Port nötig. Er ruft `rename_destination_folder(source_root, new_exact, old_name)` auf; die Konfliktprüfung ignoriert dabei den umzubenennenden Ordner selbst, wie oben beschrieben.

Fakes: `tests/fakes/__init__.py`, `FaultInjectingFileSystem` (~:303) um `fail_rename`, `crash_after_rename` (wirft `SimulatedCrash` nach dem Dateisystem-Rename) und `fail_rmdir` erweitern.

### Schritt 2 – State-Store: Schema v2, Rename-Journal, Register-Updates

`src/vuechoixgarde/store/state.py`, `src/vuechoixgarde/ports/state.py`, `src/vuechoixgarde/ports/models.py`, Fake `InMemoryStateStore` (~:114):

- `_SCHEMA_VERSION = 2`. In `load()` (`state.py:~144–155`) eine Migrationskette einführen: `0→1` (bestehend) und dann `1→2`. Neue DBs durchlaufen beide. `user_version > 2` weiterhin wie bisher behandeln (Downgrade-Problem ist ein separater Review-Befund).
- Migration `_migration_1_to_2`:
  ```sql
  CREATE TABLE folder_renames (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    old_folder TEXT NOT NULL,
    new_folder TEXT NOT NULL,
    intermediate_folder TEXT,
    target_slots_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('started','done','rolled_back','recovered')),
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
  PRAGMA user_version = 2;
  ```
  `old_folder`/`new_folder`/`intermediate_folder` sind die vollständigen Pfad-Strings, **exakt so gebildet wie `CopyRecord.destination_folder` beim Kopieren**. Vor der Implementierung in `app/toggle.py` (`_toggle_on`) nachsehen, wie der String entsteht (erwartet: `str(source_root / exact_name)`), und eine gemeinsame Hilfsfunktion `destination_folder_key(source_root, exact_name) -> str` einführen, die beide Stellen nutzen.
- Neue Store-Methoden (alle mit `BEGIN IMMEDIATE` und mit `contextlib.closing` um die Verbindung, damit für neue Methoden nicht das Verbindungsleck aus dem Review entsteht):
  - `start_folder_renames(profile_id, renames: tuple[FolderRenameRecord, ...]) -> None`: legt alle Journal-Zeilen einer Speicherung in **einer** Transaktion mit `state='started'` an.
  - `complete_folder_renames(profile_id, rename_ids, folder_updates: tuple[tuple[str, str], ...], removed_folders: tuple[str, ...], slots: tuple[Slot, ...]) -> None`: in **einer** Transaktion
    1. `UPDATE copies SET destination_folder=? WHERE profile_id=? AND destination_folder=?` für jedes `(old, new)`. Vorher prüfen, dass für `new` keine Zeilen existieren, sonst `StateStoreError(INVALID_DATA)`.
    2. `DELETE FROM copies WHERE profile_id=? AND destination_folder=?` für jeden fehlenden alten Ordner (FR-100: alter Ordner existiert nicht).
    3. Slots ersetzen (Logik von `replace_profile_slots` als interne Funktion `_replace_slots(connection, ...)` herauslösen und wiederverwenden).
    4. Journal-Zeilen auf `done` setzen.
  - `mark_folder_renames_rolled_back(rename_ids)`, `mark_folder_rename_recovered(rename_id)`.
  - `unfinished_folder_renames() -> tuple[FolderRenameRecord, ...]`.
  - `remove_destination_folder_records(profile_id, destination_folder: str, slots: tuple[Slot, ...]) -> int`: in einer Transaktion alle `copies` dieses Ordners löschen und die Slots ersetzen. Rückgabe: Anzahl gelöschter Einträge.
  - `remove_copy_records(profile_id, destination_folder, names: tuple[str, ...])` für den Teilerfolg beim Löschen.
- Dataclass `FolderRenameRecord(id, profile_id, old_folder, new_folder, intermediate_folder, state, started_at, updated_at)` in `ports/models.py`.
- Vorbedingung im Service (nicht im Store): Für das Profil dürfen keine `operations` mit `state='started'` existieren (vgl. Review-Befund zu `reassign_profile`).

### Schritt 3 – Wiederherstellung unterbrochener Renames

`src/vuechoixgarde/app/recovery.py`: neue Funktion `recover_folder_renames(...)`. Sie wird an **beiden** Stellen aufgerufen, an denen `recover_operations` läuft (`app/session.py:138`, `app/service.py:381`), und zwar **vor** `recover_operations` und vor jedem Reconcile. Wichtig: Der Reconcile würde Register-Einträge eines verschwundenen alten Ordners sonst löschen.

Entscheidungstabelle pro `started`-Eintrag des geöffneten Profils (Existenz über `lstat`, Containment-Prüfungen wie in Schritt 1):

| alt | Zwischenname | neu | Aktion |
|---|---|---|---|
| ja | nein | nein | Rename hat nicht stattgefunden → `rolled_back`; Profil-Slots unverändert lassen |
| nein | nein | ja | Rename physisch erfolgt → Register und Slots nachziehen (`complete_folder_renames` mit gespeicherten Ziel-Slots, siehe unten) → `recovered` |
| nein | ja | nein | Zwischenzustand → Zwischenname zurück auf alt benennen → `rolled_back` |
| ja | ja / – | ja | inkonsistent → nichts anfassen, `recovery_pending = True`, Fehler `rename_recovery_failed` mit beiden Namen |
| nein | nein | nein | Ordner verschwunden → Register-Einträge für alt entfernen, Slot-Name bleibt → `recovered`, Warnung |

Damit „nachziehen“ möglich ist, enthält der Journal-Eintrag die Ziel-Slots in der Spalte `target_slots_json` (JSON-Liste von `{key_position, destination_name, color}`, geschrieben in `start_folder_renames`). Dadurch werden auch Änderungen an Tasten und Farben derselben Speicherung korrekt wiederhergestellt.

Solange ein Rename-Eintrag `started` bleibt, gilt `recovery_pending`. Slot-Aktionen sind dann gesperrt (bestehender Mechanismus, `session.py:245`).

### Schritt 4 – Service: Speichern mit Renames

`src/vuechoixgarde/app/service.py`:

- `save_settings_and_profile_slots(submission: SettingsSubmission)` (oder die bestehende Signatur plus `renames: tuple[FolderRename, ...] = ()`; bestehende Aufrufer in Tests anpassen). Ablauf:
  1. Bestehende Validierung, `_require_session`, `_ensure_idle`.
  2. Gibt es Renames: Abbruch mit `FolderManagementError` bei `recovery_pending`, nicht verfügbarem Register oder offenen Kopier-Operationen.
  3. **Vorprüfung aller Renames vor dem ersten Dateisystemzugriff** (FR-101):
     - `validate_folder_name(new)`.
     - `resolve_destination_folder(source_root, old)`: FAULTY führt zum Abbruch `old_folder_faulty`; NOT_FOUND wird als „fehlt“ markiert; FOUND liefert `exact_old`.
     - Belegungsprüfung gegen die Namensliste **vor** der Speicherung: `new` ist belegt, wenn ein Eintrag `e` mit `comparison_key(e) == comparison_key(new)` existiert und `e` nicht der eigene `exact_old` ist. Das gilt auch dann, wenn ein anderer Rename derselben Speicherung `e` frei machen würde (Namenstausch erfordert getrennte Speicherungen).
     - Zwei Renames mit gleichem Ziel werden bereits von `validate_slot_profile` (doppelte Namen) abgefangen. Trotzdem defensiv prüfen.
     - Bei einem Fehler wird `FolderManagementError(NAME_OCCUPIED | INVALID_NAME | OLD_FOLDER_FAULTY, old_name, new_name)` geworfen, ohne Änderung.
  4. `start_folder_renames` (Journal, inklusive `target_slots_json`).
  5. Dateisystem-Renames nacheinander. Scheitert Nummer *k*: die Renames 1..k-1 in umgekehrter Reihenfolge zurückbenennen, `mark_folder_renames_rolled_back`, Fehler werfen. Scheitert auch ein Rückbenennen, den Eintrag `started` lassen, `recovery_pending = True` setzen und die Fehlermeldung `rename_rollback_failed` ausgeben (die Wiederherstellung beim nächsten Start übernimmt).
  6. `complete_folder_renames(...)` mit allen `(old_key, new_key)`, den fehlenden alten Ordnern und den neuen Profil-Slots. Scheitert dieser DB-Schritt: Dateisystem zurückbenennen (wie 5.), dann Fehler.
  7. Erst danach `save_preferences` für die globalen Einstellungen (bestehende Logik inklusive `PartialSettingsSaveError` bleibt erhalten; Profil und Ordner sind in diesem Fall bereits konsistent).
  8. Ohne Renames: Verhalten wie bisher (`save_profile_slots` → `replace_profile_slots`).
  9. Log je Rename (FR-091): `LogEvent` ergänzen (`FOLDER_RENAMED`, `FOLDER_RENAME_FAILED`), nur Ordnernamen loggen, keine Bildnamen.
- Rückgabe: `SessionView` plus `renamed: tuple[tuple[str, str], ...]` (oder ein neues Feld im Rückgabetuple von `save()`), damit die UI die Erfolgsmeldung mit altem und neuem Namen zeigen kann.

### Schritt 5 – Service: Zielordner löschen

`src/vuechoixgarde/app/service.py` (oder neues Modul `app/folders.py`, wenn `service.py` zu groß wird; Stil wie `app/toggle.py`):

- `inspect_destination_folder(slot_index: int) -> FolderDeletionCheck`
  - Vorbedingungen wie in Schritt 4.2, dazu: Slot hat einen gespeicherten Namen.
  - `resolve_destination_folder`: NOT_FOUND ergibt `MISSING`, FAULTY ergibt `FAULTY`.
  - Bei FOUND: `list_destination_entries` und `state.copy_records(profile_id, folder_key)`. Für jeden Eintrag:
    - `FILE` mit Register-Eintrag, dessen `fingerprint_file` Größe und SHA-256 trifft: verifizierte Kopie.
    - alles andere ist ein fremder Eintrag: Datei ohne Eintrag, geänderte Kopie, Verzeichnis, Link, OTHER, versteckte Datei.
  - Ergebnis `FolderDeletionCheck(case: DELETABLE | FOREIGN_ENTRIES | MISSING | FAULTY, folder_name, managed_names: tuple[str,...], foreign_names: tuple[str,...], fingerprint: str)`. `fingerprint` ist ein Hash über die sortierte Liste `(name, kind, size, sha256)` und dient als Bestätigungs-Token.
  - Register-Einträge zu nicht mehr existierenden Dateien zählen weder als Kopie noch als fremd; sie werden beim Ausführen mit entfernt.
- `delete_destination_folder(slot_index: int, confirmed: FolderDeletionCheck) -> FolderDeletionResult`
  - Erneut `inspect_destination_folder`. Weichen `case` oder `fingerprint` ab, wird **nichts** getan und Status `CHECK_CHANGED` mit neuem Check zurückgegeben. Die UI fragt dann erneut. (Lehre aus Review-Befund H4: Eine Bestätigung gilt nur für den angezeigten Stand.)
  - `DELETABLE`: Für jede Kopie `delete_verified_file(..., record.size, record.sha256)` (prüft unmittelbar vor dem Löschen erneut). Danach `remove_empty_destination_folder`. Dann `remove_destination_folder_records(profile_id, folder_key, slots_mit_name_None)` → Ergebnis `DELETED`.
  - Teilfehler (eine Löschung scheitert oder `FOLDER_NOT_EMPTY`): `remove_copy_records` nur für die bereits gelöschten Kopien, Slot-Name bleibt, Ergebnis `PARTIAL` mit Fehlercode (FR-104).
  - `FOREIGN_ENTRIES` / `FAULTY`: **keine** Dateisystem-Schreiboperation. `remove_destination_folder_records(...)` → Ergebnis `DETACHED` mit Warnschlüssel und `foreign_names`.
  - `MISSING`: `remove_destination_folder_records(...)` → `REMOVED_INFO`.
  - Slots ohne Namen: `dataclasses.replace(slot, destination_name=None)` für den betroffenen Index, sonst unverändert.
  - Log-Ereignisse `FOLDER_DELETED`, `FOLDER_DETACHED`, `FOLDER_DELETE_FAILED` (nur Ordnername und Anzahlen).
  - `_ensure_idle` und das bestehende `OperationGate` nutzen (FR-051).

### Schritt 6 – UI

`src/vuechoixgarde/ui/settings_dialog.py`, `src/vuechoixgarde/ui/main_window.py`:

- `_SlotEditor`: `origin_name` je Zeile (Entscheidung 1). Methode `renames() -> tuple[FolderRename, ...]`.
- Nur im Editor `"profile"`: je Zeile ein Knopf „Zielordner löschen…“ (zugängliche Beschriftung inklusive Slot-Taste, FR-08x Accessibility; Tab-Reihenfolge prüfen).
  - Aktiv nur, wenn: `origin_name is not None`, aktueller Name == `origin_name`, Editor nicht read-only und keine Operation läuft.
  - Bei jeder Textänderung neu bewerten.
- `SettingsDialog._save`: `SettingsSubmission` im UI-Thread bauen (H1). Den Speichern-Knopf und die Profil-Aktionen bis zum Ergebnis deaktivieren (Review-Befund N4, betrifft denselben Fluss).
- `main_window.save_preferences`: Der Worker bekommt nur die Submission. Fehlerbehandlung:
  - `FolderManagementError` → i18n-Text mit `{old}`/`{new}`, Dialog bleibt offen (bestehender Fehlerpfad).
  - Erfolg mit Renames → Statusmeldung `destination_folder_renamed`.
- Löschen-Ablauf:
  1. Klick → `inspect` im Datei-Worker.
  2. Ergebnis im UI-Thread → `QMessageBox`:
     - Icon: Question; bei FOREIGN/FAULTY: Warning.
     - Buttons: Yes (Text je Fall: „Löschen“ / „Nur Zuordnung entfernen“) und Cancel.
     - `setDefaultButton(Cancel)`, `setEscapeButton(Cancel)`.
     - `informativeText` nach FR-103: Anzahl der Kopien; bei fremden Einträgen die Anzahl und die ersten 10 Namen sichtbar (nicht nur in `detailedText`, vgl. Review-Befund M1).
  3. Yes → `delete_destination_folder` im Worker. Bei `CHECK_CHANGED` erneut fragen.
  4. Ergebnis:
     - `DELETED` / `REMOVED_INFO`: Statusmeldung.
     - `DETACHED`: modale Warnung (`QMessageBox.warning`) mit dem Hinweis zum manuellen Löschen.
     - `PARTIAL`: Fehlerdialog.
     - Danach den Profil-Editor des Dialogs aus der neuen `SessionView` neu befüllen (Name leer) und die Hauptansicht aktualisieren (`_apply_view`).
- Die bisherige Warnung `destination_renamed` umbenennen in `destination_unassigned` und den Text korrigieren (z. B. de: „Der Ordner „{name}“ ist keinem Slot mehr zugeordnet; vorhandene Kopien bleiben dort.“). Das betrifft `service.py:~238–245`, alle drei Kataloge und den Test `tests/integration/test_phase6_service.py:42` (umbenennen und an den neuen Ablauf anpassen: Ein Rename über `renames` verschiebt jetzt physisch; die alte Situation entsteht nur noch durch Entfernen/Zurücksetzen).

### Schritt 7 – i18n

`src/vuechoixgarde/i18n/de.json`, `en.json`, `fr.json`: identische Schlüssel in allen drei Dateien. `tests/unit/test_i18n_catalogs.py` muss grün bleiben. Neue Schlüssel (Texte frei formulieren, Platzhalter genau so):

- `destination_folder_renamed` – „Zielordner „{old}“ wurde in „{new}“ umbenannt.“
- `rename_name_occupied` – „„{new}“ existiert bereits im Quellordner. „{old}“ wurde nicht umbenannt.“
- `rename_old_faulty` – „Der Zielordner „{old}“ ist fehlerhaft und kann nicht umbenannt werden.“
- `rename_failed` – „„{old}“ konnte nicht in „{new}“ umbenannt werden. Es wurde nichts geändert.“
- `rename_rollback_failed` – „Die Umbenennung konnte nicht vollständig zurückgenommen werden. Sie wird beim nächsten Öffnen des Ordners abgeschlossen.“
- `rename_recovery_failed` – „Ordner „{old}“ und „{new}“ existieren beide; die unterbrochene Umbenennung wurde nicht fortgesetzt.“
- `rename_unavailable` – „Umbenennen ist gerade nicht möglich (Wiederherstellung offen oder Kopierregister nicht verfügbar).“
- `delete_folder_button`, `delete_folder_title`
- `delete_folder_confirm_deletable` – mit {name} und {count}, Hinweis „endgültig, nicht in den Papierkorb“
- `delete_folder_confirm_foreign` – mit {name}, {count}, {names}: Ordner bleibt, Verwaltung wird beendet
- `delete_folder_confirm_missing`
- `delete_folder_yes_delete`, `delete_folder_yes_detach`
- `delete_folder_done`, `delete_folder_info_removed`
- `delete_folder_foreign_warning` – „Der Ordner „{name}“ enthält unbekannte Dateien und wurde deshalb nicht gelöscht. Bitte lösche ihn bei Bedarf manuell. Dateien darin werden nicht mehr verwaltet.“
- `delete_folder_partial`, `delete_folder_failed`, `delete_folder_check_changed`
- `destination_unassigned` (ersetzt `destination_renamed`)

### Schritt 8 – Tests

Neue Testmodule; Muster aus `tests/integration/test_phase6_service.py:42–69` und `tests/ui/test_phase6_ui_flows.py:28–64` übernehmen. In jedem Integrationstest `source_guard` (`tests/integration/conftest.py:55`) mit `seal(allowed_destinations={...})` verwenden und `runtime.shutdown()` im `finally` aufrufen (auch `save_preferences` innerhalb des `try`).

- `tests/unit/test_folder_management.py`: Rename-Vorprüfung (belegt; Groß-/Kleinschreibung; NFC/NFD; Namenstausch wird abgelehnt; mehrere Renames), Klassifikation für das Löschen (leer, nur verifiziert, geänderte Kopie, fremde Datei, versteckte Datei, Unterordner, Symlink), Token-Vergleich.
- `tests/integration/test_folder_rename.py`:
  - Umbenennen verschiebt den Ordner, Bytes sind identisch, `slot_status` und Zähler zeigen die Bilder weiter als ausgewählt (AK 21).
  - Toggle-off nach dem Umbenennen löscht im neuen Ordner.
  - Ziel belegt durch Ordner bzw. Datei, auch nur in anderer Schreibweise → Fehler, alles unverändert (Dateien, Register, Slots).
  - Nur Schreibweise geändert → angewendet.
  - Alter Ordner fehlt → nur der Name ändert sich, kein Ordner wird angelegt.
  - Alter Ordner ist ein Symlink → Fehler.
  - Zwei Renames, der zweite scheitert (`fail_rename`) → der erste ist zurückgenommen.
  - `crash_after_rename` → neue Runtime öffnen → konsistent (AK 22); alle Zeilen der Tabelle in Schritt 3.
  - Recovery-Pending sperrt das Umbenennen.
- `tests/integration/test_folder_delete.py`:
  - Fall DELETABLE: Ordner und Register-Einträge sind weg, der Slot hat keinen Namen mehr.
  - Leerer Ordner.
  - FOREIGN_ENTRIES mit fremder Datei, `.DS_Store`, geänderter Kopie und Unterordner: alles physisch unverändert (per Hash geprüft), Register leer, Slot ohne Namen, Warnung (AK 24).
  - MISSING, FAULTY.
  - Ein Eintrag erscheint zwischen Prüfung und Ausführung → `CHECK_CHANGED`, nichts gelöscht.
  - `fail_rmdir` → `PARTIAL`.
  - Ein anderer Unterordner und die Dateien im Quellordner bleiben unverändert.
- `tests/integration/test_store.py`: Migration v1→v2 auf einer v1-Datenbank (Fixture per `_migration_0_to_1` erzeugen), `complete_folder_renames` ist atomar (Fehler in der Mitte → Rollback), PK-Konflikt wird erkannt.
- `tests/ui/test_folder_management_ui.py`:
  - Der Löschen-Knopf ist nur bei gespeichertem, unverändertem Namen aktiv.
  - Dialog: Default ist Cancel, verglichen über die Button-Rolle `dialog.defaultButton() == dialog.button(Cancel)`, nicht über den Text. `Esc` bricht ab und ändert nichts (AK 23).
  - Fremde Namen stehen im `informativeText`.
  - Rename-Fehler hält den Einstellungsdialog offen.
  - `save()` liest keine Widgets im Worker: Test, der `SettingsSubmission` prüft.
- Bestehende Tests an geänderte Signaturen anpassen. Keine Tests löschen, die weiterhin gültige Anforderungen prüfen.

### Schritt 9 – Dokumentation

- `docs/user-guide.md`: Abschnitt „Zielordner umbenennen und löschen“ (Verhalten, Grenzen, Hinweis „endgültig, kein Papierkorb“, manuelles Löschen bei fremden Dateien).
- `docs/technical-design.md`: neue Port-Methoden, Schema v2 und `folder_renames`, Wiederherstellungstabelle, H1-Regel „Worker bekommen nur Wertobjekte“.
- `docs/manual-test-plan.md`: Fälle für AK 21–24 inklusive Windows (Ordner im Explorer geöffnet → Rename scheitert sauber) und macOS (APFS, nur Groß-/Kleinschreibung geändert).
- `docs/known-limitations.md`: Ein Namenstausch braucht zwei Speicherungen. Ein Dateisystem ohne No-Replace-Rename (z. B. manche Netzlaufwerke unter Linux) kann nicht umbenennen.
- `CHANGELOG.md`: Eintrag unter „Unreleased“.

## 3. Abnahme

Im Projektordner ausführen; alle Befehle müssen erfolgreich sein:

```
uv sync --locked
uv run ruff format --check
uv run ruff check
uv run pyright
QT_QPA_PLATFORM=offscreen uv run pytest -q
```

Zusätzlich: Die Akzeptanzkriterien 21–24 aus `docs/requirements.md` sind je durch mindestens einen automatisierten Test abgedeckt (Testnamen im Abschlussbericht nennen). `git diff --stat` enthält keine Änderung an `docs/requirements.md`.

## 4. Nicht Teil dieses Plans

Die übrigen Befunde des Reviews (`.deutschlandgpt/reviews/2026-10-21-final-review.md`) werden separat umgesetzt. Ausnahmen: H1 und N4, weil derselbe Code umgebaut wird. Zähler auf konfigurierte Ordner beschränken (H3, zweiter Teil) nur dann, wenn es für die Tests aus AK 21 nötig ist.
