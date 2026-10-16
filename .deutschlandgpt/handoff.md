# Handoff – VueChoixGarde

Stand: nach Abschluss der Konzeptphase, vor Beginn der Entwicklung.
Zweck: Fortsetzung der Arbeit auf einem anderen Rechner bzw. in einer neuen Sitzung.

## 1. Ziel des Projekts

VueChoixGarde soll gemäß `docs/requirements.md` (SRS v0.5) als **lokal laufende Desktop-App** umgesetzt werden.

## 2. Arbeitsweise / Präferenzen

- Kommunikation auf Deutsch; Projektdokumente (Requirements, Design, ADR) auf Englisch.
- Technische Vorschläge konkret, mit Vor-/Nachteilen und mindestens zwei Varianten.
- Anwendung bleibt vollständig lokal (keine Cloud-Abhängigkeit).
- Technische Konzepte werden in `docs/` dokumentiert.
- Bisher wurde bewusst **kein Code** erstellt – erst Dokumentation, dann Entwicklung.
- Projektanweisung beachten: keine geheimen Dateien (`.env`, Schlüssel, Tokens, Backups usw.) lesen oder verarbeiten.

## 3. Bisherige Ergebnisse

| Datei | Inhalt | Status |
|---|---|---|
| `docs/requirements.md` | SRS v0.5 | committet (`74de1f4`) |
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

### Tastaturkonzept (Abweichung von FR-081)

- Tasten werden von Anfang an über ihre **physische Position** erkannt (plattformspezifische Scancode-Tabellen) – die Aktion ist immer korrekt.
- Die **Beschriftung** zeigt zunächst das US-QWERTY-Zeichen und wird beim ersten Tastendruck durch das tatsächlich erzeugte Zeichen ersetzt.
- Neubelegung jederzeit in den Einstellungen per Tastendruck möglich.
- Folge: Auf Nicht-US-Layouts kann die Beschriftung bis zum ersten Drücken falsch sein. Das widerspricht FR-081 und Abnahmekriterium 14 → SRS muss angepasst werden (siehe offene Punkte).

## 5. Bekannte Risiken (Auswahl, Details in `docs/technical-design.md` Abschnitt 14)

- Scancode-Tabellen je Plattform → vor dem UI-Bau per Tastatur-Prototyp validieren.
- HEVC-Patentlage vor einer Veröffentlichung prüfen.
- Race Condition mit Fremdprogrammen zwischen Prüfung und Finalisierung (Finalisierung überschreibt nie; Restrisiko dokumentiert).
- Paketgröße / unsignierte Builds.
- Performance bei 10.000 Bildern und großen JPEGs (NFR-010/011).

## 6. Offene Punkte

Vor Entwicklungsbeginn klären:

1. **SRS anpassen:** FR-081 (`docs/requirements.md`, ca. Zeile 187) und Abnahmekriterium 14 (ca. Zeile 274) an das akzeptierte Beschriftungsverhalten anpassen. Sonst schlägt die Abnahme formal fehl.
2. **Typprüfer festlegen:** mypy, pyright oder keiner.
   Empfehlung: **pyright** (Modus „standard“) – schneller, gute Unterstützung der PySide6-Stubs. mypy wäre der verbreitete Standard, aber langsamer.

Kann später entschieden werden:

3. **Projektlizenz:** muss mit LGPL-Komponenten (PySide6) vereinbar sein; MIT oder Apache-2.0 sind bei dynamischem Linken/One-Folder-Build möglich. Falls das GitHub-Repo öffentlich ist, früh festlegen.
4. **macOS-Intel-Build** ja/nein – relevant erst für Packaging/CI.
5. `.deutschlandgpt/` committen oder in `.gitignore` aufnehmen.

## 7. Empfohlene nächsten Schritte

1. Offene Punkte 1 und 2 entscheiden und umsetzen.
2. Projektgerüst anlegen: `uv init`, `pyproject.toml` mit Ruff, pytest, pytest-qt und gewähltem Typprüfer; Grundstruktur gemäß `docs/technical-design.md`.
3. **Tastatur-Prototyp** (Spike) auf Windows, Linux und macOS: Erkennung per physischer Position und Beschriftungs-Lernen prüfen.
4. Kern ohne UI implementieren: Ordner-Scan, sicheres Kopieren (FR-046), SQLite-Register, Symlink-Erkennung (NFR-002), Einzelinstanz je Ordner (NFR-043) – mit Tests.
5. Danach UI auf Basis von PySide6.

## 8. Einstieg in der neuen Sitzung

Vorschlag für die erste Nachricht:

> Lies `.deutschlandgpt/handoff.md`, `docs/technical-design.md` und `docs/adr/0001-technology-choice.md` und mach mit den offenen Punkten in Abschnitt 6 weiter.

Hinweis: Diese Datei und `.deutschlandgpt/` müssen committet und gepusht werden, damit sie auf dem anderen Rechner verfügbar sind.
