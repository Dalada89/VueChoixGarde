# Product Requirements — VueChoixGarde

**Document type:** Software Requirements Specification (SRS)  
**Version:** 0.5 (draft for Version 1 of the product)  
**Product:** VueChoixGarde — a local desktop application for quickly reviewing images and sorting them into destination folders  
**Target platforms:** Linux, Windows and macOS  

## 1. Introduction

### 1.1 Purpose

VueChoixGarde lets users review a folder of images with the keyboard and copy selected images into themed destination folders, without looking up filenames or switching between file-manager windows.

Each destination is represented by a slot with its own key. Pressing a slot key copies the current image into that slot's destination folder; pressing it again removes that copy. The original image in the source folder is never changed.

### 1.2 Document conventions

- This document describes **what** the product must do. It deliberately does not prescribe a programming language, framework, library or storage format.
- Priorities: **MUST** = required for V1; **SHOULD** = important, may be deferred only by explicit decision; **COULD** = optional enhancement.
- Every requirement has a unique ID (`FR-…` functional, `NFR-…` non-functional) and is stated only once. Other sections refer to it by ID.
- Terms in the glossary (Section 2) are used with exactly the meaning defined there.

## 2. Glossary

| Term | Definition |
|---|---|
| Application data | Everything the application stores outside the image folders: global settings, global slot template, destination profiles and copy register. Stored locally in the operating system's usual per-user location. |
| Conflict file | A file in a destination folder whose name matches a file the application wants to create there (case-insensitive, see FR-033) and that is **not** a managed copy. A conflict file is never overwritten, modified or deleted. |
| Copy register | Part of the application data. For each managed copy it records: source folder, source filename, destination folder, destination filename, file size and content hash at the time of copying. |
| Current image | The image currently displayed in the main view. |
| Destination folder | A direct subfolder of the source folder into which a slot copies images. |
| Destination profile | The set of slots (key, destination folder name, color) that belongs to one source folder. |
| Global slot template | The slot configuration used to create the destination profile of a source folder that has no profile yet. |
| Image list | The sorted list of supported images found in the source folder when it was opened or last refreshed. |
| Managed copy | A file that the application itself created in a destination folder and recorded in the copy register. |
| Modified managed copy | A managed copy whose current size or content hash no longer matches the copy register (e.g. it was edited after copying). |
| Physical key position | The location of a key on the keyboard, independent of the character printed on it or produced by the active layout. |
| Progress | The position of the current image in the image list and the total number of images, e.g. “12 of 80”. |
| Reconciliation | Comparing the copy register with the files actually present in the destination folders and updating the register and the displayed status accordingly. Reconciliation never creates, changes or deletes image or sidecar files. |
| Selected (in a destination) | The current image has a verified managed copy in that slot's destination folder. |
| Sidecar file | A file in the source folder that belongs to an image according to the rules in FR-043. Sidecar files are copied and removed together with their image. |
| Slot | A configurable association of exactly one slot key, one destination folder name and one feedback color. |
| Slot key | The single key, without modifiers, that triggers a slot. |
| Source folder | The folder selected by the user that contains the images to review. |
| Supported image | A regular file at the top level of the source folder whose extension is on the fixed list in FR-004. |
| Toggle on / toggle off | Activating a slot for an image that is not selected / is selected in that slot's destination folder. |
| Verified managed copy | A managed copy that exists at the recorded path and whose size and content hash match the copy register. |

## 3. Product Scope

### 3.1 In scope for V1

- Open a source folder and review its supported images one at a time.
- Navigate with the keyboard; sort by filename in ascending or descending order.
- Up to 12 slots with configurable key, destination folder name and color; four default slots.
- Toggle a byte-identical copy of the current image (and its sidecar files) into a destination folder.
- Show which destinations contain the current image.
- Keep settings, destination profiles and selection status across restarts.
- Selectable user interface language: German, English, French.
- Help view with an overview of all keyboard shortcuts.
- Local JSONL log file.

