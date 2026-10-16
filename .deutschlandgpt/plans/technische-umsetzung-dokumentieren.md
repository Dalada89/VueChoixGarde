# Plan: Technische Umsetzungsvarianten dokumentieren

## Kontext

`docs/requirements.md` (SRS v0.5) legt bewusst keine Technologie fest (Abschnitt 1.2). Es fehlt eine technische Beschreibung, wie VueChoixGarde umgesetzt wird. Grundbedingung: alles bleibt lokal (NFR-005), keine Netzwerkdienste, kein Auto-Update.

Die Anforderungen mit dem größten Einfluss auf die Technologiewahl:

| Anforderung | Warum sie bei der Wahl entscheidet |
|---|---|
| FR-081 Physische Tastenposition + Anzeige des Zeichens im aktiven Layout | Position abfragen ist überall leicht, die Anzeige des passenden Zeichens im aktiven Layout aber nicht |
| NFR-040 Gleiches Verhalten unter Linux/Windows/macOS | Unterschiedliche Rendering-Engines/Webviews erzeugen Abweichungen |
| FR-004/021/022 Formate, EXIF-Orientierung, erstes Frame, TIFF/HEIC | Bestimmt die Bildbibliothek |
| FR-046 Sicheres Kopieren: Temp-Datei, Hash prüfen, umbenennen ohne Überschreiben | Braucht echten Dateisystemzugriff (Link/Rename ohne Überschreiben) |
| NFR-002 Symlinks/Junctions auflösen, FR-005 versteckte Dateien | Braucht `realpath`/`lstat` und Dateiattribute des Betriebssystems |
| NFR-043 Sperre pro Ordner außerhalb des Quellordners, FR-091/092 JSONL-Log mit Rotation | Braucht App-Daten-Verzeichnis des Betriebssystems |
| NFR-030 Logik ohne Fenster testbar | Klare Schichten: Kern, Speicherung, Dateizugriff, UI |

## Varianten

### A) Python 3.12 + PySide6 (Qt 6) + Pillow (+ pillow-heif)
- UI: Qt Widgets (QSS für dunkles Design), `QFileDialog`, `QStandardPaths` (App-Daten), `QLockFile` (NFR-043), Qt-Übersetzungen (DE/EN/FR), `QSoundEffect`.
- Bild: Pillow `ImageOps.exif_transpose`, `seek(0)` für das erste Frame; `pillow-heif` für HEIC.
- Dateien: `pathlib`/`os`; Finalisieren per `os.link(tmp, ziel)` + `unlink(tmp)` (schlägt fehl, wenn das Ziel existiert); `hashlib`; `shutil.copystat`/`os.utime` für mtime.
- Tests: pytest, pytest-qt; Pakete: PyInstaller oder Briefcase, GitHub Actions Matrix.
- Pro: ausgereifte Bildbibliothek, HEIC auf allen Plattformen möglich, ein Toolkit, gut testbarer Python-Kern.
- Contra: FR-081 (Layoutzeichen zur Scancode-Position) braucht pro Plattform eigenen Code (xkbcommon / `ToUnicodeEx` / `UCKeyTranslate`); PyInstaller-Pakete 80–150 MB, unsignierte Builds lösen öfter Virenwarnungen aus; flüssige Navigation braucht Vorladen in Threads.

### B) Electron + Vue 3 + TypeScript + sharp (libvips)
- Main-Prozess (Node): Dateizugriff, Kopierlogik, Register (JSON-Datei mit atomarem Schreiben), Log (z. B. pino + Rotation), Sperre (Lockdatei im App-Datenordner), `app.getPath('userData')`, `dialog.showOpenDialog`.
- Renderer (Vue): UI, `KeyboardEvent.code` für physische Position, `navigator.keyboard.getLayoutMap()` für das angezeigte Zeichen (in Chromium auf allen Plattformen vorhanden), vue-i18n.
- Bild: sharp im Main-Prozess: `.rotate()` (EXIF), `page: 0` (erstes Frame), TIFF → Anzeige-JPEG/WebP über ein eigenes `app://`-Protokoll. HEIC: die vorgebauten sharp-Binaries dekodieren kein HEVC → Fehlermeldung nach FR-004 (zulässig, kein Release-Kriterium).
- Kopieren: `fs.copyFile` auf Temp-Datei, Hash, `fs.link` → `unlink` (kein Überschreiben), `fs.utimes`.
- Tests: Vitest (Kern ohne Electron), Playwright für E2E; Verteilung mit electron-builder als GitHub-Release.
- Pro: überall dieselbe Chromium-Engine (NFR-040), FR-081 fast ohne Zusatzaufwand, Vue passt zum Projektnamen, modernes UI schnell gebaut.
- Contra: Pakete groß (~150–250 MB) und mehr RAM; Chromium muss bewusst abgeschottet werden (kein Remote-Content, CSP, Rechtschreibprüfungs-Download und Updater aus); kein HEIC.

