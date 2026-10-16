# Plan: Entwicklungsstart für VueChoixGarde

## Kontext

Das Handoff beschreibt den Stand nach der Konzeptphase und vor dem ersten Anwendungscode. `docs/requirements.md` (SRS v0.5), `docs/technical-design.md` und `docs/adr/0001-technology-choice.md` legen den Produktumfang und Python/PySide6-Architektur bereits fest. Im aktuellen Projektdateibestand sind keine Anwendungssourcen oder Projektmanifeste vorhanden. Vor dem produktiven UI-Start bestehen zwei dokumentierte Klärungen: FR-081/Abnahmekriterium 14 widersprechen dem akzeptierten Beschriftungs-Fallback, und der statische Typprüfer ist noch offen. Der separate Plan `image-sorter-desktop-app.md` beschreibt einen abweichenden, älteren/anderen Umfang und ist nicht die maßgebliche Spezifikation.

## Betroffene Dateien

- `docs/requirements.md` – FR-081 und Abnahmekriterium 14 an die bereits akzeptierte Beschriftungs-Lernlogik angleichen.
- `docs/technical-design.md` – Entscheidung für pyright (standard) dokumentieren und Umsetzungskonfiguration konkretisieren.
- `pyproject.toml`, `uv.lock`, `.python-version` – Projektgrundlage und Abhängigkeiten gemäß technischem Design erstellen.
- `src/vuechoixgarde/`, `tests/` – Paketstruktur und erste testgetriebene Kernbausteine anlegen.
- `docs/` – Abweichende/alte Planung nicht als Implementierungsspezifikation verwenden; technische Doku bleibt maßgeblich.

## Schritte

1. Vor dem ersten Implementierungsschritt die beiden Startentscheidungen bestätigen: SRS-Fassung für FR-081/Abnahmekriterium 14 und pyright im Standard-Modus als Typprüfer (empfohlene Voreinstellung gemäß Handoff).
2. SRS und technisches Design aufeinander abstimmen; Projektlizenz, macOS-Intel-Build und Commit-Policy für `.deutschlandgpt/` als spätere Entscheidungen belassen.
3. Projektgerüst passend zum Design erstellen: Python >=3.12, uv, PySide6, Pillow, pi-heif, platformdirs, filelock; pytest, pytest-qt, Ruff, pyright und PyInstaller in den passenden Abhängigkeitsgruppen. Die Architekturgrenzen und Ruff-Regeln aus dem Design konfigurieren.
4. Einen kleinen Tastatur-Spike für physische Tastenpositionen bauen und die auf Linux erreichbaren Qt-Scancodes testen; Windows/macOS-Verifikation als plattformübergreifenden Validierungspunkt dokumentieren, bevor die Tastatursteuerung der UI als abgeschlossen gilt.
5. Mit testgetriebener, UI-unabhängiger Kernlogik beginnen: Namens-/Slotvalidierung, deterministische natürliche Sortierung, Bildlistenfilter, Sidecar-Zuordnung und Navigation. Danach sichere Dateisystemoperationen, Register/Recovery und erst dann UI ausbauen.
6. Checks gemäß Projektkonfiguration ausführen: `uv sync --locked`, `uv run ruff format --check`, `uv run ruff check`, `uv run pyright` und `uv run pytest`; fehlende plattformübergreifende Prüfungen klar kennzeichnen.

## Risiken

- Ohne Korrektur der SRS würde die beschlossene Tastaturbeschriftung bei der formalen Abnahme scheitern.
- Die Scancode-Zuordnung kann je Qt/OS/Wayland-Tastatur variieren; UI-Integration erst nach Prototypprüfung abschließen.
- Sichere Kopier-/Rollback-Logik hat hohes Datenverlustrisiko und muss mit Fehler-Injektion und temporären Testordnern abgedeckt werden.
- Die Plandatei `image-sorter-desktop-app.md` enthält abweichende Anforderungen und Toolentscheidungen; sie darf nicht parallel als Quelle der Wahrheit genutzt werden.
- `uv` ist im bereitgestellten Host-Tool-Snapshot nicht aufgeführt; Verfügbarkeit beim Start prüfen und gegebenenfalls erst einrichten.
