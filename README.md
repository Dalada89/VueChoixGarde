# VueChoixGarde

VueChoixGarde is a local desktop application for reviewing images and sorting byte-identical copies into destination folders. The source images are never modified. The application does not use accounts, cloud services, network access or automatic updates.

## Features

- Keyboard-first review, natural filename sorting and manual refresh.
- Up to 12 configurable destination slots, profiles and a global slot template.
- Safe copy/toggle behavior with conflict detection, a local copy register and recovery journal.
- German, English and French interface; optional success sound.
- JPEG, PNG, GIF, BMP, TIFF and WebP; HEIC/HEIF remains visible even where decoding is unavailable.

## Download and install

Download the archive for your operating system from the [GitHub Releases](../../releases) page. Releases are unsigned and are distributed as one-folder application bundles. Extract the whole archive before launching; do not move the executable out of its application folder.

- **Linux:** extract the `.tar.gz` archive and launch `VueChoixGarde/VueChoixGarde`. If needed, run `chmod +x VueChoixGarde/VueChoixGarde` first.
- **Windows:** extract the `.zip` archive and launch `VueChoixGarde/VueChoixGarde.exe`. Windows SmartScreen may show a warning because builds are unsigned; verify the published SHA-256 checksum before proceeding.
- **macOS (Apple silicon):** extract the archive and launch the `.app`. Gatekeeper may require the user to explicitly approve an unsigned app in Privacy & Security. The app is not notarized.

See the [User Guide](docs/user-guide.md) for first-run steps and safety details.

## Quick start

1. Launch the app and choose a source folder.
2. Review images with Left/Right or the on-screen controls.
3. Give a slot a destination folder name when first used. The destination is a direct subfolder of the source folder.
4. Press the slot key to add a copy. Press it again to remove a verified copy. Modified copies require explicit confirmation.
5. Use Settings to configure slots, language, sound and profiles.

## Platform and format matrix

| Platform | Release artifact | CPU | Image formats |
|---|---|---|---|
| Linux | One-folder `.tar.gz` | x86_64 | JPEG, PNG, GIF, BMP, TIFF, WebP; HEIC/HEIF decoding platform-dependent |
| Windows | One-folder `.zip` | x86_64 | JPEG, PNG, GIF, BMP, TIFF, WebP; HEIC/HEIF decoding platform-dependent |
| macOS | `.app` archive | arm64 | JPEG, PNG, GIF, BMP, TIFF, WebP; HEIC/HEIF decoding platform-dependent |

The release platform matrix reflects automated builds; see [Supported Formats](docs/supported-formats.md) and [Known Limitations](docs/known-limitations.md) for qualification.

## Development

See [Development](docs/development.md) for prerequisites, setup, checks and packaging instructions.

## License

The application is licensed under the MIT License. Bundled third-party components retain their own licenses; see [Third-Party Notices](THIRD_PARTY_NOTICES.md). HEVC patent rights may apply to HEIC/HEIF use in some jurisdictions; see the [format notes](docs/supported-formats.md). This is not legal advice.
