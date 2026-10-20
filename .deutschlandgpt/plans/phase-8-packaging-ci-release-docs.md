# Phase 8 – Packaging, CI/Releases, Dokumentation, Abnahme (finale Phase)

## Context

Phasen 1–7 sind implementiert. Phase 8 macht daraus ein auslieferbares Produkt: PyInstaller-Builds (One-Folder) für
Linux/Windows/macOS (arm64), GitHub-Actions-CI und -Releases, Lizenz-/Third-Party-Prüfung, Dokumentation (NFR-032) und ein
Abnahme-/Plattformtestplan gegen die Abnahmekriterien 1–19 der SRS.

Vorgaben aus `docs/technical-design.md`: Abschnitt 12 (Packaging, One-Folder, LGPL), Abschnitt 11 (CI: `uv sync --locked`,
`ruff format --check`, `ruff check`, `pyright`, `pytest` mit Qt offscreen), Releases aus Tags, **ungesignierte** Builds
(SRS 3.2). Kein Netzwerkzugriff der App (NFR-005), auch nicht im Bundle (kein QtNetwork).

### Entscheidungen des Nutzers (final)
1. **Projektlizenz:** egal, Hauptsache kompatibel mit Projekt und Bibliotheken → **MIT** (verträglich mit PySide6/LGPL bei dynamischem
   Linken im One-Folder-Build, Pillow HPND, pi-heif BSD-3 mit LGPL-Native-Libs, filelock/platformdirs). Copyright-Zeile
   „VueChoixGarde contributors“; Inhaber-Name kann der Nutzer im Review ändern. `pyproject.toml`: `license`-Feld ergänzen
   (derzeit nicht gesetzt).
2. **macOS-Intel-Build:** nicht nötig → nur `macos-latest` (arm64); in `known-limitations.md` vermerkt.
3. **Sound im Bundle:** grundsätzlich ja (QtMultimedia mitbündeln). Zuwachs wird gemessen und dokumentiert. Nur wenn er
   „wirklich sehr viel“ ausmacht, wird **nicht stillschweigend** gekürzt: ich lege dann die gemessenen Zahlen vor und frage nach.
   Bis dahin gilt: Sound bleibt drin.
4. **Dokumentation:** alles im Repo bleibt **Englisch** (README, Docs, CHANGELOG, Notices). Keine DE/FR-Dokumente.
   (Die App-UI bleibt de/en/fr.)

## A. Review Phase 7 (per Codelektüre; im Plan-Modus keine Läufe)

Handoff nennt 330 bestanden / 1 übersprungen – nicht von mir verifiziert. `app` blieb Qt-frei.

### Fehler (vor Phase 8 beheben)
1. **Hilfetext zeigt wörtlich `\n`:** `i18n/{en,de,fr}.json` (`help_shortcuts`) und `ui/texts.py:93-95` enthalten `\\n`
   (doppelt maskiert). Fix + Test auf echte Zeilenumbrüche.
2. **DE/FR teilweise unübersetzt** (`selected_accessible`, `invalid_captured_key`, `color_contrast_warning`, `slot_invalid_key`,
   `help_shortcuts`, vermutlich `help_behavior`, `help_slot_accessible` u. a.). Paritätstest prüft nur Schlüssel/Platzhalter.
   Fix: übersetzen; Test „Wert in de/fr == en ⇒ Schlüssel in expliziter Allowlist“. Terminologie: DE „Slot/Zielordner“, FR „emplacement/destination“.

### Wichtige Befunde
3. Legacy-Dict `TEXTS` in `ui/texts.py` entfernen; `en.json` einzige Quelle; Test `test_catalog_keys_match_legacy_text_source`
   ersetzen durch „alle verwendeten Schlüssel existieren“.
4. `ui/sound.py`: Pfad per `__file__` → `importlib.resources.as_file`; `QSoundEffect` wirft keine Exceptions, Fehler über
   `status()/statusChanged` erkennen und einmalig loggen (ohne Pfade); Effekt hinter schmalem Protocol/Factory für Tests.
5. Fehlende Tests: F1/FR-084-Guard, Live-Sprachwechsel, Sound-Gating (nur nach erfolgreichem Hinzufügen und `sound_enabled`),
   Accessible Names, Kontrastmatrix (NFR-022, ≥ 4.5:1), 12-Slot-Layout bei Mindestgröße, Eliding/Tooltips.
6. `HelpDialog`: kein Schließen-Button, `parent` untypisiert, Slot-Zeilen mit Hex-Farbwert statt Taste + Name (+ Zustand).
7. `_retranslate` ohne geöffneten Ordner nur teilweise (Platzhalter, Tooltips, Accessible Names).
8. Qt-Übersetzer (`_load_qt_translation`) nutzt `QLibraryInfo.TranslationsPath` – im Bundle fehlt/ändert sich der Pfad; Fallback darf nur
   zum englischen Standarddialog führen.