### C) Tauri 2 + Vue 3 + TypeScript, Kern in Rust
- Rust-Kern: Dateien (`std::fs::hard_link`, `sha2`), Bild (`image` + `kamadak-exif`, optional `libheif-rs`), `directories` für App-Daten, `fs4` für Sperre; UI wie in B.
- Pro: kleine Pakete (~10–20 MB), wenig RAM, sehr robuster und gut testbarer Kern (`cargo test`).
- Contra: drei verschiedene Webviews (WebView2, WKWebView, WebKitGTK) → Abweichungen gegen NFR-040; `getLayoutMap()` fehlt in WebKit → FR-081 wieder nativ in Rust pro Plattform; Rust-Know-how nötig; WebKitGTK unter Linux hat bekannte Eigenheiten.

### D) Reine Browser-App (File System Access API) – nicht empfohlen
- Pro: keine Installation, statische Dateien.
- Contra: nur Chromium; keine Symlink-Auflösung (NFR-002), keine versteckten Dateiattribute (FR-005), kein Umbenennen ohne Überschreiben (FR-046), kein mtime (FR-055), keine Sperre zwischen Instanzen (NFR-043), App-Daten nur in IndexedDB/OPFS statt im Ordner des Betriebssystems, Log-Ordner nicht öffenbar (FR-092). Mehrere MUST-Anforderungen sind damit nicht erfüllbar.

## Empfehlung (Entscheidung durch Nutzer)
- **B (Electron + Vue)**, wenn gleiches Verhalten auf allen Plattformen und FR-081 Vorrang haben.
- **A (PySide6)**, wenn Python bevorzugt wird und HEIC wichtig ist; den Mehraufwand für FR-081 einplanen.

## Betroffene Dateien
- NEU `docs/technical-design.md`: Technisches Konzept (Varianten, Vergleichstabelle, Entscheidung, Architektur der gewählten Variante).
- Optional NEU `docs/adr/0001-technologiewahl.md`: kurzer Architecture Decision Record (Kontext, Entscheidung, Folgen).
- Keine Änderung an `docs/requirements.md` (bleibt technologieneutral nach 1.2).

## Schritte nach Freigabe
1. Nutzer wählt eine Variante (A, B oder C).
2. `docs/technical-design.md` anlegen mit:
   1. Zweck, Bezug auf SRS v0.5
   2. Vergleich der Varianten (Tabelle mit den Kriterien oben) und Begründung der Wahl
   3. Architektur nach NFR-030: Module `core` (Sortierung, Navigation, Slot-/Namensprüfung, Toggle-Entscheidung), `fs` (Dateizugriff, sicheres Kopieren, Pfadprüfung), `store` (Einstellungen, Profile, Kopierregister, Schreiben über Temp-Datei + Rename), `ui`, `log`
   4. Datenformate: Einstellungen/Profile/Register (JSON mit Schemaversion), Ablageort pro Betriebssystem
   5. Ablauf Toggle on/off als Schrittfolge zu FR-044–FR-050
   6. Umsetzung der Plattformdetails: Tastatur (FR-081), Unicode-Normalisierung NFC + case-fold (NFR-041), reservierte Windows-Namen (FR-034), Symlinks/Junctions (NFR-002), HEIC je Plattform
   7. Maßnahmen „nur lokal“ (NFR-005)
   8. Teststrategie zu Abschnitt 8 und Build/Release (NFR-044)
   9. Risiken und offene Punkte
3. Optional den ADR anlegen.
4. Keine Befehle nötig (reine Dokumentation).

## Risiken
- FR-081 ist bei A und C der größte Aufwand. Zuerst einen kleinen Prototyp bauen.
- HEIC: Lizenz-/Patentlage von HEVC-Decodern (libheif/libde265) für die Verteilung prüfen.
- Unsignierte Builds: Hinweise zu Gatekeeper/SmartScreen dokumentieren (NFR-044).
