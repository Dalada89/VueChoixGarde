# Plan: ADR 0002 – QML/Quick und FFmpeg-Platzhalter eng begrenzt erlauben

Stand: 2026-10-21 · Entscheidung des Nutzers: „Erlauben, aber eng begrenzt.“ Ergänzt `zielordner-umbenennen-loeschen.md` (unabhängig davon umsetzbar). Nur Dokumentation, Bundle-Prüfung und Test; keine Anwendungslogik.

## Context

`docs/adr/0002-qtnetwork-as-qtmultimedia-dependency.md` lässt die Frage offen, ob QtQml/QtQuick (ca. 16 MiB) und die Qt-FFmpeg-Platzhalter `ssl`/`crypto` als transitive Abhängigkeit von QtMultimedia ins Paket dürfen. Ohne sie startet die App, hat aber keinen Sound-Backend. `tools/check_bundle.py` verbietet diese Namen heute (`_FORBIDDEN_NAMES`: `qt6qml`, `qt5qml`, `qt6quick`, `qt5quick`, `libssl`, `libcrypto`), daher scheitert der Scan.

## Entscheidung

- Erlaubt nur wenn QtMultimedia im Bundle ist (wie bei QtNetwork): QtQml/QtQuick-Bibliotheken und die Qt-FFmpeg-Platzhalter für ssl/crypto.
- Weiterhin verboten: echte OpenSSL-Bibliotheken (`libssl*`, `libcrypto*` außerhalb des Platzhalter-Musters), `plugins/tls/`, `qopensslbackend`, `qcertonlybackend`, WebSockets/HttpServer/NetworkAuth/WebEngine/WebChannel/WebView, `networkinformation`, x265 (Dateiname und Binärsymbole).
- Quellcode-Verbot für Netzwerk-APIs (Ruff TID251 und AST-Test) und NFR-005 bleiben unverändert.

## Schritte

1. **Genaue Dateinamen ermitteln:** Linux-Bundle bauen bzw. das vorhandene prüfen (`uv run python tools/check_bundle.py <bundle>`), die Platzhalter-Dateinamen und -Pfade aus der Ausgabe ablesen. Nur diese Muster freigeben, keine breiten Teilstrings. Windows/macOS-Namen sind lokal nicht prüfbar: nach dem ersten Release-Workflow-Lauf ergänzen.
2. **`tools/check_bundle.py`:** Neue Konstante `_ALLOWED_WITH_MULTIMEDIA` um die QML/Quick-Marker erweitern; die exakten Platzhalter-Muster als eigene Liste. Diese Marker aus `_FORBIDDEN_NAMES` herausnehmen, aber vor der Verbotsprüfung nur dann ausnehmen, wenn Multimedia vorhanden ist. Das echte `libssl`/`libcrypto`-Verbot muss für alles andere gelten (Platzhalter-Muster so eng, dass `libssl.so.3` weiter durchfällt). Ausnahmen in der Ausgabe als „Allowed (QtMultimedia dependency)“ listen; Erfolgsmeldung anpassen.
3. **Tests `tests/unit/test_bundle_check.py`:** (a) QML/Quick + Platzhalter + Multimedia → bestanden; (b) dieselben Dateien ohne Multimedia → Fehler; (c) echte `libssl.so.3`/`libcrypto.so.3` weiterhin Fehler, auch mit Multimedia; (d) `plugins/tls/`, `qopensslbackend`, x265 weiterhin Fehler; (e) Pfad-Trenner Windows/POSIX.
4. **ADR 0002:** Status auf „Accepted“ setzen; Abschnitt „Decision“ um die Ausnahme erweitern (nur transitiv, nur mit Multimedia, Platzhalter sind keine OpenSSL-Bibliothek, Präsenz ist keine Sicherheitskontrolle); „Validation still required“ ersetzen durch: sauberer Linux-Scan und Smoke-Test nach der Änderung, Windows/macOS über Release-Workflow. Konsequenz „Paket größer / mehr Sicherheitsfragen“ beibehalten.
5. **Weitere Texte angleichen:** `tools/generate_third_party_notices.py` (Zeilen ~68–70) und danach `THIRD_PARTY_NOTICES.md` neu erzeugen (Hinweis auf QML/Quick als Multimedia-Abhängigkeit); `docs/known-limitations.md` und `CHANGELOG.md` kurz ergänzen. `docs/requirements.md` NICHT ändern (NFR-005 bleibt).
6. **Abnahme:** `uv run ruff format --check`, `uv run ruff check`, `uv run pyright`, `QT_QPA_PLATFORM=offscreen uv run pytest -q`; Linux-Bundle-Scan und `--smoke-test` grün.

## Risiken

- Zu breite Muster würden echte OpenSSL-Dateien durchlassen → Test (c) ist Pflicht.
- Platzhalter-Namen auf Windows/macOS unbekannt → erster Release-Lauf kann noch scheitern; dann Muster gezielt ergänzen.
