# Phase 8 – Korrektur: QtNetwork als QtMultimedia-Abhängigkeit zulassen (Variante 1)

## Context

Der Linux-Build wurde erzeugt, aber `--smoke-test` scheitert beim Start: `PySide6.QtMultimedia` importiert auf Modulebene
`PySide6.QtNetwork` (PyInstaller-Warnung in `build/pyinstaller/vuechoixgarde/warn-vuechoixgarde.txt:34`: „excluded module named
PySide6.QtNetwork – imported by … PySide6.QtMultimedia (top-level)“). `packaging/vuechoixgarde.spec` schließt die Bindings aber aus
(`_excludes`, Zeile 68), und die native `libQt6Network.so.6` landet trotzdem im Bundle (`COLLECT-00.toc:65`).

Entscheidung: **Sound bleibt** (ursprüngliche Nutzerentscheidung 3). Das Bundle enthält QtNetwork **nur als technische Abhängigkeit von
QtMultimedia**. NFR-005 („darf keine Bilder, Metadaten, Einstellungen oder Logs über das Netzwerk senden“, `docs/requirements.md:229`) bleibt
unverändert gültig und wird weiter durch Code-Regeln abgesichert, nicht durch Abwesenheit einer Bibliothek.
Die frühere Vorgabe „QtNetwork gar nicht im Bundle“ war strenger als die Anforderung und wird bewusst aufgegeben.

## Ist-Zustand (gelesen)

- `pyproject.toml`: Ruff TID251 verbietet bereits `PySide6.QtNetwork`, `socket`, `urllib`, `http`, `ssl`, `requests` u. a. in **allem** Quellcode.
  Das bleibt unverändert und ist die eigentliche NFR-005-Absicherung.
- `packaging/vuechoixgarde.spec`: `_excludes` enthält `PySide6.QtNetwork`; `_hiddenimports` enthält `PySide6.QtMultimedia`.
- `tools/check_bundle.py`: `_FORBIDDEN = (b"qt6network", b"qt5network", b"x265")`; prüft Dateinamen **und** Binärinhalt. Mit QtMultimedia im
  Bundle würden Dateiname (`libQt6Network.so.6`) und Inhalte (z. B. `libQt6Multimedia` referenziert Network) immer treffen.
- `tests/unit/test_bundle_check.py`: erwartet Exit 1 bei `Qt6Network.dll`.
- Textstellen, die QtNetwork als ausgeschlossen beschreiben: `docs/technical-design.md:430` (und :389 listet `PySide6.QtNetwork` korrekt als
  *Code*-Verbot), `docs/development.md:39`, `THIRD_PARTY_NOTICES.md:32-34` (**wird von `tools/generate_third_party_notices.py` erzeugt –
  dort ändern, nicht die Ausgabe von Hand**), `.github/workflows/release.yml:65-66` (nur Aufruf, bleibt).
- `ui/sound.py` nutzt `QSoundEffect`; Smoke-Test in `packaging/entry.py` baut `MainWindow` (und damit vermutlich `SoundPlayer`).

## Geänderte / neue Dateien

1. `packaging/vuechoixgarde.spec`
2. `tools/check_bundle.py`
3. `tests/unit/test_bundle_check.py` (erweitern)
4. neu `tests/unit/test_no_network_imports.py`
5. `packaging/entry.py` (Smoke-Test schärfen)
6. `tools/generate_third_party_notices.py` (Textblock), danach `THIRD_PARTY_NOTICES.md` neu erzeugen
7. `docs/technical-design.md` (Abschnitt 12, Zeile ~430), `docs/development.md` (Zeile 39), `docs/known-limitations.md`
8. neu `docs/adr/0002-qtnetwork-as-qtmultimedia-dependency.md`
9. `.deutschlandgpt/handoff.md` (Phase-8-Stand, Abweichung)

## Schritte

### 1. Spec: QtNetwork zulassen, TLS/OpenSSL fernhalten
- `"PySide6.QtNetwork"` aus `_excludes` entfernen; stattdessen in `_hiddenimports` aufnehmen (damit der Import von QtMultimedia
  zuverlässig aufgelöst wird). Alle übrigen Excludes (QtQml/Quick, WebEngine, Pdf, Svg, OpenGL, Sql, Test) bleiben.
- Der PyInstaller-Hook `hook-PySide6.QtNetwork.py` ruft `collect_qtnetwork_files()` auf und kann OpenSSL-Bibliotheken
  (`libssl`, `libcrypto`, Windows `libssl-*.dll`, macOS dylibs) sowie Qt-TLS-Plugins mitziehen. Die App braucht kein TLS.
  Nach der Analyse `_analysis.binaries` und `_analysis.datas` filtern: Einträge entfernen, deren Zielpfad/Name auf
  `libssl`, `libcrypto`, `/plugins/tls/`, `qopensslbackend`, `qcertonlybackend`, `networkinformation`/`libqnetworklistmanager` passt.
  Erst nach einem Build **prüfen**, was tatsächlich im Bundle liegt (Build-Ausgabe/`COLLECT-00.toc`), und nur filtern, was vorhanden ist;
  danach muss `--smoke-test` weiterhin grün sein. Falls ein Filter den Start bricht, Filter für diesen Eintrag zurücknehmen und in der
  Doku als bekannte Abhängigkeit festhalten (Befund melden, nicht raten).
