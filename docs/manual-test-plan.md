# Manual Platform Acceptance Plan

This plan supplements automated unit/integration/UI tests. Complete it on physical or representative Linux, Windows and macOS installations. Record failures and OS/build identifiers; do not infer a pass from an offscreen test. Use generated, non-personal test images and a temporary source folder containing collision, sidecar, hidden, symlink and modified-copy cases. Record each result in the blank columns; no manual platform result is asserted here.

## Platform/build record

| Platform | OS version | CPU / session | Artifact/version | Tester/date | Result / notes |
|---|---|---|---|---|---|
| Linux | | x86_64; X11 and Wayland where available | | | |
| Windows | | x86_64 | | | |
| macOS | | Apple silicon arm64 | | | |

## SRS acceptance traceability

| # | SRS acceptance check | Linux | Windows | macOS | Evidence / issue |
|---:|---|---|---|---|---|
| 1 | Fixed formats, hidden files, subfolders, external links; HEIC listed and unavailable message when needed | | | | |
| 2 | Natural/case-insensitive sorting; direction change preserves current item and progress | | | | |
| 3 | Arrow navigation stops at both ends; progress follows position | | | | |
| 4 | EXIF orientation; unreadable image remains navigable and toggleable | | | | |
| 5 | Unnamed slot prompt; cancel creates no folder or copy | | | | |
| 6 | Case-folded destination identity and invalid-name rejection | | | | |
| 7 | Image plus sidecars are byte-identical; source remains unchanged | | | | |
| 8 | Toggle-off removes only verified copies in one destination; source/other destinations/folder remain | | | | |
| 9 | Modified copy requires explicit confirmation; cancel preserves it | | | | |
| 10 | Pre-existing case-variant conflict is neither overwritten nor deleted | | | | |
| 11 | Simulated/interrupted copy leaves no partial output after recovery | | | | |
| 12 | Key repeat toggles once; concurrent actions are ignored | | | | |
| 13 | Selection restores after restart; external deletion becomes unselected | | | | |
| 14 | Physical W/A/S/D positions on QWERTY/QWERTZ/AZERTY; learned labels persist; modifiers blocked | | | | |
| 15 | New folder gets global template; profiles do not leak between folders | | | | |
| 16 | Sound only after successful toggle-on; setting disables it | | | | |
| 17 | Switch DE/EN/FR; F1 shows shortcuts and current slot help | | | | |
| 18 | Missing app data initializes; damaged data is preserved and causes no deletion | | | | |
| 19 | No writes outside source folder and application data, including symlink cases | | | | |
| 20 | JSONL logs parse and contain no image metadata | | | | |
| 21 | Saving a changed name on an existing profile slot physically renames the direct folder and updates selections/register paths; unrelated folders and source files remain unchanged | | | | |
| 22 | Interrupt a folder rename at journal-only, intermediate and completed stages; reopen and confirm recovery is consistent before reconciliation | | | | |
| 23 | Delete confirmation defaults to Cancel; Escape cancels without deleting files, folders, slots or register entries | | | | |
| 24 | Folder with foreign/modified/hidden entries is detached only; confirm every entry and the folder remain byte-for-byte unchanged | | | | |

## Release-specific checks

| Check | Linux | Windows | macOS | Notes |
|---|---|---|---|---|
| Extracted artifact launches from read-only install directory; app data goes to user data | | | | |
| Artifact `--smoke-test` exits 0 | | | | |
| Sound resource resolves; audio backend failure does not stop sorting | | | | |
| HEIC/HEIF sample decode and orientation, if available | | | | |
| Keyboard layouts, AltGr, dead keys, key repeat and text-field focus | | | | |
| Rename while destination is open/locked in Explorer; fail cleanly and retain a consistent profile | N/A | | N/A | Windows-specific |
| APFS case-only folder rename (e.g. `Before` → `bEFORE`) through the journaled intermediate name | N/A | N/A | | macOS-specific |
| Unsigned-app warning and documented launch path | | | | |

Automated CI can execute filesystem and UI tests on hosted runners but is not a substitute for physical keyboard/layout validation. Do not fill in results until the corresponding test was performed.
