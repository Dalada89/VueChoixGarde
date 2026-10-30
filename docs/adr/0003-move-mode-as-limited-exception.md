# ADR 0003: Move mode as a limited exception to source-file protection

- Status: Accepted with requirements version 0.8 (product owner confirmed).

## Context

Up to version 0.7 the application never changed image files in the source folder (NFR-001); sorting worked only by byte-identical copies. The product owner wants a “trash” destination that really moves images out of the source folder, and in general a per-slot choice between copying and moving.

## Options considered

1. Keep copy-only behavior; users delete images manually.
2. Per-slot mode Copy/Move. Move is the only operation that removes source files. It uses a verified, no-overwrite procedure, is recorded in the copy register and can be undone for the session.
3. Move to the operating system's trash/recycle bin (rejected, see below).

## Decision

Choose option 2 (FR-120 to FR-127). NFR-001 and Section 3.2 are narrowed: source files are still never modified, renamed or deleted, and are moved only by a Move slot (FR-121) or its undo (FR-124). Copy remains the default for every slot; only the new default slot `R` / `trash` moves. Moved files are never deleted by the application and count as foreign entries, so “delete destination folder” cannot destroy the only remaining copy (FR-125). A mode can be changed only while no managed copies exist for the slot's folder (FR-126).

## Consequences

- Data safety now relies on the move procedure (write, verify, then remove the source; rollback on failure) and on crash recovery for interrupted moves, analogous to renames (FR-101).
- Undo is session-only; after a restart a moved image can only be restored manually.
- Acceptance criteria 7, 8 and 24 to 28 and the test requirements cover the new behavior.
- The `trash` slot moves images into an ordinary destination folder named `trash` inside the source folder. The application never moves anything into the operating system's trash/recycle bin; the user may do that manually in the file manager.
- Option 3 is not chosen because it depends on platform-specific trash handling (NFR-040) and cannot be restored by the application.
- Camera RAW files (e.g. `.nef`) with the same stem are sidecar files (FR-043) and are therefore moved or copied together with their image.

## Reversibility

Setting all slots to Copy restores the previous behavior. Removing the Move mode requires reverting FR-120 to FR-127.