- Build: `uv run pyinstaller --clean --noconfirm --distpath dist --workpath build/pyinstaller packaging/vuechoixgarde.spec`.

### 2. `tools/check_bundle.py`: von „Verbot“ zu „Allowlist mit Begründung“
- Dateiname-Prüfung statt Inhaltsprüfung für Qt-Module (Inhalts-Scan würde nach der Änderung zwangsläufig überall treffen).
  Namensmuster (case-insensitive, deckt `libQt6Network.so.6`, `Qt6Network.dll`, `QtNetwork.framework/…`, `QtNetwork.abi3.so`):
  - **erlaubt, wenn QtMultimedia im selben Bundle ist:** `qt6network`, `qtnetwork`. Ausgabe: `Allowed (QtMultimedia dependency): <Pfad>`.
    Ist Network vorhanden, aber **keine** Multimedia-Datei (`qt6multimedia`/`qtmultimedia`) → Fehler („unexplained QtNetwork“).
  - **verboten (Fehler):** weitere Netzwerk-/Web-Module: `qt6websockets`, `qt6httpserver`, `qt6networkauth`, `qt6webengine`, `qt6webchannel`,
    `qt6webview`, `qt6qml`/`qt6quick` (letztere ohnehin per Excludes draußen; hier als Regression-Schutz), sowie TLS/OpenSSL:
    `libssl`, `libcrypto`, `ssleay`/`libssl-*.dll`, Pfade mit `/plugins/tls/`, `qopensslbackend`.
  - **weiterhin verboten:** `x265` (Name **und** Binärinhalt wie bisher; der Inhalts-Scan wird auf `x265` beschränkt).
- Ausgabe am Ende: `Bundle scan passed (<n> files; QtNetwork only as QtMultimedia dependency; no TLS; no x265).`
- Markerlisten als benannte Konstanten (`_ALLOWED_WITH_MULTIMEDIA`, `_FORBIDDEN_NAMES`, `_FORBIDDEN_CONTENT`), keine Dopplungen.
- Hinweis: macOS-`.app` hat Qt unter `Contents/Frameworks`/`Resources`; `rglob` findet beides, Symlinks werden wie bisher übersprungen
  (bei Symlink-only-Treffern reicht der echte Dateiname).

### 3. Tests
- `tests/unit/test_bundle_check.py` anpassen/erweitern (Subprozess wie bisher, `tmp_path`-Fixtures):
  1. Doku-Erwähnung ignoriert (bleibt).
  2. `Qt6Network.dll` + `Qt6Multimedia.dll` → Exit 0, Ausgabe enthält „QtMultimedia dependency“.
  3. `Qt6Network.dll` allein → Exit 1.
  4. `libssl.so.3` / `plugins/tls/libqopensslbackend.so` neben Network+Multimedia → Exit 1.
  5. `Qt6WebSockets.dll` → Exit 1.
  6. Binärdatei mit `x265` → Exit 1 (bleibt).
- Neu `tests/unit/test_no_network_imports.py`: AST-Scan über `src/`, `packaging/`, `tools/` – kein `import`/`from … import` von `PySide6.QtNetwork`
  (auch `from PySide6 import QtNetwork`), `socket`, `urllib`, `http`, `ssl`, `ftplib`, `smtplib`, `requests`, `httpx`, `aiohttp`; zusätzlich kein
  String-Literal `"PySide6.QtNetwork"` in `importlib.import_module`-Aufrufen. Dokumentierte Ausnahme: `tools/check_bundle.py` darf den Namen als
  *String* enthalten (Imports werden geprüft, nicht Strings). Ruff TID251 bleibt die erste Verteidigungslinie; der Test fängt Umgehungen
  (z. B. `from PySide6 import QtNetwork`, falls Ruff das nicht erfasst – im Zweifel erst mit temporärer Probe-Datei verifizieren).
- Bestehender Sound-Test (`SoundPlayer` mit Fake-Effect) bleibt unverändert.

### 4. Smoke-Test schärfen (`packaging/entry.py`)
- Zusätzlich zu `MainWindow` ausdrücklich `from vuechoixgarde.ui.sound import SoundPlayer` importieren und `SoundPlayer(window)` erzeugen
  (echtes `QSoundEffect`), damit genau dieser Fehlerfall (fehlende Bindings/Backend-Plugins) den Smoke-Test brechen würde. `play_added()` nicht
  aufrufen (kein Ton in CI/offscreen); ein `Error`-Status des Effekts wegen fehlender Audiogeräte gilt **nicht** als Smoke-Fehler, weil
  `SoundPlayer` ihn bereits best-effort loggt.
- Optional als Information in der Logzeile: `multimedia_backend_loaded=true`.