### 3.2 Out of scope for V1

- Moving, renaming, modifying or deleting files in the source folder.
- Destination folders outside the source folder or nested deeper than one level.
- Image editing or changing image content or metadata.
- Zoom, 1:1 view, full-screen mode, slideshows and playback of animations.
- Recursive scanning of subfolders.
- RAW images and video files, neither as reviewable images nor as companion files copied together with an image (FR-043).
- Automatic detection of new or deleted source files while a folder is open (a manual refresh is provided).
- Cloud synchronization, accounts, network services and automatic updates.
- Automatic classification, rating, AI-based selection or duplicate detection.
- Trash/recycle bin integration and undo history (toggle-off deletes permanently; the original remains in the source folder).
- Code signing and notarization of release builds.

## 4. Users and Usage Context

**Users:** People who want to sort locally stored photos quickly into one or more selections. No technical knowledge is required.

**Context:** The application runs locally on a desktop computer. Users work primarily with the keyboard. Source folders typically contain photos from cameras and smartphones.

## 5. Functional Requirements

### 5.1 Source Folder and Image List

- **FR-001 — Select source folder (MUST):** Users MUST be able to select a source folder with the operating system's folder-selection dialog.
- **FR-002 — Validate source folder (MUST):** The application MUST check that the selected path exists, is a folder and is readable. Otherwise it MUST show an error (FR-090) and MUST NOT open the folder.
- **FR-003 — Top level only (MUST):** Only files directly in the source folder are considered. Subfolders, including destination folders, are never scanned.
- **FR-004 — Supported formats (MUST):** A file is a supported image only if its extension (compared case-insensitively) is on this fixed list:
  - MUST: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tif`, `.tiff`, `.webp`
  - Platform-dependent display: `.heic`, `.heif` — always part of the image list. On platforms where the application cannot decode them, they are handled as unreadable images (FR-023): instead of the image, an error MUST state that this format cannot be displayed on this platform (FR-090). Decoding HEIC/HEIF is not a release criterion for V1.

  All other files are silently ignored: they do not appear in the image list and do not count towards progress. The file content is not used to determine the format.
- **FR-005 — Ignored entries (MUST):** Hidden files (name starting with `.` or marked hidden by the operating system), folders and symbolic links/shortcuts whose target lies outside the source folder MUST be ignored.
- **FR-006 — Empty image list (MUST):** If the image list is empty, the application MUST show a clear empty state, and navigation and slot actions MUST be disabled.
- **FR-007 — Static image list and refresh (MUST):** The image list is built when the folder is opened. It MUST NOT change automatically while the folder is open. A manual refresh command (key `F5` and a visible control) MUST rebuild the image list; the current image MUST remain current if it still exists, otherwise the nearest following image becomes current.
- **FR-008 — Sorting (MUST):** The image list MUST be sorted by filename:
  - case-insensitive,
  - with natural number ordering (`IMG_2` before `IMG_10`),
  - deterministic: names that compare equal are ordered by their exact character sequence.
- **FR-009 — Sort direction (MUST):** A visible control MUST switch between ascending and descending order. After switching, the current image MUST remain current and its position in the progress display MUST be updated. The last chosen direction is a global setting (FR-060).
- **FR-010 — Last folder (SHOULD):** Users SHOULD be able to enable a setting that reopens the last source folder on start.

### 5.2 Image Display and Navigation

- **FR-020 — Display (MUST):** The current image MUST be scaled to fit the available display area while preserving its aspect ratio. Images smaller than the display area MUST NOT be enlarged beyond 100 %.
- **FR-021 — Orientation (MUST):** The image MUST be displayed rotated/mirrored according to its EXIF orientation tag, if present. The file itself MUST NOT be changed.
- **FR-022 — Multi-frame files (MUST):** For animated GIF/WebP and multi-page TIFF files, the first frame/page MUST be displayed as a still image.
- **FR-023 — Unreadable image (MUST):** If an image cannot be read or decoded, or has been removed since the image list was built, it MUST remain in the image list and a clear error MUST be displayed instead of the image. All other images MUST remain accessible. Slot actions MUST remain available for such an image; if the file is missing or cannot be read when copying, the operation fails with an error (FR-090) and nothing is created in the destination folder.
- **FR-024 — Next / previous (MUST):** The right arrow key MUST show the next image; the left arrow key MUST show the previous image (“next” and “previous” refer to the current sort direction).
- **FR-025 — List boundaries (MUST):** Navigation MUST stop at the first and last image; it does not wrap around. A subtle visual cue MUST indicate that the boundary has been reached.
- **FR-026 — Key repeat during navigation (MUST):** Holding an arrow key MUST continue navigating (keyboard auto-repeat). Images that are skipped quickly need not be fully rendered.
- **FR-027 — Filename (MUST):** The full filename of the current image MUST be visible. Long names MAY be shortened visually but the full name MUST be available (e.g. as tooltip).
- **FR-028 — Progress (MUST):** The application MUST show the position of the current image and the total number of images (e.g. “12 of 80”) as text and as a progress bar. The progress bar reflects the position only: navigating backwards moves it backwards.
- **FR-029 — Selection count (SHOULD):** The application SHOULD show how many images of the image list are selected in at least one destination.
- **FR-030 — Navigation has no side effects (MUST):** Navigating MUST NOT trigger any file operation.

### 5.3 Slots, Destination Profiles and Destination Folders

- **FR-031 — Default slots (MUST):** The global slot template MUST initially contain four slots whose keys are defined by the physical key positions of `W`, `A`, `S`, `D` on a US-QWERTY keyboard (FR-081). Each default slot has a distinct default color and no destination folder name.
- **FR-032 — Number of slots (MUST):** Users MUST be able to add and remove slots. A destination profile contains at least 1 and at most 12 slots.
- **FR-033 — Configure slot (MUST):** For each slot users MUST be able to set the slot key, the destination folder name and the feedback color. Within one profile:
  - slot keys MUST be unique,
  - destination folder names MUST be unique when compared case-insensitively and after Unicode normalization (`Best` and `best` are the same folder).
  
  Conflicts MUST be reported and MUST be resolved before saving.
- **FR-034 — Destination folder name rules (MUST):** A destination folder name MUST be rejected with an explanation if it is empty, consists only of spaces or dots, contains a path separator, is `.` or `..`, is absolute, contains characters not permitted on any of the target platforms (`< > : " / \ | ? *` and control characters), ends with a space or dot, or is a name reserved on Windows (e.g. `CON`, `NUL`, `COM1`). The same rules apply on all platforms so that profiles behave identically everywhere.
- **FR-035 — Name prompt on first use (MUST):** If a slot without a destination folder name is activated, the application MUST ask for a name. Cancelling MUST create neither a folder nor a copy. A confirmed name is saved in the destination profile.
- **FR-036 — Create destination folder (MUST):** When a slot is toggled on and its destination folder does not exist, the application MUST create it as a direct subfolder of the source folder. If a folder whose name differs only in case already exists, that folder MUST be used and no second folder created.
- **FR-037 — Existing destination folder (MUST):** An existing destination folder MUST be used without emptying, renaming or otherwise changing its existing contents.
- **FR-038 — Destination folder is not a folder (MUST):** If a file (not a folder) with the destination folder name exists, or the destination folder resolves to a location outside the source folder (symbolic link, junction, alias), the slot MUST be marked as faulty and no file operation MUST take place.
- **FR-039 — Empty destination folders remain (MUST):** A destination folder MUST NOT be deleted, even if it no longer contains any files after toggle-off.
- **FR-040 — Destination profile per source folder (MUST):** Each source folder has its own destination profile, identified by the source folder's absolute, normalized path. The active profile (source folder name and path) MUST be visible. A profile MUST never be applied to a different source folder automatically.
- **FR-041 — New source folder (MUST):** When a source folder without a profile is opened, a new profile MUST be created as a copy of the global slot template. Later changes to the template MUST NOT change existing profiles.
- **FR-042 — Manage template and profiles (MUST):** Users MUST be able to:
  - save the current profile's slots as the global slot template,
  - reset the global slot template to the default slots (FR-031),
  - reset the current profile to the global slot template,
  - assign an existing profile whose source folder no longer exists to the currently opened folder (for moved or renamed folders). This MUST happen only by explicit user choice; the copy register entries of that profile are then checked by reconciliation (FR-070).

