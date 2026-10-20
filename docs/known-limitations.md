# Known Limitations

- **QtNetwork library in the bundle:** QtNetwork is present only as a technical dependency of QtMultimedia. Application code does not import it or open sockets; Ruff and an AST regression test enforce the code boundary. TLS/OpenSSL components are excluded and checked in release bundles.
- **Unsigned builds:** release binaries are not signed; macOS builds are not notarized. Windows SmartScreen and macOS Gatekeeper may show warnings. See the [User Guide](user-guide.md).
- **macOS architecture:** no Intel macOS build is produced; the release target is Apple silicon (arm64).
- **HEIC/HEIF:** files are listed everywhere, but decoding depends on the packaged wheel/native libraries and has not been validated against every camera sample. See [Supported Formats](supported-formats.md).
- **Keyboard labels:** actions use physical positions, while labels start with US-QWERTY characters and are learned on the first unmodified keypress. Dead-key composition can temporarily teach a composed character. See FR-081/FR-086 and the keyboard checklist.
- **Keyboard hardware validation:** results for X11, Wayland, Windows and macOS, QWERTY/QWERTZ/AZERTY, AltGr and dead keys must be recorded on real devices. The checklist intentionally leaves those results blank until testing is performed.
- **Wayland:** physical scan-code behavior and popup/focus handling require manual testing in a Wayland session; synthetic automated events do not establish hardware behavior.
- **Path lengths:** long-path behavior depends on operating-system and filesystem support. Windows has a dedicated extended-path implementation; system policy and non-local filesystems may still impose limits.
- **Profiles and app data:** moving a source folder can require manual profile reassignment. Back up application data before changing or deleting it outside the app.
- **Refresh:** the image list is a snapshot and is not watched continuously. Use Refresh after external changes.
- **Display:** animated formats show only their first frame/page. No zoom, editing, video playback, RAW decoding or recursive scan is provided.
- **Recovery:** recovery is journal-driven and conservative; ambiguous or externally modified files may remain pending for manual resolution rather than being changed.
- **Performance:** documented local smoke measurements are informative only and are not a cross-platform performance guarantee.
