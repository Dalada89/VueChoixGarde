# Product Requirements — VueChoixGarde

**Document type:** Software Requirements Specification (SRS)  
**Status:** Draft for Version 1 (V1)  
**Product:** VueChoixGarde — a local desktop application for quickly reviewing and sorting images into destination folders  
**Target platforms:** Linux, Windows and macOS  

## 1. Purpose and Objectives

The application simplifies reviewing a collection of images and copying selected images into themed destination folders. Users browse images in a continuous view using the keyboard, without looking up filenames or switching between file-manager windows.

The application provides four default destination slots (`W`, `A`, `S`, `D`) and allows additional slots. Each slot has a keyboard shortcut, destination folder and configurable visual color. All slots behave identically apart from those settings. Slot actions are a destination-only toggle: the first activation copies the current image and its matching sidecar files into that slot's destination; activating the same slot again removes those copies from that destination. The application MUST NEVER delete, move, rename or modify any source-folder file. It MUST NOT overwrite or remove unrelated/pre-existing destination files.

Image files MUST be copied as-is, byte for byte, rather than opened and re-encoded. This preserves embedded camera and location metadata such as EXIF, IPTC and XMP data.

## 2. Definitions

| Term | Definition |
|---|---|
| Source folder | The folder selected by the user that contains images to review. |
| Destination folder | A folder to which selected images are copied. In V1, destinations are children of the source folder. |
| Destination slot | A configurable association between a unique keyboard shortcut, destination folder/name and visual feedback color. |
| Current image | The image currently displayed in the main view. |
| Selected image | An image that currently has an application-managed copy in one or more configured destination folders. |
| Embedded image metadata | Information stored inside an image file, including camera settings and, where present, GPS/location information (e.g. EXIF, IPTC, XMP). |
| Supported image | A regular file in a supported raster format that the application can display. |
| Progress | The current image's position in the ordered image list and total number of images, e.g. “12 of 80”. |

## 3. Product Scope

### 3.1 In scope for V1

- Select a source folder and review its images in a main view.
- Navigate with the left/right arrow keys; left means next and right means previous.
- Display the current filename and position/total count with a progress bar.
- Provide four default destination slots (`W`, `A`, `S`, `D`) and allow additional slots.
- Configure each slot's shortcut, destination folder name and visual feedback color.
- Persist global preferences and source-folder-specific destination profiles across launches.
- Preconfigure destination folder names; create the configured folder on first use if necessary.
- Toggle an image's application-managed copy in a destination: create it on first activation and remove it on the next activation.
- Never change source files; protect unrelated or unrecognized destination files from removal or replacement.
- Allow the same image to be copied into multiple destinations.
- Show a star and per-destination status for selected images.
- Allow the short copy sound to be disabled.
- Support JPEG/JPG, PNG, GIF, BMP, TIFF and WebP; exclude RAW images and video.
- Run on Linux, Windows and macOS.
- Provide a non-destructive way to reconcile stored selection status with files found in destination folders.

### 3.2 Out of scope for V1

- Moving, deleting or renaming source files from the application. Destination deletion is limited to removing this application's managed copies as the inverse of the slot toggle.
- Image editing, color correction or modification of image content or metadata.
- Cloud synchronization, accounts or network services.
- Automatic classification, AI-based selection, rating or duplicate detection.
- RAW image and video support.

## 4. User Groups and Usage Context

**Primary users:** People who want to review locally stored images quickly and assemble selections in one or more destination folders.

**Usage context:** The application runs locally on the user's computer. Users select a folder containing images and operate the application primarily with the keyboard. The interface should be understandable without technical knowledge.

## 5. Functional Requirements

Priorities: **MUST** = required for V1; **SHOULD** = important, but may be deferred only by explicit agreement; **COULD** = optional enhancement.

### 5.1 Startup and Source Folder