### 5.4 Slot Toggle (Copy and Remove)

- **FR-043 — Sidecar files (MUST):** For an image `<stem>.<ext>`, the following files in the source folder are its sidecar files (extensions compared case-insensitively):
  - `<stem>.xmp`
  - `<stem>.<ext>.xmp` (e.g. `IMG_1.jpg.xmp`)
  - `<stem>.aae` (iPhone edit information)

  No other files are treated as sidecar files. In particular, RAW files (e.g. `.cr2`, `.nef`, `.arw`, `.dng`) and Live Photo videos (e.g. `.mov`) with the same stem are not sidecar files and are never copied. If several images share a stem (e.g. `IMG_1.jpg` and `IMG_1.png`), `<stem>.xmp` and `<stem>.aae` belong to each of them.
- **FR-044 — Toggle on (MUST):** Activating a slot for an image that is not selected in its destination folder MUST copy the image and all its sidecar files into the destination folder under their original filenames. The operation is a unit: if any of the target names is occupied by a conflict file (FR-047), no file MUST be copied and the conflict MUST be reported. A sidecar file that already exists in the destination as a verified managed copy (shared stem, FR-043) is not copied again.
- **FR-045 — Exact copy (MUST):** Every copy MUST be byte-identical to its source. Files MUST NOT be decoded and re-encoded. This preserves all embedded metadata (EXIF including capture date, camera settings and GPS location; IPTC; XMP).
- **FR-046 — Safe copy procedure (MUST):** Each file MUST first be written to a temporary file in the destination folder with a name reserved by the application, then its content hash MUST be compared with the source file, and only then MUST it receive its final name. Assigning the final name MUST NOT overwrite an existing file. If any step fails, the temporary file MUST be removed and all files of the operation already finalized MUST be removed again, so that no partial result remains. Temporary files left behind by an interrupted run MUST be removed at the next start only if the copy register identifies them as the application's own.
- **FR-047 — Conflict files (MUST):** Before creating a file, the application MUST check whether a file with the same name already exists in the destination folder (compared case-insensitively on all platforms). If that file is not a verified managed copy, it is a conflict file: it MUST NOT be overwritten, modified or deleted, and the application MUST name the conflict in a clear message.
- **FR-048 — Toggle off (MUST):** Activating a slot for an image that is selected in its destination folder MUST permanently delete the verified managed copy of the image and of its sidecar files from that destination folder (no trash, no confirmation). A sidecar copy shared by another image that is still selected in the same destination MUST be kept. The source files MUST remain unchanged.
- **FR-049 — Modified managed copies (MUST):** If, on toggle off, the copy of the image or of one of its sidecar files is a modified managed copy, the application MUST NOT delete anything automatically. It MUST show a dialog naming the affected file(s) and stating that the changes would be lost. Deletion MUST happen only after explicit confirmation; the default choice MUST be “Cancel”.
- **FR-050 — Check before every operation (MUST):** Before every toggle the application MUST check the actual state of the destination folder against the copy register. The decision between toggle on, toggle off and conflict MUST be based on this check, not on the stored status alone. Missing managed copies (e.g. deleted externally) MUST be removed from the copy register, and the image counts as not selected.
- **FR-051 — One operation at a time (MUST):** At most one file operation runs at a time. Slot activations while an operation is running MUST be ignored with brief feedback, not queued. Keyboard auto-repeat of a held slot key MUST be ignored, so that holding a key never toggles more than once.
- **FR-052 — Only the current image (MUST):** A slot action MUST apply only to the image that was current when the key was pressed. Navigating during an operation MUST NOT redirect it to another image.
- **FR-053 — Multiple destinations (MUST):** The same image MAY be selected in several destinations. An operation in one destination MUST NOT affect any other destination.
- **FR-054 — Stay on image (MUST):** After a slot action the current image MUST remain current; the application MUST NOT advance automatically.
- **FR-055 — File modification time (SHOULD):** Copies SHOULD keep the source file's modification time. Extended attributes, permissions, ownership, access control lists and other file-system metadata are explicitly not required to be preserved.
- **FR-056 — Success feedback (MUST):** After a successful toggle on or toggle off, the interface MUST briefly show which slot was affected and whether the image was added or removed, using the slot's color plus its key and destination name.
- **FR-057 — Sound (MUST):** After a successful toggle on, a short, subtle sound MUST play. Users MUST be able to switch it off. No sound MUST play after toggle off, a conflict, a cancelled action or an error.
- **FR-058 — Failed operations (MUST):** Failures (e.g. missing permission, insufficient space, file in use) MUST be reported (FR-090). The interface MUST NOT indicate success, the copy register MUST reflect the actual state, and the user MUST be able to continue working.

