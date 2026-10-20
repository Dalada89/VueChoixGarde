# Supported Formats

Extension matching is case-insensitive and uses a fixed allowlist. The file content is not used to decide whether an entry appears in the image list. Files are copied byte-for-byte; VueChoixGarde does not transcode or write metadata.

| Extensions | Listed | Display behavior |
|---|---:|---|
| `.jpg`, `.jpeg` | Yes | Pillow JPEG decoding; EXIF orientation is applied for display. |
| `.png` | Yes | Pillow PNG decoding. |
| `.gif` | Yes | First frame only; animation playback is out of scope. |
| `.bmp` | Yes | Pillow BMP decoding. |
| `.tif`, `.tiff` | Yes | First frame/page only. |
| `.webp` | Yes | Pillow WebP decoding; first frame/page. |
| `.heic`, `.heif` | Yes | Always listed. Decoding depends on the platform wheel and native decoder availability; a clear unavailable-format message is shown when decoding is unavailable. Validate the actual release artifact before relying on HEIC/HEIF. |

RAW formats, video and all other extensions are ignored. Sidecar files are copied only when they match the application’s documented sidecar rules; they are not independently shown as images. The SRS explicitly excludes RAW and video as companion files.

## HEIC/HEIF and HEVC

HEIC/HEIF decoding uses `pi-heif` and its native dependencies where available. Binary wheel and decoder behavior can vary by operating system and architecture. Release smoke tests verify JPEG decoding and plugin registration, but do not certify every HEIC sample or metadata variation. See the manual acceptance plan for real-file validation.

HEIC/HEIF content encoded with HEVC may be subject to patent rights, royalties or other restrictions in some jurisdictions. No patent license is granted by this project or its dependencies. This is general information, not legal advice.