- **FR-001 — Select source folder (MUST):** The system MUST allow users to select a local folder using a folder-selection dialog.
- **FR-002 — Validate folder (MUST):** The system MUST check that the selected path exists, is a directory and is readable. An invalid or inaccessible path MUST produce a clear error, not a crash.
- **FR-003 — Detect image files (MUST):** The system MUST detect supported image files in the selected source folder. V1 searches only the top level and does not search subfolders recursively.
- **FR-004 — Exclude destinations (MUST):** Configured destination folders and their contents MUST NOT appear as source images in the current review session.
- **FR-005 — Empty folder (MUST):** If no supported images are found, the application MUST show a clear empty state and disable navigation and copy actions.
- **FR-006 — Filename ordering (MUST):** Images MUST be sorted by filename. The user MUST be able to choose ascending or descending order; the list and progress position MUST update accordingly. Comparison MUST be deterministic and case-insensitive. Whether digit sequences sort naturally (e.g. `IMG_2` before `IMG_10`) is an open refinement (Section 12).

### 5.2 Image Display and Navigation

- **FR-010 — Display image (MUST):** The system MUST scale the current image proportionally to fit the available display area, preserve its aspect ratio and MUST NOT modify the file.
- **FR-011 — Decode errors (MUST):** If a file cannot be decoded, its entry MUST remain in the navigation list and a clear error MUST be displayed in place of the image. Other images must remain accessible.
- **FR-012 — Next image (MUST):** The left arrow key MUST move to the next image.
- **FR-013 — Previous image (MUST):** The right arrow key MUST move to the previous image.
- **FR-014 — Navigation boundaries (MUST):** Boundary behavior MUST be consistent. V1 SHOULD stop at the beginning/end rather than wrap around; confirm in Section 12.
- **FR-015 — Filename (MUST):** The full filename of the current item MUST be visible.
- **FR-016 — Progress display (MUST):** The application MUST show current position and total count (e.g. “12 of 80”) and provide a visual progress bar.
- **FR-017 — Update on navigation (MUST):** Progress and selection indicators MUST update whenever the current image changes. Navigation MUST NOT trigger a copy action.
- **FR-018 — Sort direction (MUST):** A clearly visible control or menu item MUST switch between ascending and descending filename order.

### 5.3 Destination Slots, Settings and Shortcuts

- **FR-020 — Default slots (MUST):** The application MUST provide four destination slots by default, assigned to `W`, `A`, `S` and `D`.
- **FR-021 — Additional slots (MUST):** Users MUST be able to add slots beyond the four defaults. A documented safe maximum or practical limit MUST be defined.
- **FR-022 — Consistent slot behavior (MUST):** All slots MUST have the same destination-toggle behavior. A slot differs only in shortcut, destination and visual feedback color.
- **FR-023 — Configure slot (MUST):** Settings MUST allow users to configure each slot's shortcut, destination folder name and visual feedback color.
- **FR-024 — Preconfigure destination (MUST):** Users MUST be able to enter a destination folder name in settings before first use. Activating the slot MUST create that folder if it does not exist and copy the image there without another name prompt.
- **FR-025 — First-use name prompt (MUST):** If a slot has no destination name configured, first activation MUST prompt for a name. After setup, the association MUST be saved in that source folder's profile.
- **FR-026 — Existing destination folder (MUST):** If the configured destination folder already exists, the application MUST use it without deleting, emptying or changing its contents.
- **FR-027 — Invalid names (MUST):** Empty names and names that could address a path outside the source folder (e.g. absolute paths, `..` traversal or path separators) MUST be rejected with an explanation. V1 destinations are children of the selected source folder.
- **FR-028 — Shortcut reassignment (MUST):** Users MUST be able to assign and change shortcuts in settings. One shortcut MUST NOT be assigned to multiple actions. Conflicts MUST be reported and resolved before saving.
- **FR-029 — Allowed shortcuts (SHOULD):** The application SHOULD allow single unmodified keys suitable for shortcuts while reserving navigation arrows and keys required for text entry or system/dialog operation. The permitted key set MUST be validated on all target operating systems.
- **FR-030 — Visible assignments (MUST):** The shortcut, destination name and chosen color for each slot MUST be visible during review. The UI MUST remain understandable with many slots; see Section 12.
- **FR-031 — Persistent settings (MUST):** Slot count, shortcut assignments, destination names, colors, sound preference and sort direction MUST persist across launches. Users MUST be able to edit or reset settings.
- **FR-032 — Global and per-folder settings (MUST):** Global preferences (e.g. sound and default sort direction) MUST be stored separately from destination profiles. Destination slots MUST be associated with the relevant source-folder profile so that settings for one source folder are not accidentally applied to another. The active profile MUST be visible.
- **FR-033 — Safe profile handling (MUST):** If a source folder is moved or its path changes, the application MUST NOT silently apply another folder's destinations. It MUST let the user select or reconfigure the appropriate profile.

