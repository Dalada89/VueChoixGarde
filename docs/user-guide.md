# User Guide

## Install and launch

Download the archive for your operating system from Releases and extract the complete archive to a writable location. Do not launch the executable from inside the compressed archive or separate it from the adjacent application files.

- **Linux:** extract the `.tar.gz`; if the executable bit was not retained, run `chmod +x VueChoixGarde/VueChoixGarde`, then launch it. On minimal distributions, install the system libraries required by Qt 6 and audio output.
- **Windows:** extract the `.zip` and launch `VueChoixGarde/VueChoixGarde.exe`. Because the release is unsigned, SmartScreen may display a warning. Check the published SHA-256 checksum and only continue if you trust the download.
- **macOS Apple silicon:** extract the archive and open `VueChoixGarde.app`. The app is unsigned and not notarized. Gatekeeper may block the first launch; review the warning and, if you trust the downloaded build, approve it in System Settings → Privacy & Security. macOS Intel builds are not provided.

Application settings, profiles, the copy register and logs are stored in the current user's standard application-data directory; they are not written into the source folder. The application is designed to run offline.

## Review and sort images

1. Choose **Open folder…** and select a readable source folder.
2. The app lists supported files directly in that folder only. It does not scan subfolders, hidden entries or destination folders recursively.
3. Use Left/Right to navigate. F5 refreshes the list; refresh does not watch the folder continuously. The sort control changes ascending/descending natural filename order.
4. Activate a slot key to add a byte-identical copy into that slot's direct destination subfolder. On first use, enter a valid destination name. Activating the same slot again removes a verified managed copy.
5. If a managed copy was changed outside the app, removal requires confirmation. Cancel is the default. Files that are not registered as app-managed are treated as conflicts and are not overwritten or deleted.

The source image and sidecars are never changed. Toggle-off permanently deletes only verified copies after confirmation rules; there is no recycle-bin integration or undo history.

## Slots, profiles and templates

Settings → Slots lets you add or remove slots (one to 12), assign a physical key position, choose a destination folder name and select a color. Duplicate keys or destination names block saving. Destination folders are direct children of the source folder.

A profile belongs to a source folder and persists its slots and copy register. The global slot template supplies slots for a folder with no existing profile. Settings → Profiles allows managing templates and profiles, including orphaned profiles. Reassigning a profile does not move image files.

## Keyboard shortcuts and layout labels

- Left / Right: previous / next image
- F1: contextual help
- F5: refresh the folder listing
- Escape: close the current dialog
- Ctrl+,: open settings
- Ctrl+O: open a source folder
- Slot keys: toggle the current image in the corresponding destination

Slot actions use physical key positions. The initial captions use US-QWERTY characters; on a non-US layout, press a slot key once so the app can learn the character produced at that position. Until then its caption may be inaccurate even though the action position is fixed. A dead key can briefly cause a composed character to be learned. Reassign keys in Settings if needed. See the manual checklist for layout validation.

## Settings, language and sound

Settings → General controls the interface language (German, English or French), the optional added-copy sound, the default sort order, and reopening the last source folder. Sound is played only after a successful toggle-on and only when enabled. Audio-device failures do not interrupt file operations.

## Logs and recovery

Logs are local JSON Lines files under the application-data directory. They are intended for troubleshooting and do not contain image bytes or image metadata. Do not share logs without reviewing their paths and operational details.

The app journals copy operations and performs recovery/reconciliation when a folder is opened. Reconciliation updates register state but does not create, modify or delete image files. If application data is damaged, the app offers to continue with defaults or in view-only mode. The damaged data is preserved unless the user accepts the recovery choice.

## Accessibility

The interface supports keyboard operation, descriptive accessible names on key controls, visible focus styling and high-contrast interface text. Text can be translated in German, English and French. The slot color stripe is supplementary; status is also conveyed with a symbol and text.

For format-specific behavior and release limitations, see [Supported Formats](supported-formats.md) and [Known Limitations](known-limitations.md).
