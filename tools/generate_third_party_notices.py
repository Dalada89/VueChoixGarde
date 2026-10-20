"""Generate the third-party notice inventory from installed distribution metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, metadata, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DISTRIBUTIONS = (
    ("PySide6", "Qt for Python bindings; dynamically linked Qt libraries"),
    ("PySide6_Essentials", "Qt Core, GUI and Widgets runtime libraries"),
    ("PySide6_Addons", "Qt Multimedia runtime libraries"),
    ("shiboken6", "Qt for Python binding support"),
    ("Pillow", "Image decoding"),
    ("pi-heif", "HEIF/HEIC decoding plugin"),
    ("filelock", "Per-source-folder process lock"),
    ("platformdirs", "Per-user application-data path resolution"),
)


def _distribution_row(distribution: str, purpose: str) -> str:
    try:
        package_metadata = metadata(distribution)
        package_version = version(distribution)
    except PackageNotFoundError:
        return f"| {distribution} | Not installed in this environment | {purpose} |"
    license_name = package_metadata.get("License-Expression") or package_metadata.get("License")
    if not license_name or license_name.strip().lower() in {"unknown", "n/a"}:
        license_name = "See upstream license files included with the distribution"
    return f"| {distribution} {package_version} | {license_name} | {purpose} |"


def main() -> None:
    rows = [
        "| Python ≥3.12 | Python Software Foundation License | Runtime for the application. |",
        *(_distribution_row(name, purpose) for name, purpose in _DISTRIBUTIONS),
        "| libheif (pi-heif native wheel, where present) | LGPL-3.0-or-later | "
        "HEIF container/codec library. |",
        "| libde265 (pi-heif native wheel, where present) | LGPL-3.0-or-later | HEVC decoder. |",
        "| VueChoixGarde added sound | CC0 1.0 Universal | Original generated WAV cue; see "
        "`src/vuechoixgarde/resources/sounds/README.txt`. |",
    ]
    content = (
        """# Third-Party Notices

This inventory is generated from installed Python distribution metadata by
`tools/generate_third_party_notices.py`, with curated rows for native pi-heif
dependencies and the project's original sound. Verify the files included in
each release bundle and retain the corresponding upstream license texts. This
inventory is not legal advice.

| Component / version | License metadata | Use |
|---|---|---|
"""
        + "\n".join(rows)
        + """

## Native libraries and excluded components

pi-heif may distribute native `libheif` and `libde265` libraries, whose LGPL
terms continue to apply. This is a one-folder distribution: shared libraries
remain separate and dynamically linked. Qt/PySide6 libraries remain replaceable
in the extracted application folder, subject to their LGPL terms. This project
does not relicense dependencies.

QtNetwork is included only as a technical dependency of QtMultimedia. The
application does not use network APIs or open sockets; source imports are
checked by Ruff and an AST regression test. The bundle scan rejects `libssl`/
`libcrypto` libraries, Qt TLS plugins, and x265 encoder symbols. Qt Multimedia
may bundle Qt-provided FFmpeg SSL/crypto stubs; these are not OpenSSL libraries.
The x265 encoder is not required for decoding and must not be distributed by
these builds.

## HEVC patent notice

HEIC/HEIF content using HEVC may be subject to patent rights, royalties or
restrictions in some jurisdictions. Decoder software does not grant patent
rights. Users and distributors are responsible for assessing their
circumstances. This is informational and not legal advice.
"""
    )
    (ROOT / "THIRD_PARTY_NOTICES.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