### 5.4 Slot Toggle and Destination Conflict Handling

- **FR-040 — Destination-only toggle (MUST):** On first activation, a slot MUST copy the current image and its matching sidecar files into its configured destination. On a subsequent activation of the same slot while that image is selected there, the application MUST remove the application's managed copies of that image and its matching sidecars from that destination. The source folder and every file in it MUST remain present and unchanged in both cases. This removal MUST be limited to the selected image's managed destination copies; unrelated destination files MUST NOT be removed.
- **FR-041 — Exact file copy (MUST):** The application MUST copy the original file bytes directly; it MUST NOT decode and re-encode the image as part of copying. This MUST preserve embedded metadata, including camera and GPS/location metadata, along with all other embedded metadata and the original image data.
- **FR-042 — Current image only (MUST):** A slot action MUST apply only to the image that is current when the action is triggered.
- **FR-043 — Multiple destinations (MUST):** The same image MUST be copyable into multiple destination folders. Copying it to one destination MUST NOT affect copies in any other destination.
- **FR-044 — Toggle existing selection (MUST):** If the current image has a verified application-managed copy in the slot's destination, activating the slot MUST remove that copy and any verified matching sidecar copies from that destination, then update selection status. It MUST NOT report this as a duplicate no-op.
- **FR-045 — Protect destination conflicts (MUST):** A same-name destination file that is not verified as this application's managed copy MUST be treated as a conflict. It MUST NOT be overwritten, modified or deleted. The application MUST report the conflict clearly and MUST NOT mistake it for a selected copy eligible for removal.
- **FR-046 — Copy errors (MUST):** Permission, disk-space and other I/O failures MUST be reported clearly. The source MUST remain untouched, the UI MUST NOT indicate success, and the user MUST be able to continue.
- **FR-047 — Copy feedback (MUST):** After a successful copy, the interface MUST briefly identify the slot/action. Feedback MUST be a UI effect only and MUST NOT alter the image or its metadata.
- **FR-048 — Slot color (MUST):** Users MUST be able to choose a visual feedback color for each slot. Each cue MUST also identify the slot by name or shortcut; color alone is insufficient.
- **FR-049 — Sound (MUST):** A brief, subtle “pling” MUST play after a successful copy by default. Users MUST be able to disable it in settings. No success sound may play when no copy occurred or an operation failed.
- **FR-050 — Star and per-destination status (MUST):** The current image MUST show a star or equivalent indicator if a copy exists in at least one configured destination. The UI MUST identify exactly which destination(s) contain a copy. The indicator MUST NOT obscure important image content or be applied to the image file.
- **FR-051 — Stay on current image (MUST):** A copy action MUST leave the current image selected; the application MUST NOT automatically advance.
- **FR-052 — Toggle off (MUST):** If a slot is activated again while the current image is selected in that destination, the application MUST remove the verified application-managed destination copy and matching sidecar copies, preserve the source files, and update the UI to show that the image is no longer selected there.

### 5.5 Selection Metadata Reconciliation and Error Communication

- **FR-060 — Persist selection status (MUST):** The application MUST store enough local metadata to restore per-image/per-destination status after restart. This application metadata MUST NOT contain image content and MUST remain local.
- **FR-061 — Reconcile status (MUST):** Users MUST have a non-destructive way to rescan configured destination folders and reconcile stored selection status with files actually present. Reconciliation MAY update application metadata and indicators only; it MUST NOT create, replace, rename or delete image files.
- **FR-062 — Uncertain metadata (MUST):** If settings or selection metadata are missing, corrupt or ambiguous, the application MUST fail safely, report the issue and leave all source and destination image files untouched. It MUST NOT infer permission to delete or overwrite files.
- **FR-063 — Keyboard operation (MUST):** Navigation and slots MUST work without a mouse while the main window is active. Text fields MUST accept normal typing without triggering slot shortcuts.
- **FR-064 — Clear errors (MUST):** Errors MUST explain the cause in plain language and, where possible, suggest a next step.
- **FR-065 — Clear slot state (MUST):** The UI MUST distinguish a slot that is unconfigured, ready, already contains the current image, or has encountered an error.
- **FR-066 — Cross-platform behavior (MUST):** Core workflows, settings, supported formats and file-safety behavior MUST work consistently on Linux, Windows and macOS. Differences in paths, case sensitivity, permissions and keyboard shortcuts MUST be handled and tested.