### 5. Dokumentation & Notices (alles Englisch)
- `docs/technical-design.md` Z. 430: „QtMultimedia is retained for optional WAV feedback. QtNetwork is bundled only because QtMultimedia
  imports it; application code never imports or uses it (enforced by Ruff TID251 and an AST test). TLS/OpenSSL components are not shipped.
  QtQML/QtQuick, QtWebEngine, QtPdf, QtSvg, QtOpenGL and QtSql remain excluded. Release builds scan the bundle: unexplained network modules,
  TLS components and x265 fail the build.“ Z. 389 unverändert.
- `docs/development.md` Z. 39: neuen Prüfumfang beschreiben (Allowlist, TLS-Verbot, x265).
- `tools/generate_third_party_notices.py`: Absatz „The bundle scan rejects QtNetwork and x265 files…“ ersetzen durch: QtNetwork ist als
  QtMultimedia-Abhängigkeit enthalten, die Anwendung baut keine Netzwerkverbindungen auf, TLS wird nicht ausgeliefert, x265 darf nicht enthalten sein.
  Dann `uv run python tools/generate_third_party_notices.py` und Diff von `THIRD_PARTY_NOTICES.md` prüfen (nur dieser Absatz soll sich ändern).
- `docs/known-limitations.md`: Eintrag „QtNetwork library present in bundle“ mit Begründung und Hinweis, dass die App keine Sockets öffnet.
- Neu `docs/adr/0002-qtnetwork-as-qtmultimedia-dependency.md`: Kontext (Smoke-Test-Fehler), Optionen (1: mitliefern, 2: Sound entfernen,
  3: externe Player/`winsound`, 4: Zwei-Varianten-Build), Entscheidung Variante 1, Konsequenzen (Bundle-Größe, Prüfregeln, Rückweg: Option 2).
- `README.md`: Satz „does not use … network access“ bleibt korrekt (Verhalten, nicht Bibliothek); keine Änderung nötig.
- `.deutschlandgpt/handoff.md`: Abweichung und neuer Prüfstand eintragen.
- `docs/requirements.md` NFR-005 **nicht ändern**.

### 6. Größenmessung
- Bundlegröße (`du -sh dist/VueChoixGarde`) und Größe von `libQt6Network*`, `libQt6Multimedia*`, Multimedia-Plugins (`PySide6/Qt/plugins/multimedia`)
  und FFmpeg-Bibliotheken ermitteln und in `docs/development.md` oder ADR 0002 als Information eintragen (Grundlage für spätere „zu groß“-Entscheidung).

## Verifikation (lokal Linux)

1. `uv sync --locked --group build`
2. `uv run ruff format --check`, `uv run ruff check`, `uv run pyright`, `uv run pytest -q` (Basis laut Handoff: Phase 7: 330 bestanden; neue
   Tests kommen hinzu; keine Regression).
3. PyInstaller-Build wie oben; `uv run python tools/check_bundle.py dist/VueChoixGarde` → Exit 0 mit „QtMultimedia dependency“-Meldung;
   `find dist/VueChoixGarde -iname '*ssl*' -o -iname '*crypto*' -o -ipath '*plugins/tls*'` → leer.
4. `dist/VueChoixGarde/VueChoixGarde --smoke-test` → Exit 0 („smoke test passed“).
5. Negativprobe: temporär `libssl.so.3` in Kopie des Bundles legen → `check_bundle` Exit 1 (nur in `/tmp`-Kopie, nichts im Repo ändern).
6. Windows/macOS lassen sich lokal nicht bauen: die CI-Release-Läufe (`workflow_dispatch`) liefern den Nachweis. Offene Annahme: WMF- bzw.
   AVFoundation-Backend importieren QtNetwork ebenfalls (gleiche Python-Bindings) – dann greift derselbe Fix; Dateinamenmuster decken `.dll`,
   `.dylib` und `.framework` ab. Das Ergebnis ehrlich als „lokal ungetestet“ melden, bis die CI grün ist.

## Risiken

- Der PyInstaller-QtNetwork-Hook kann OpenSSL/TLS-Plugins mitliefern; Filter im Spec könnte zu aggressiv sein → Smoke-Test entscheidet.
- Bundle wird größer (Network + Multimedia-Backends); wird gemessen, nicht geschätzt.
- Dateinamen-Allowlist kann Qt-Umbenennungen übersehen (neue Qt-Version) → Tests mit synthetischen Namen, Meldung nennt Pfad.
- Aussage „App öffnet keine Netzwerkverbindungen“ stützt sich auf Code-Regeln (Ruff + AST-Test), nicht auf Abwesenheit der Bibliothek;
  QtMultimedia selbst kann bei lokalen Dateien keine Verbindungen nötig machen, wird hier aber nicht per Netzwerkmonitor geprüft.
  Optional manuell: Start mit Netzwerk-Sandbox (`unshare -n`) oder `strace -e trace=network` und Hinweis in `manual-test-plan.md`.

## Nicht Teil dieser Korrektur

Keine Commits, kein Tag/Push; keine Änderungen an NFR-005, an Phase-7-Fixes oder an den übrigen Excludes.
