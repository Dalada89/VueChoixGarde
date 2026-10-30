# Changelog

## 0.1.0 — unreleased

- Initial public release candidate for local image review and safe copy-based sorting.
- Added Linux, Windows and Apple-silicon macOS one-folder packaging and cross-platform release automation.
- Added German, English and French catalogs, help, settings, profiles and optional sound feedback.
- Documented supported formats, safety behavior, known limitations and manual acceptance checks.
- Added journaled, no-replace destination-folder renaming with crash recovery and copy-register updates.
- Added verified destination-folder deletion, foreign-entry detachment, stale-confirmation checks and multilingual UI prompts.
- Moved settings saves to immutable UI-thread submissions so file workers never read Qt widgets.
- Added Copy/Move slot modes, the R → `trash` Move default, RAW sidecar grouping, journaled Move recovery and session-only `Ctrl+Z` undo with localized feedback and help.