## 6. Non-functional Requirements

### 6.1 Data Safety, Image Integrity and Privacy

- **NFR-001:** The application MUST never modify, move, rename or delete a source-folder file, including images and sidecars.
- **NFR-002:** The application MUST NOT overwrite, modify, move or rename destination files. It may delete only verified application-managed copies of the current image and its matching sidecars when the user toggles that slot off. All unrelated or unrecognized destination files MUST remain untouched.
- **NFR-003:** Copies MUST be byte-identical to their source. This is the primary guarantee that embedded EXIF/IPTC/XMP, camera settings, GPS/location information and image data are preserved.
- **NFR-004:** Display scaling, color feedback, stars and other UI effects MUST occur only in memory/UI and MUST NOT be written into copied or source image files.
- **NFR-005:** Destination names MUST NOT permit writes outside the selected source folder.
- **NFR-006:** Image processing, application metadata and settings MUST remain local. V1 MUST NOT send images, image metadata or settings to external services.
- **NFR-007:** If an application metadata inconsistency makes a file's status uncertain, the application MUST report uncertainty and leave all image files untouched.

### 6.2 Performance and Responsiveness

- **NFR-010:** On agreed reference hardware, the next image should appear within 500 ms for files up to 20 MB in a representative local collection. Hardware and test conditions must be defined before acceptance.
- **NFR-011:** The window MUST NOT remain blocked during image loading or copying. Longer operations should show a visible busy state.
- **NFR-012:** Large images should be scaled efficiently for display; original files MUST NOT be re-encoded.

### 6.3 Usability and Accessibility

- **NFR-020:** The primary workflow must be discoverable and usable without prior training.
- **NFR-021:** Slot identity MUST NOT rely on color alone; name or shortcut must also be visible.
- **NFR-022:** Keyboard focus and dialogs must be clear. Text entry MUST NOT trigger global slot shortcuts.
- **NFR-023:** The star, per-destination status and slot toggle/conflict feedback must be distinguishable without color perception.
- **NFR-024:** Text and contrast must be legible at a typical desktop window size.

### 6.4 Maintainability and Quality

- **NFR-030:** UI, application logic, settings/metadata persistence and file/image access MUST be organized in separate modules.
- **NFR-031:** Business logic MUST be automatically testable without real user images or a visible desktop.
- **NFR-032:** Additional slots, settings and supported formats should be extendable without major restructuring.
- **NFR-033:** Installation, startup, usage, settings, supported formats, test execution and known limitations must be documented for all target platforms.

### 6.5 Reliability and Compatibility

- **NFR-040:** A corrupt individual image MUST NOT prevent review of the remaining images.
- **NFR-041:** Unicode filenames MUST be supported where the underlying file system permits.
- **NFR-042:** JPEG/JPG, PNG, GIF, BMP, TIFF and WebP MUST be listed and tested on all supported platforms. RAW and video files are not supported.
- **NFR-043:** Settings and selection metadata MUST be stored in an OS-appropriate user configuration location and survive normal application restarts. Corrupt metadata MUST fail safely without modifying image files.

## 7. Data and Rules

- V1 supports JPEG/JPG, PNG, GIF, BMP, TIFF and WebP raster images. RAW and video files are excluded.
- Only files at the top level of the selected source folder are listed; subfolders are not searched recursively.
- Destination folders are children of the source folder and excluded from the source image list.
- The application copies files byte for byte and retains the original filename. It does not rewrite image contents or metadata.
- Embedded metadata (including EXIF camera and GPS/location fields, IPTC and XMP data) is preserved because the original file bytes are copied without re-encoding.
- Application settings and selection metadata are separate from image files. Selection metadata records which source image has a copy in which destination; it does not contain image content.
- Each slot is a toggle for the current image in that slot's destination: first activation copies it; the next activation removes the verified application-managed destination copy. Other slots and destinations are unaffected.
- The source image and all matching sidecar files in the source folder are immutable and are never deleted, moved, renamed or modified.
- A matching sidecar is a file in the source folder whose filename stem is exactly the image's stem and whose suffix/extension differs from the image's suffix/extension (for example, `Bild_1.xmp` alongside `Bild_1.jpg`). Matching sidecars are copied with the image and removed from that destination when toggled off.
- An unrecognized same-name destination file is a conflict, not permission to overwrite or remove it. The application MUST verify that destination files are managed copies before removal.