9. Handoff Abschnitt 14 auf „abgeschlossen“ aktualisieren.

Offen/manuell: Tastaturtests (X11/Wayland/Windows/macOS; QWERTZ/AZERTY; AltGr; Totasten), echte HEIC-Dateien, Dead-Key-Labels;
prüfen, ob `activeModalWidget()/activePopupWidget()` im FR-084-Guard umgesetzt ist, sonst nachziehen.

## B. Phase 8.0 – Pflicht-Fixes vor Packaging

Dateien: `src/vuechoixgarde/i18n/{de,en,fr}.json`, `ui/texts.py`, `ui/sound.py`, `ui/help_dialog.py`, `ui/main_window.py`,
`ui/style.py`; Tests: `tests/unit/test_i18n_catalogs.py`, neu `tests/ui/test_help_language_sound.py`, `tests/unit/test_contrast.py`,
`tests/ui/test_accessibility.py`.

1. A.1–A.3 umsetzen.
2. Sound-Härtung (A.4) mit Fake-Effect-Tests.
3. Hilfe: Schließen-Button, Typen, Slot-Zeilen ohne Farbwert; Tests für F1/Guard, Echt-Zeilenumbrüche, Nicht-US-Layout-Hinweis in 3 Sprachen.
4. `_retranslate` vollständig, auch ohne Ordner; Test de→fr→en mit und ohne Ordner.
5. Kontrasttest (WCAG-Luminanz) über `style.py`-Paare und Standard-Slot-Palette; durchgefallene Paare anpassen.
6. 12-Slot-Layout-Test bei Mindestgröße in DE/EN/FR.
7. Grün: `uv run ruff format --check`, `ruff check`, `pyright`, `pytest -q`.

## C. Phase 8 – Umfang

### C1. Einstiegspunkt, Version, Smoke-Test
- `packaging/entry.py` (dünner Start über `vuechoixgarde.__main__.main`).
- Versionsquelle `pyproject.toml`; Laufzeit `importlib.metadata.version`; im Spec `copy_metadata("vuechoixgarde")`.
- `--smoke-test`: temporäres App-Data-Verzeichnis, Runtime + Hauptfenster (offscreen erlaubt), alle drei Kataloge laden, WAV auflösen,
  Pillow-Decoding eines in-memory JPEG, `pi_heif`-Registrierung nur als Information, Exit 0/1, Ergebnis zusätzlich in Logdatei
  (Windows windowed hat kein stdout). Kein Netzwerk. Unit-Test der Exit-Codes.