### 5.5 Settings and Application Data

- **FR-060 — Global settings (MUST):** The following MUST be stored as global settings and persist across restarts: user interface language, sound on/off, sort direction, reopen last folder (FR-010), global slot template.
- **FR-061 — Profiles and copy register (MUST):** Destination profiles and the copy register MUST persist across restarts. They MUST be stored only in the application data, never in the source or destination folders.
- **FR-062 — First start (MUST):** If no application data exists, the application MUST create it with default values without asking.
- **FR-063 — Damaged application data (MUST):** If application data exists but cannot be read, the application MUST NOT overwrite or delete it. It MUST report the problem and offer to continue with default values; the damaged data MUST then be kept under a different name. As long as the copy register is unavailable, no toggle off MUST be possible (all same-name destination files are treated as conflict files).
- **FR-064 — Settings dialog (MUST):** All settings in FR-033 and FR-060 MUST be editable in a settings dialog. Changes take effect immediately after saving.

### 5.6 Selection Status and Reconciliation

- **FR-070 — Reconciliation (MUST):** Reconciliation MUST run automatically when a source folder is opened and MUST be available as a manual command. It MUST:
  - remove copy register entries whose file no longer exists,
  - mark modified managed copies as such,
  - leave all files in the source and destination folders untouched.
- **FR-071 — Adopt existing files (COULD):** Reconciliation COULD offer to record files in a destination folder that are byte-identical to a source image or sidecar file as managed copies. This MUST happen only after explicit user confirmation, listing the files concerned.
- **FR-072 — Selection indicator (MUST):** If the current image is selected in at least one destination, a star (or equivalent symbol) MUST be shown. For every slot the interface MUST show whether the current image is selected in its destination. Indicators MUST NOT cover the central image area and MUST NOT be written into any file.
- **FR-073 — Slot states (MUST):** For each slot, the interface MUST distinguish these states for the current image, not by color alone: *no destination name*, *ready*, *selected*, *modified copy*, *conflict*, *faulty* (FR-038).