## 8. V1 User Workflow

1. The user opens a source folder. The application loads its source-folder profile, if one exists.
2. The application displays the first image in filename order with filename, progress, destination slots and per-destination selection status.
3. The user can choose ascending or descending filename order.
4. The user navigates with left (next) and right (previous).
5. In settings, the user configures slots: shortcut, destination folder name and visual color. Global preferences such as sound are separate. These settings persist between launches and destination profiles are associated with the source folder.
6. If a slot has no configured folder name, first activation prompts for one. Otherwise, the configured destination is created on first use if necessary.
7. If the current image is not selected in the slot's destination and no conflict exists, the application copies the image and matching sidecars byte-for-byte, updates local selection status and gives brief feedback; the “pling” plays if enabled.
8. If the current image is already selected in that destination, activating the same slot removes only its verified managed image and sidecar copies from that destination, updates status and gives clear feedback. The source files remain untouched.
9. A star indicates that the image exists in at least one destination; the slot display shows exactly which destinations contain it.
10. If metadata is inconsistent, reconciliation may update status only; it MUST NOT remove files. The application MUST fail safely and require sufficient verification before a toggle-off operation can delete a destination copy.

## 9. Acceptance Criteria

V1 is acceptable when at least the following scenarios pass:

1. Core workflows operate on Linux, Windows and macOS.
2. A folder with supported images displays a stable filename order; ascending/descending changes order and progress correctly.
3. Left moves to next and right to previous; boundary behavior matches the agreed rule.
4. An unconfigured slot prompts for a destination name; cancellation creates neither a folder nor a copy.
5. A preconfigured slot creates its destination folder on first use if necessary, without asking for the name again.
6. The first activation creates byte-identical copies of the image and all matching sidecar files; all source files remain present and unchanged.
7. Embedded camera and location metadata (where present), EXIF/IPTC/XMP data and image bytes are identical in source and copy; matching sidecars are also copied byte-for-byte.
8. Activating the same slot again removes the verified managed copies of the image and matching sidecars from that destination only; all source files and files in other destinations remain untouched.
9. Same-name pre-existing or untracked destination files remain untouched and produce a clear conflict notice; they are never treated as eligible for toggle-off deletion.
10. The same image can be copied into several destinations; each destination status is shown independently.
11. The star and per-destination statuses are restored after restart and can be non-destructively reconciled with actual destination contents.
12. Added slots have unique shortcuts and user-selected colors; color is not the only way to identify a slot.
13. The default copy sound plays after success and can be disabled; no success sound plays when no copy occurred or an operation failed.
14. JPEG/JPG, PNG, GIF, BMP, TIFF and WebP pass tests on all three platforms; RAW and video files are ignored.
15. Invalid names, unreadable images, missing permissions and corrupt settings/metadata fail safely without crashing or changing image files.
16. Automated tests use temporary test data and do not require the user's personal images.

## 10. Test Requirements

- Unit tests: image filtering and filename sorting in both directions, navigation, slot configuration, shortcut conflicts, destination-name validation, progress and per-folder profile behavior.
- Integration tests using temporary folders: create destination, byte-for-byte copy and toggle-off deletion, matching sidecar handling, multiple destinations, collision protection, source-file immutability, path-traversal rejection and settings persistence.
- Metadata tests MUST include files with representative EXIF camera fields and GPS/location fields, and verify byte-for-byte identity after copy. Sidecar tests MUST cover same-stem/different-extension matching and ensure unrelated stems are not copied or deleted.
- Reconciliation tests MUST verify metadata/status recovery without creating, replacing, renaming or deleting any image file, including when metadata is missing or corrupt.
- UI tests: settings workflows, slot toggle-on/toggle-off, star/per-destination status, destination conflict notice, keyboard focus, sound preference and error messages, where stable in the test environment.
- Cross-platform verification: automated checks and manual smoke tests on Linux, Windows and macOS; at minimum cover path handling, permissions, key bindings and settings storage.
- Manual acceptance: different image formats, large images, text entry, colors, selection indicators, sound on/off, toggle-on/toggle-off behavior and destination conflict handling.

