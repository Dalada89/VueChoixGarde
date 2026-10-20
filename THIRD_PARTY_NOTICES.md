# Third-Party Notices

This inventory is generated from installed Python distribution metadata by
`tools/generate_third_party_notices.py`, with curated rows for native pi-heif
dependencies and the project's original sound. Verify the files included in
each release bundle and retain the corresponding upstream license texts. This
inventory is not legal advice.

| Component / version | License metadata | Use |
|---|---|---|
| Python ≥3.12 | Python Software Foundation License | Runtime for the application. |
| PySide6 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Qt for Python bindings; dynamically linked Qt libraries |
| PySide6_Essentials 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Qt Core, GUI and Widgets runtime libraries |
| PySide6_Addons 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Qt Multimedia runtime libraries |
| shiboken6 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Qt for Python binding support |
| Pillow 12.3.0 | MIT-CMU | Image decoding |
| pi-heif 1.4.0 | BSD-3-Clause | HEIF/HEIC decoding plugin |
| filelock 4.2.0 | MIT | Per-source-folder process lock |
| platformdirs 4.13.3 | MIT | Per-user application-data path resolution |
| libheif (pi-heif native wheel, where present) | LGPL-3.0-or-later | HEIF container/codec library. |
| libde265 (pi-heif native wheel, where present) | LGPL-3.0-or-later | HEVC decoder. |
| VueChoixGarde added sound | CC0 1.0 Universal | Original generated WAV cue; see `src/vuechoixgarde/resources/sounds/README.txt`. |

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
