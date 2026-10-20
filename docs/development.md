# Development

## Requirements

- Python 3.12 or newer, as declared in `pyproject.toml`.
- `uv` for locked environments and commands.
- A Qt-capable desktop environment for interactive/manual UI checks. Headless tests use Qt offscreen.
- Build requirements and compiler/runtime libraries needed by PyInstaller and native wheels on the target operating system.

## Setup

```sh
uv sync --locked
uv run ruff format --check
uv run ruff check
uv run pyright
uv run pytest -q
```

Install the build tool group only when packaging:

```sh
uv sync --locked --group build
uv run pyinstaller --clean --noconfirm packaging/vuechoixgarde.spec
```

The output is a one-folder bundle under `dist/`. The build is unsigned. Do not use or overwrite the pre-existing wheel in `dist/`; packaging writes the application bundle there and the wheel is a separate artifact if generated explicitly.

## Runtime and smoke test

Run the installed entry point with `uv run vuechoixgarde`, or run a packaged artifact with `--smoke-test`. The smoke test creates temporary application data, starts Qt offscreen where configured, loads all three catalogs, resolves the WAV resource, decodes an in-memory JPEG and reports HEIF plugin registration. It writes a result to the application's temporary log and returns a nonzero status on failure.

## Bundle checks

```sh
uv run python tools/check_bundle.py dist/VueChoixGarde
```

The check allows QtNetwork only when QtMultimedia is present, because Multimedia imports the binding; unexplained network modules, Qt web/network add-ons, TLS/OpenSSL components and x265 fail the scan. The x265 check covers both names and binary contents; Qt module checks use filenames. Ruff TID251 and the AST regression test ensure application code never imports network APIs. The release workflow runs the checks on each built artifact and attaches platform archives with SHA-256 sums. Releases are created as drafts for a maintainer to review; publishing and signing are manual.

## Tests and privacy

Run `uv run pytest -q` from the repository root. Qt tests use the offscreen platform in CI; they use generated fixtures and temporary directories, never a user's personal image collection. Manual platform testing is tracked in `manual-test-plan.md` and `keyboard-test-checklist.md`.

## Linux bundle measurement

A local Linux x86_64 build with Python 3.13 and PyInstaller 6.22.3 occupied 239M on disk (248,502,211 bytes across 426 regular files, about 237 MiB). Measured Qt components: `libQt6Network.so.6` 2,153,672 bytes; `libQt6Multimedia.so.6` 2,048,080 bytes; `libffmpegmediaplugin.so` 855,376 bytes; QtQml libraries 8,354,896 bytes; and QtQuick 8,393,168 bytes. The bundled FFmpeg libraries (`libavformat`, `libavcodec`, `libswresample`, `libswscale`, `libavutil`) total about 20.3 MB. This is a sound-enabled build; no separate no-Multimedia A/B build was made.

The FFmpeg Multimedia plugin links to QtQml, QtQuick and QtNetwork. A probe copy with QML/Quick and FFmpeg SSL/crypto stub libraries removed reported that no QtMultimedia backend was available. Retaining a working bundled sound backend therefore appears to require QML/Quick and these Qt stub libraries. The original bundle contained no `libssl`, `libcrypto` or Qt TLS plugin paths. See [ADR 0002](adr/0002-qtnetwork-as-qtmultimedia-dependency.md) for the dependency-policy question and validation details.

## Release process

A `vX.Y.Z` tag must match the version in `pyproject.toml`. The release workflow builds Linux x86_64, Windows x86_64 and macOS arm64 artifacts, runs each artifact's smoke test, archives the bundle and creates a draft GitHub Release. Review the draft, notices, artifact contents and checksums before publishing. Do not tag or publish from a local working tree as part of routine development.