### 5.7 Keyboard

- **FR-080 — Keyboard-only operation (MUST):** Navigation, slot actions, refresh and help MUST be usable without a mouse while the main window has focus.
- **FR-081 — Physical key positions (MUST):** Slot keys MUST be stored and recognized by physical key position. The interface MUST display the character that the active keyboard layout produces for that position (e.g. `Z Q S D` on AZERTY for the default slots).
- **FR-082 — Allowed slot keys (MUST):** A slot key MUST be a single key of the main character block (letters, digits, punctuation) pressed without any modifier. Key presses with Shift, Ctrl, Alt, AltGr, Cmd/Win or similar modifiers MUST NOT trigger a slot. The following keys are reserved and cannot be slot keys: arrow keys, `F1`–`F12`, `Esc`, `Enter`, `Tab`, `Space`, `Backspace`, `Delete` and modifier keys.
- **FR-083 — Fixed application keys (MUST):** `→` next image, `←` previous image, `F1` help and shortcut overview, `F5` refresh image list, `Esc` close dialog/overlay.
- **FR-084 — Text input and dialogs (MUST):** While a text field has focus or a dialog is open, slot keys and navigation keys MUST NOT trigger their actions in the main view.

### 5.8 User Interface, Help and Language

- **FR-085 — Language (MUST):** The user interface MUST be available in German, English and French and the language MUST be selectable in the settings. On first start the operating system language MUST be used if it is one of these, otherwise English.
- **FR-086 — Help and shortcut overview (MUST):** `F1` and a visible control MUST open a help view that lists all application keys and the current slot keys with their destination names and colors, and briefly explains the toggle behavior and that source files are never changed.
- **FR-087 — Slot bar (MUST):** All slots of the active profile MUST be visible during review in a compact bar outside the central image area, each with key, destination name, color and state (FR-073). With up to 12 slots no slot may be hidden.
- **FR-088 — Appearance (SHOULD):** The interface SHOULD use a modern, flat dark design:
  - dark grey background around the image (approx. `#2B2B2B`), slightly lighter panels (approx. `#383838`), light grey text,
  - a single accent color for controls; slot colors are used only for slot-related elements,
  - the operating system's standard sans-serif font, slightly rounded corners, no decorative effects that distract from the image.

