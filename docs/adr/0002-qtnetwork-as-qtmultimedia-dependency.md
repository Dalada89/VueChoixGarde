# ADR 0002: Bundle QtNetwork as a QtMultimedia dependency

- Status: Accepted for the QtNetwork binding only; additional native dependencies discovered during the Linux build require a product-owner decision.

## Context

The packaged smoke test could not start when `PySide6.QtNetwork` was excluded: `PySide6.QtMultimedia` imports the binding at module load. Sound feedback is a product requirement and `QSoundEffect` remains in the application. The SRS requirement NFR-005 prohibits sending images, metadata, settings or logs over the network; it does not prohibit a transitive Qt library from being present.

## Options considered

1. Bundle QtNetwork only as QtMultimedia's technical dependency, enforce a source-level no-network-import rule, and reject unexplained network modules and TLS components in bundle checks.
2. Remove QtMultimedia and the bundled sound cue.
3. Replace QtMultimedia with platform-specific native sound players, with separate Windows, macOS and Linux implementations.
4. Produce separate sound-enabled and sound-free application bundles.

## Decision

Choose option 1. Keep `QSoundEffect`, include `PySide6.QtNetwork` as a PyInstaller hidden import, and do not import or use network APIs in application code. Preserve the Ruff TID251 ban and add an AST regression test covering direct imports, `from PySide6 import QtNetwork`, and dynamic `importlib.import_module` calls. NFR-005 is unchanged.

The release bundle checker permits QtNetwork only when QtMultimedia is present. It rejects unexplained network/web modules, TLS/OpenSSL filenames and x265 encoder artifacts. Qt-module names are checked by filename; x265 is checked by filename and encoder-specific binary symbols to avoid false positives from harmless version/codec-name strings.

## Consequences

- The QtNetwork binding/library is shipped as an implementation dependency, not as an application feature. The bundle is larger and may attract broader security review.
- Source-level guards (Ruff and AST) enforce the application-code boundary; the library's presence is not a security control.
- TLS/OpenSSL shared libraries and Qt TLS plugins must not be bundled. Release tests enforce this policy.
- A Linux PyInstaller build (Python 3.13, PyInstaller 6.22.3, x86_64) completed and the packaged `--smoke-test` exited 0. Bundle file contents total 248,502,211 bytes (about 237 MiB; `du -sh` reports 239M). The QtNetwork library is 2,153,672 bytes; QtMultimedia is 2,048,080 bytes; the FFmpeg Multimedia plugin is 855,376 bytes.
- The same build also contains QtQml/QtQuick native libraries (about 16.0 MiB combined) and Qt FFmpeg `ssl`/`crypto` stub libraries. The Multimedia FFmpeg plugin's dynamic dependencies include QtQml, QtQuick and QtNetwork. A copy of the bundle with the QML/Quick and FFmpeg `ssl`/`crypto` stubs removed started the app, but reported that no QtMultimedia backend was available. Therefore retaining functioning sound appears to require at least the QML/Quick runtime dependencies. No `libssl`, `libcrypto` or Qt `plugins/tls` files were found in the original bundle. Whether the Qt FFmpeg stubs are acceptable under the no-TLS policy and whether QML/Quick may be allowed as transitive Multimedia dependencies must be confirmed before the bundle scan can pass without weakening the previous exclusions.
- The 239M bundle is the sound-enabled measurement. A separate sound-free baseline was not built; the component sizes above provide the measured Multimedia-related footprint, not a claimed A/B build delta.

## Rejected alternatives and reversibility

Removing QtMultimedia is the straightforward rollback if the additional dependency footprint or policy is unacceptable; it also removes sound. Platform-specific players and dual artifacts add maintenance and validation cost. The decision can be revisited by changing the sound implementation and bundle policy together.

## Validation still required

- Resolve the QtQml/QtQuick and FFmpeg stub dependency policy, then make the bundle checker pass without suppressing unrelated network or x265 findings.
- Run a clean Linux bundle scan and smoke test after that resolution. Windows and macOS remain untested locally and require successful release workflow runs.