### C2. PyInstaller-Spec `packaging/vuechoixgarde.spec`
- One-Folder, windowed. `datas`: i18n-JSONs, `resources/` (QSS, `sounds/added.wav`, README), `copy_metadata`.
- Hooks/Hidden Imports für `pi_heif` (native Libs prüfen) und PIL-Plugins.
- Qt schlank: QtCore/Gui/Widgets/**Multimedia**; `excludes`: QtNetwork, QtQml/Quick, WebEngine, Pdf, Svg u. ä. Bundle-Scan: kein `Qt6Network`.
  Multimedia-Backend je Plattform mitbündeln. **Größe mit/ohne Multimedia messen und in `docs/` dokumentieren**; Sound bleibt drin
  (Nutzerentscheidung 3), außer die Zahlen sind extrem – dann Rückfrage.
- Qt-Übersetzungen `qtbase_de/fr.qm` bündeln; `_load_qt_translation` auf Bundle-Pfad (`sys._MEIPASS`) ausrichten, Fallback ohne Fehler.
- Windows `.exe` mit Versionsinfo; macOS `.app` (Bundle-ID, `NSHighResolutionCapable`), ungesigniert; Linux Ordner + `.tar.gz`.
  Icon: selbst erzeugt (Skript in `tools/`), unter MIT.
- Build: `uv run pyinstaller packaging/vuechoixgarde.spec --noconfirm`; `build/`, `dist/` in `.gitignore`; vorhandene `dist/*.whl` nicht anfassen.
- PyInstaller als Dev-Dependency (Gruppe `build`) in `pyproject.toml`, `uv.lock` aktualisieren (`uv lock`).

### C3. Lizenzen & Rechtliches
- `LICENSE` (MIT), `pyproject.toml` `license`.
- `THIRD_PARTY_NOTICES.md` via `tools/generate_third_party_notices.py` (`importlib.metadata`) + geprüfte Zusätze für native Libs:
  Qt/PySide6 LGPL-3.0, libheif/libde265 LGPL, Pillow HPND, filelock, platformdirs, Python PSF, CC0-Sound. LGPL: Hinweis, Lizenztext,
  Austauschbarkeit der Qt-Bibliotheken (One-Folder).
- CI-Schritt: Bundle nach `x265` durchsuchen, Fund = Fehler (Entscheidung `pi-heif`).
- HEVC-Patenthinweis in der Doku, ausdrücklich kein Rechtsrat.

### C4. CI `.github/workflows/ci.yml`
- Trigger `push` auf `main`, `pull_request`. Matrix: `ubuntu-latest`, `windows-latest`, `macos-latest` (arm64). Kein Intel-Runner.
- Schritte: checkout, `astral-sh/setup-uv` (gepinnt, Cache), `uv sync --locked`, ruff format --check, ruff check, pyright,
  `pytest -q` mit `QT_QPA_PLATFORM=offscreen`. Linux: nötige Systempakete (z. B. `libegl1`, `libgl1`, `libxkbcommon0`, `libdbus-1-3`,
  `libxcb-cursor0`, `libpulse0`) durch Lauf ermitteln.
- Actions auf Commit-SHA pinnen; `permissions: contents: read`; `concurrency`; keine Secrets.
- Windows/macOS-Fehler in Fsops-Tests sind echte Befunde und werden gefixt oder als Lücke dokumentiert.

### C5. Release `.github/workflows/release.yml`
- Trigger Tag `v*.*.*` (Tag == `pyproject`-Version prüfen) und `workflow_dispatch` für Probe-Builds (nur Artifacts).
- Je OS: Sync, Build, `--smoke-test` am Artefakt, Bundle-Checks (kein QtNetwork, kein x265), Archiv
  `VueChoixGarde-<version>-<os>-<arch>.<zip|tar.gz>` (macOS via `ditto`).
- Job `publish` (nur dieser mit `contents: write`): `SHA256SUMS.txt`, `gh release create --draft --generate-notes`. Kein Auto-Publish, kein Signieren.

### C6. Dokumentation (alles Englisch)
- `README.md` (Root): Zweck, Funktionen, Download, Schnellstart, Plattform-/Formatmatrix, Lizenz.
- `docs/user-guide.md`: Installation je Plattform inkl. SmartScreen/Gatekeeper/`chmod +x`, Ablauf, Slots/Profile/Vorlagen, Shortcuts,
  Einstellungen, Sprache/Ton, Logs, Recovery/Reconcile, Nicht-US-Layout-Einschränkung (FR-081/086), Barrierefreiheit.
- `docs/supported-formats.md` (FR-004, HEIC je Plattform nach Prüfung, Sidecars FR-043), `docs/known-limitations.md`
  (Dead-Key-Labels, ungesignierte Builds, kein macOS-Intel-Build, FR-071 zurückgestellt, Pfadlängen, Wayland nach Test),
  `docs/development.md`, `docs/manual-test-plan.md` (Plattform × Prüfpunkt, Traceability Kriterien 1–19), `CHANGELOG.md` (0.1.0).
- `docs/keyboard-test-checklist.md`: Ergebnisse leer lassen, nur der Nutzer füllt sie auf echter Hardware.
- `technical-design.md` nur bei tatsächlicher Abweichung anpassen (mit Vermerk); `.deutschlandgpt/handoff.md` aktualisieren.

### C7. Abschluss-Qualitätsdurchlauf
- Lokal (Linux): Ruff, pyright, pytest, Build, Smoke-Test, Offscreen-Screenshots DE/EN/FR, Bundle-Inhalt/-Größe.
- Performance-Stichprobe NFR-010/011 (10.000 generierte Bilder) nur informativ dokumentieren.
- Prüfen: Bundle schreibt nur in Quell-/App-Data-Ordner (NFR-001/002), Smoke-Test im schreibgeschützten Installationsordner.

## D. Reihenfolge, Verifikation, Risiken

Reihenfolge: B → C1 → C2 (Linux-Build) → C3 → C4 → C5 → C6 → C7. Commit-Vorschläge nach B und nach C2; committen nur auf Wunsch,
nie pushen/taggen ohne ausdrückliche Anweisung.

Verifikation: `uv sync --locked`, ruff format --check, ruff check, pyright, `pytest -q` (Basis 330/1 laut Handoff, keine Regression),
`uv run pyinstaller packaging/vuechoixgarde.spec`, `dist/VueChoixGarde/VueChoixGarde --smoke-test` (Exit 0), Bundle-Scan.
Windows/macOS lokal nicht prüfbar → nur per CI, ehrlich als „lokal ungetestet“ berichten.

Risiken: unvollständige Bündelung von `pi-heif`/Multimedia-Plugins (Smoke-Test deckt Decoding und Sound-Auflösung ab); Paketgröße;
Warnungen bei ungesignierten Builds (nur Doku); macOS-Scancodes und Wayland ohne Hardware ungeprüft; Release-Workflows mit minimalen Rechten.