### 5.9 Errors and Logging

- **FR-090 — Error messages (MUST):** Error messages MUST state in plain language what happened, which file or folder is affected and, where possible, what the user can do. Technical details MAY be shown on request. Errors MUST NOT terminate the application.
- **FR-091 — Log file (MUST):** The application MUST write a local log file in JSON Lines format (one JSON object per line) in the application data. Each entry MUST contain at least timestamp (ISO 8601), level, event type and message. Logged events include: start/end, folder opened, every file operation with its result, conflicts, reconciliation results and errors.
- **FR-092 — Log limits (MUST):** The log MUST NOT contain image content or image metadata (e.g. GPS coordinates). Log files MUST be limited in size and rotated (e.g. at most 5 files of 10 MB each). The settings or help view MUST offer a way to open the log folder.

## 6. Non-functional Requirements

### 6.1 Data Safety and Privacy

- **NFR-001 — Permitted file operations (MUST):** The application MUST perform no write operation on the file system other than:

  | Location | Permitted operation |
  |---|---|
  | Source folder | Create a destination folder (FR-036). Nothing else. |
  | Destination folder | Create temporary files and managed copies (FR-046); delete own temporary files and managed copies (FR-046, FR-048, FR-049). |
  | Application data | Read and write application data and log files. |

  In particular, files in the source folder MUST never be modified, moved, renamed or deleted, and no file outside the source folder and the application data MUST be changed.
- **NFR-002 — Stay inside the source folder (MUST):** Every path the application writes to MUST, after resolving symbolic links, junctions and aliases, lie inside the source folder (or the application data). Paths that resolve to a location outside MUST be rejected.
- **NFR-003 — No deletion without verification (MUST):** A file MUST be deleted only if it is a verified managed copy (FR-048) or after explicit confirmation as a modified managed copy (FR-049). Uncertainty about a file's status MUST never be treated as permission to delete or overwrite.
- **NFR-004 — UI effects are not persisted (MUST):** Scaling, rotation, color feedback, stars and other indicators exist only in the interface and MUST NOT be written into any image file.
- **NFR-005 — Local only (MUST):** The application MUST NOT send images, metadata, settings or logs over the network.

### 6.2 Performance

The following values are targets. They are verified on the developer's own computer; no formal reference hardware is defined for V1.

