# ADR 0001 — Technology choice

**Status:** Accepted  
**Date:** 2026-10-16  
**Related:** [Product Requirements (SRS) v0.5](../requirements.md), [Technical Design](../technical-design.md)

## Context

VueChoixGarde is a local desktop application for Linux, Windows and macOS. The SRS deliberately leaves the technology open (SRS 1.2). The requirements that weigh most in choosing one are:

- **FR-004:** HEIC/HEIF files are always listed; decoding is platform-dependent and not a release criterion, but photos from smartphones are a typical use case (SRS 4).
- **FR-081:** Slot keys are recognized by physical position and labeled with the character of the active keyboard layout.
- **NFR-040:** Identical behavior on all three platforms.
- **FR-046, NFR-002, NFR-043:** Safe copying (temporary file, hash check, non-overwriting finalization), resolution of symbolic links/junctions, single-instance lock in the application data. These require full file system access.
- **NFR-030:** Application logic testable without a window.
- **NFR-005:** Local only, no network.

## Considered options

1. **A — Python + PySide6 (Qt 6) + Pillow + HEIF plugin**
   - Pro: HEIC decoding on all platforms; mature image library (EXIF orientation, first frame, TIFF); one toolkit with native dialogs, data paths, sound; pure-Python core that is easy to test; Python is the preferred language.
   - Contra: Qt gives the physical key position, but not the character of the active layout for that position; exact labels need native code per platform. Packages of about 80–150 MB. Smooth navigation requires background decoding and preloading.
2. **B — Electron + Vue 3 + TypeScript + sharp**
   - Pro: one browser engine everywhere (NFR-040); FR-081 nearly free (`KeyboardEvent.code` + `navigator.keyboard.getLayoutMap()`); fast UI development.
   - Contra: no HEIC decoding with the prebuilt sharp binaries; large packages (about 150–250 MB) and high memory use; Chromium must be locked down for local-only use.
3. **C — Tauri 2 + Vue 3 + Rust core**
   - Pro: small packages (about 10–20 MB), robust and well-testable Rust core.
   - Contra: three different system webviews work against NFR-040; no `getLayoutMap()` in WebKit, so FR-081 needs native code as in A; Rust know-how required.
4. **D — Pure browser app (File System Access API)**
   - Contra: cannot resolve symbolic links (NFR-002), read hidden attributes (FR-005), finalize without overwriting (FR-046), set modification times (FR-055) or lock across instances (NFR-043). Several MUST requirements are not achievable. Rejected.

## Decision

We use **Option A**:

- **Python** (CPython 3.13, minimum 3.12) with **PySide6** (Qt Widgets) for the user interface.
- **Pillow** for decoding and **`pi-heif`** (decoder-only variant of `pillow-heif`) for HEIC/HEIF.
- **uv** as package and project manager (`pyproject.toml`, committed `uv.lock`).
- **ruff** as linter and formatter.
- **pytest** and **pytest-qt** for tests, **PyInstaller** (one-folder) for release builds, GitHub Actions and GitHub Releases for distribution.

HEIC/HEIF compatibility on all platforms is valued higher than exact key labels from the first start.

For FR-081, V1 uses a simplified approach: keys are **recognized** by physical position from the start (platform-specific scan code tables), but the **label** is learned from the character the key produces when it is first pressed, and initially shows the US-QWERTY character. Users can reassign keys in the settings at any time by pressing the desired key.

## Consequences

**Positive**

- HEIC/HEIF photos can be displayed on Linux, Windows and macOS.
- One language for the whole application; the core can be tested quickly with pytest without Qt or a window.
- uv gives reproducible environments and builds through the lock file; ruff provides fast linting and formatting in one tool and is also used to enforce architecture rules (no network imports, no Qt in the core).

**Negative / accepted**

- **Deviation from FR-081 and acceptance criterion 14:** on non-US layouts a slot key label can be wrong until the key has been pressed once. The action itself is correct. The SRS should be adjusted, or native label providers (Windows `ToUnicodeEx`, Linux `xkbcommon`, macOS `UCKeyTranslate`) implemented later; the stored data format does not need to change for that.
  *Update 2026-10-16:* SRS v0.6 adopts this label behavior in FR-081 and acceptance criterion 14; it is no longer a deviation.
- The scan code tables per platform are a risk and must be validated by a small keyboard prototype before the UI is built.
- Release packages are relatively large (about 80–150 MB).
- License obligations: PySide6/Qt and `libheif`/`libde265` are LGPLv3 (dynamic linking, license texts in releases). The HEVC patent situation must be assessed before the first public release.
- `pillow-heif` is not used because its binary wheels bundle the GPL-licensed `x265` encoder, which is not needed for viewing.