## 11. Assumptions

- The application is local-first and supports Linux, Windows and macOS.
- The source folder is strictly immutable. Destination copies are toggleable: the application may delete only verified copies it manages in the selected destination, as the inverse of copying; unrelated destination files are protected.
- Destination folders are created inside the selected source folder.
- Four default slots are provided; users can add more.
- Each slot has its own shortcut, destination name and configurable visual color.
- Global preferences are separate from source-folder destination profiles; profiles persist across launches and are clearly associated with their source folder.
- Selection status is based on destination copies and local application metadata; a star and per-destination indicators show it.
- Repeating a shortcut for an image selected in that destination toggles it off by removing only verified application-managed image and matching sidecar copies from that destination; source files are never removed.
- Image copying preserves all embedded metadata by copying the original bytes without re-encoding.
- JPEG/JPG, PNG, GIF, BMP, TIFF and WebP are supported; RAW and video are not.

## 12. Remaining Design Decisions

The following points remain open; decisions already provided by the user are captured as requirements above.

| ID | Decision | Recommendation / question |
|---|---|---|
| OD-001 | Profile identity | Should destination profiles be keyed by canonical folder path, or should users explicitly name/select profiles? Recommendation: path-based profiles with a visible name and a safe “relink profile” flow if a folder is moved. |
| OD-002 | Image subfolders | Should images in subfolders be included? Recommendation: top-level only in V1. |
| OD-003 | Destination location | Should destinations always be children of the source folder? Recommendation: yes for V1, as specified. |
| OD-004 | Navigation boundaries | Stop at the first/last image or wrap around? Recommendation: stop and show a subtle boundary cue. |
| OD-005 | Natural numeric ordering | Should digit sequences sort naturally (`IMG_2` before `IMG_10`) or lexically? Recommendation: natural numeric ordering while retaining ascending/descending choice. |
| OD-006 | Slot presentation at scale | How should many slots appear without cluttering the image? Recommendation: compact scrollable slot bar plus settings list; keep per-destination status visible. |
| OD-007 | Reconciliation matching | How should the app identify existing destination copies if local status metadata is lost? Recommendation: match source/destination relative paths and compare content hashes; report uncertain matches and never change files. |
| OD-009 | Additional formats | Confirm that GIF, BMP, TIFF and WebP are all required alongside JPEG and PNG, as currently specified. |
| OD-010 | Manual refresh | Should new files in the source folder be detected automatically? Recommendation: manual refresh in V1. |
| OD-011 | Zoom | Is fit-to-window sufficient, or is zoom/1:1 view required in V1? Recommendation: fit-to-window first. |
| OD-012 | Progress information | Should the UI show a separate selected-image count in addition to position/total? Recommendation: yes, if it remains visually simple. |
| OD-013 | Close behavior | Should the last source folder be restored on launch? Recommendation: offer this as a preference; no unsorted-work warning is needed because files are never changed. |
| OD-014 | Performance reference | Define reference hardware and test conditions for the 500 ms/20 MB target on each supported OS. |
| OD-015 | Keyboard layouts | Should defaults map to logical character keys or physical key positions? Recommendation: logical key values and user reassignment, validated across keyboard layouts. |

## 13. Change History

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-18 | Initial structured requirements draft. |
| 0.2 | 2026-10-18 | Added extensible slots, persistent settings, sorting direction, selection indicators, optional sound, common image formats and Linux/Windows/macOS support. |
| 0.3 | 2026-10-18 | Clarified source-file protection, byte-identical copying, embedded metadata preservation, per-source-folder profiles, per-destination status and non-destructive metadata reconciliation. |
| 0.4 | — | Replaced destination copy-only/no-op behavior with a per-slot toggle: first activation copies the image and matching sidecars; second activation removes only verified managed copies from that destination. Source files are always immutable. |