- **NFR-010 — Image change (SHOULD):** On a local drive, the next image SHOULD be displayed within 500 ms for JPEG files up to 20 MB. Preloading neighboring images is permitted.
- **NFR-011 — Folder size (SHOULD):** A source folder with 10,000 supported images SHOULD open and be navigable; the image list SHOULD be available within 5 s on a local drive.
- **NFR-012 — Responsiveness (MUST):** The interface MUST remain responsive while images are loaded and files are copied. Operations taking longer than about 1 s MUST show a busy indicator.
- **NFR-013 — Memory (SHOULD):** Memory use SHOULD NOT grow with the number of images viewed; decoded images not needed for display SHOULD be released.
- **NFR-014 — Network drives (SHOULD):** Network drives and removable media are not an explicit target for V1. Source folders on such drives SHOULD work; slow or lost connections MUST lead to error messages, not to data loss or a crash.

### 6.3 Usability and Accessibility

- **NFR-020 — Learnability (design goal):** The basic workflow (open folder, navigate, toggle slot) should be understandable without documentation, using the help view (FR-086). This is not formally tested.
- **NFR-021 — Not color alone (MUST):** Slot identity, selection status and slot states MUST be recognizable without color perception (key, name, symbol or text in addition to color).
- **NFR-022 — Legibility (MUST):** Text MUST have a contrast ratio of at least 4.5:1 against its background.
- **NFR-023 — Focus (MUST):** The element with keyboard focus MUST be visibly marked.

### 6.4 Maintainability and Quality

- **NFR-030 — Separation (MUST):** User interface, application logic, application data storage and file access MUST be separated so that the application logic can be tested automatically without a visible window and without real user images.
- **NFR-031 — Extensibility (SHOULD):** Additional image formats and sidecar rules SHOULD be addable by extending the fixed lists (FR-004, FR-043) without restructuring.
- **NFR-032 — Documentation (MUST):** Installation, usage, settings, supported formats (including on which platforms HEIC/HEIF is supported), keyboard shortcuts, test execution and known limitations MUST be documented in the repository.

### 6.5 Compatibility and Distribution

- **NFR-040 — Platforms (MUST):** All functional requirements MUST behave identically on Linux, Windows and macOS, in particular path handling, case-insensitive name comparison, key handling and application data location. The only permitted difference is the platform-dependent format support in FR-004. Minimum operating system versions are determined by the chosen implementation and MUST be documented, not prescribed here.
- **NFR-041 — Filenames (MUST):** Unicode filenames MUST be supported as far as the file system permits. Names MUST be compared after Unicode normalization.
- **NFR-042 — Robustness (MUST):** A single unreadable image or a single failed operation MUST NOT prevent working with the remaining images.
- **NFR-043 — Single instance per folder (MUST):** If a source folder is already open in another instance of the application, opening it again MUST be refused with a message. The lock MUST NOT be stored in the source folder.
- **NFR-044 — Distribution (MUST):** Releases are published as downloads on the project's GitHub page. V1 has no built-in update mechanism. Releases are not code-signed; the documentation MUST explain how to open an unsigned application on each platform.

## 7. Acceptance Criteria

V1 is accepted when all of the following pass on Linux, Windows and macOS:

