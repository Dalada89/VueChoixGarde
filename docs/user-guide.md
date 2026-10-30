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
4. A slot in **Copy** mode adds a byte-identical copy to its direct destination subfolder. A slot in **Move** mode moves the current image and its sidecars there as a group. On first use, enter a valid destination name. Copy-mode slots toggle verified copies off; Move-mode actions are one-shot and remove the image from the source list.
5. If a managed copy was changed outside the app, removal requires confirmation. Cancel is the default. Files that are not registered as app-managed are treated as conflicts and are not overwritten or deleted.

Copy mode never changes source images or sidecars. Move mode deliberately changes the source folder: the image and exclusive sidecars leave it; a sidecar shared with another listed image is copied so that image keeps it. `Ctrl+Z` undoes the latest successful move in the current folder session, in reverse order. The undo stack is cleared when you change folders or close the app; there is no redo. If the original filename is occupied or a moved file is missing from its remembered destination, undo stops without changing files. Changed moved files are still restored with their current contents.

The default **R → trash** destination is an ordinary subfolder of the source folder, not the operating-system recycle bin. The app never moves files to the OS trash; empty or relocate `trash` yourself when desired.

## Slots, profiles and templates

Settings → Slots lets you add or remove slots (one to 12), assign a physical key position, choose a destination folder name and color, and select **Copy** or **Move** mode. Duplicate keys or destination names block saving. A mode change is blocked while that destination contains managed copies. Destination folders are direct children of the source folder. The default profile has W/A/S/D copy slots and an R Move slot targeting `trash`; this slot can be renamed or configured like the others. Eligible older settings and profiles receive R/`trash` once during migration if the key and name are free and fewer than 12 slots exist.

A profile belongs to a source folder and persists its slots and copy register. The global slot template supplies slots for a folder with no existing profile. Settings → Profiles allows managing templates and profiles, including orphaned profiles. Reassigning a profile does not move image files.

### Rename or delete a destination folder

In Settings → Slots → Select "Current folder profile" from the dropdown, changing the saved name of an existing destination in the current profile and saving renames that direct child folder on disk, updates its copy register and keeps the profile consistent. The app checks every target before changing anything and never replaces an existing entry. A name swap must be done in separate saves. Clearing a name, removing a slot, or changing the global template does not rename a folder.

Use **Delete destination…** on an unchanged saved profile slot to inspect its folder. If every entry is a verified managed copy, confirmation permanently deletes those copies and the now-empty folder; nothing goes to the recycle bin. Cancel is the default and Escape cancels. If the folder contains unknown, changed, hidden or non-file entries, the app leaves all files and the folder untouched and offers to remove only the slot assignment and register records. You can then review and delete the remaining files manually. If the folder changed after inspection, the app asks you to review the new state before acting. A missing folder only has its saved assignment and register information removed.

## Keyboard shortcuts and layout labels

- Left / Right: previous / next image
- F1: contextual help
- F5: refresh the folder listing
- Escape: close the current dialog
- Ctrl+,: open settings
- Ctrl+O: open a source folder
- Ctrl+Z: undo the latest move in the current folder session
- Slot keys: apply the configured Copy or Move action to the current image

Slot actions use physical key positions. The initial captions use US-QWERTY characters; on a non-US layout, press a slot key once so the app can learn the character produced at that position. Until then its caption may be inaccurate even though the action position is fixed. A dead key can briefly cause a composed character to be learned. Reassign keys in Settings if needed. See the manual checklist for layout validation.

## Settings, language and sound

Settings → General controls the interface language (German, English or French), the optional success sound, the default sort order, and reopening the last source folder. Sound is played after a successful Copy or Move action when enabled, but not after undo, removal, a conflict or an error. Audio-device failures do not interrupt file operations.

## Logs and recovery

Logs are local JSON Lines files under the application-data directory. They are intended for troubleshooting and do not contain image bytes or image metadata. Do not share logs without reviewing their paths and operational details.

The app journals Copy and Move operations and performs conservative recovery before reconciliation when a folder is opened. An interrupted Move is rolled back only when journaled files and their locations can be verified; ambiguous or changed states remain pending rather than being guessed. Reconciliation updates copy-register state but does not create, modify or delete image files. The `Ctrl+Z` undo stack is session-only and is not restored after restart. If application data is damaged, the app offers to continue with defaults or in view-only mode. The damaged data is preserved unless the user accepts the recovery choice.

## Accessibility

The interface supports keyboard operation, descriptive accessible names on key controls, visible focus styling and high-contrast interface text. Text can be translated in German, English and French. The slot color stripe is supplementary; status is also conveyed with a symbol and text.

For format-specific behavior and release limitations, see [Supported Formats](supported-formats.md) and [Known Limitations](known-limitations.md).
