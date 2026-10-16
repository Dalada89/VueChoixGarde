# .deutschlandgpt

Dieser Ordner steuert, wie DeutschlandGPT Code im Arbeitsbereich „VueChoixGarde“ arbeitet. Er ist das Gegenstück zu einer Projektkonfiguration und wird von DeutschlandGPT Code automatisch gelesen.

## Ordner

- **skills**: Deine eigenen Fähigkeiten als Markdown-Dateien. Lege pro Datei eine Fähigkeit an und beschreibe sie im optionalen Kopfbereich mit einer Zeile `description:`. Der Agent sieht Name und Beschreibung und liest die Datei bei Bedarf.
- **commands**: Eigene Slash-Befehle. Eine Datei `deploy.md` wird zum Befehl `/deploy`. Der Inhalt der Datei ist die Anweisung an den Agenten. Mit dem Platzhalter `$ARGUMENTS` fügst du die übergebenen Argumente an der gewünschten Stelle ein.
- **plans**: Hierhin schreibt der Agent im Plan-Modus seine ausgearbeiteten Pläne.
- **reviews**: Hierhin schreibt der Agent die Ergebnisse von `/code-review`.

Die Dokumentation in skills und commands pflegst du selbst. plans und reviews füllt der Agent.