1. Only files on the fixed format list appear in the image list; other files, hidden files, subfolders and symbolic links pointing outside are ignored (FR-003–FR-005). HEIC/HEIF files are always listed; where they cannot be decoded, an error is shown instead of the image (FR-004, FR-023).
2. Sorting is case-insensitive and natural (`IMG_2` before `IMG_10`); switching direction keeps the current image and updates progress (FR-008, FR-009).
3. `→` shows the next and `←` the previous image; navigation stops at both ends; the progress bar follows the position (FR-024, FR-025, FR-028).
4. Images are displayed according to their EXIF orientation; unreadable images show an error, can be skipped and can still be toggled in a slot (FR-021, FR-023).
5. An unnamed slot asks for a name; cancelling creates neither folder nor copy (FR-035).
6. `Best` and `best` are treated as the same destination folder; invalid names are rejected (FR-033, FR-034, FR-036).
7. Toggle on creates byte-identical copies of the image and its sidecar files, including all EXIF/IPTC/XMP data; source files are unchanged (FR-043–FR-046).
8. Toggle off deletes exactly the verified managed copies from that destination; source files, other destinations and the (possibly empty) destination folder remain (FR-039, FR-048, FR-053).
9. A modified managed copy is deleted only after explicit confirmation; cancelling leaves it unchanged (FR-049).
10. A pre-existing same-name file in the destination is never overwritten or deleted and is reported as a conflict, also when the names differ only in case (FR-047).
11. An interrupted copy leaves no partial files (FR-046).
12. Holding a slot key toggles exactly once; activations during a running operation are ignored (FR-051).
13. Selection status is restored after restart; externally deleted copies are recognized as not selected (FR-050, FR-061, FR-070).
14. Default slot keys are at the physical positions of `W A S D` and are labeled according to the active layout; slot keys with modifiers do not trigger (FR-031, FR-081, FR-082).
15. A new source folder receives the global slot template; another folder's profile is never applied automatically (FR-040, FR-041).
16. The sound plays only after a successful toggle on and can be switched off (FR-057).
17. Language can be switched between German, English and French; `F1` shows all shortcuts (FR-085, FR-086).
18. Missing application data is created on first start; damaged application data is kept and does not lead to deletions (FR-062, FR-063).
19. No path outside the source folder and the application data is written, including via symbolic links (NFR-001, NFR-002).
20. The log is valid JSON Lines and contains no image metadata (FR-091, FR-092).

## 8. Test Requirements

- **Unit tests:** format filter, sidecar matching (FR-043, including shared stems and case variants), natural case-insensitive sorting in both directions, navigation and boundaries, slot and name validation, key conflict detection, profile/template handling, decision logic for toggle on / toggle off / conflict / modified copy.
- **Integration tests with temporary folders:** byte-identical copying including EXIF camera, capture date and GPS fields; safe copy procedure with simulated failures; toggle off; shared sidecar copies; conflict protection with case variants; symbolic links pointing outside; externally deleted or modified copies; reconciliation without file changes; damaged and missing application data; source folder unchanged after every test (checked by content hashes).
- **Manual tests per platform:** keyboard layouts (at least QWERTY, QWERTZ, AZERTY), key repeat, focus in text fields, all formats including HEIC where supported, EXIF orientation, sound, languages, help view, appearance.
- Automated tests MUST use generated or bundled test images, never the user's personal images.

## 9. Open Decisions

There are currently no open decisions.

## 10. Change History

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-15 | Initial structured requirements draft. |
| 0.2 | 2026-10-15 | Added extensible slots, persistent settings, sorting direction, selection indicators, optional sound, common image formats and Linux/Windows/macOS support. |
| 0.3 | 2026-10-15 | Clarified source-file protection, byte-identical copying, embedded metadata preservation, per-source-folder profiles, per-destination status and non-destructive metadata reconciliation. |
| 0.4 | 2026-10-16 | Replaced copy-only behavior with a per-slot toggle: first activation copies the image and matching sidecars; second activation removes only verified managed copies. |
| 0.5 | 2026-10-16 | HEIC/HEIF always listed; on platforms without decoding support an error is shown instead of the image (FR-004); slot actions stay available for undisplayable images (FR-023). Review results incorporated: glossary with managed/verified/modified copies, copy register and sidecar rules; navigation corrected (→ next, ← previous); permanent deletion on toggle off, confirmation for modified copies; safe copy procedure; one operation at a time; case-insensitive destination names; symbolic links pointing outside rejected; EXIF orientation; maximum of 12 slots; global slot template; physical key positions, unmodified slot keys; HEIC/HEIF platform-dependent and not a release criterion; RAW files and Live Photo videos are not copied as companion files; UI languages DE/EN/FR; help and shortcut overview; JSONL logging; dark design; GitHub distribution; decided items removed; restructured to remove redundancies and technology-specific statements. |
