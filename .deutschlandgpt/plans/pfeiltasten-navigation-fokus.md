# Umsetzung: Pfeiltasten-Navigation bei Fokus auf UI-Elementen

## Kontext

Die Links/Rechts-Navigation liegt in `MainWindow.keyPressEvent()` und erreicht den Fall mit direktem Tastendruck am Fenster, nicht aber zuverlässig Tastendrücke auf fokussierten Kind-Widgets. Qt verarbeitet Pfeiltasten auf fokussierten Buttons zur Fokusnavigation. Der vorhandene Test sendet Ereignisse direkt an das Hauptfenster und deckt das reale Symptom daher nicht ab.

Der Nutzer hat die Umsetzung ausdrücklich freigegeben.

## Betroffene Dateien

- `src/vuechoixgarde/ui/main_window.py`
- `tests/ui/test_main_window.py`
- `.deutschlandgpt/handoff.md`

## Konkrete Schritte

1. Einen Qt-Anwendungs-Eventfilter am MainWindow installieren. Nur unveränderte Links/Rechts-KeyPress-Ereignisse von Widgets dieses Fensters abfangen und über die vorhandene asynchrone Navigation weiterleiten. Vorher die bestehende Ausnahmeprüfung für Dialoge, Popups und Texteingaben sowie den geladenen Bildstatus prüfen. Andere Ereignisse unverändert durchlassen.
2. UI-Regressionstests ergänzen: bei fokussiertem Button navigieren die Pfeiltasten zum vorherigen/nächsten Bild und der Button-Fokus bleibt erhalten; in einem geöffneten Dialog mit Texteingabe löst die Pfeiltaste keine Hauptfenster-Navigation aus.
3. Erst den betroffenen UI-Test, danach Ruff, Pyright und die vollständige Pytest-Suite ausführen; gefundene Probleme beheben.
4. Handoff mit Ursache, Lösung und tatsächlichen Prüfergebnissen aktualisieren.

## Risiken

Der Anwendungsfilter sieht Ereignisse aus der ganzen Qt-Anwendung. Deshalb muss er strikt auf Kind-Widgets des jeweiligen MainWindow begrenzt sein und die vorhandene Schutzlogik für Dialog-/Popup- und Texteingabefokus respektieren. Keine Änderung an Slot-Tastenbelegung oder sonstigen Shortcuts.
