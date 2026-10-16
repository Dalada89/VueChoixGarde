"""File-system operation contracts used by Phase 4 application use cases."""

from pathlib import Path
from typing import Protocol

from vuechoixgarde.ports.models import DestinationResolution, FileFingerprint, SourceScan


class SourceFolderScanner(Protocol):
    """Validate, identify, and scan the top level of a source folder."""

    def check_source_folder(self, path: Path) -> None:
        """Raise a typed error unless `path` exists as a readable directory (FR-002)."""
        ...

    def folder_identity(self, path: Path) -> str:
        """Return the canonical NFC identity of an existing folder (FR-040)."""
        ...

    def scan_source_folder(self, path: Path) -> SourceScan:
        """Return top-level images, sidecar candidates, and subfolder names (FR-003 to FR-005)."""
        ...


class FileSystemPort(Protocol):
    """Safe filesystem actions for source and destination folders."""

    def resolve_destination_folder(
        self, source_root: Path, destination_name: str
    ) -> DestinationResolution:
        """Resolve a direct destination child or report NOT_FOUND/FAULTY (FR-036 to FR-038)."""
        ...

    def create_destination_folder(self, source_root: Path, destination_name: str) -> Path:
        """Create one safe direct child folder and return its exact path (FR-036, NFR-002)."""
        ...

    def list_destination_names(
        self, source_root: Path, destination_folder: Path
    ) -> tuple[str, ...]:
        """List exact names directly in a contained destination folder (FR-047)."""
        ...

    def fingerprint_file(self, source_root: Path, path: Path) -> FileFingerprint:
        """Stream a file's SHA-256 and return size plus `mtime_ns` evidence."""
        ...

    def copy_to_temp(
        self, source_root: Path, destination_folder: Path, source_name: str, temp_name: str
    ) -> FileFingerprint:
        """Copy source bytes to an exclusively-created and verified temp file (FR-045/FR-046)."""
        ...

    def finalize_temp_file(
        self, source_root: Path, destination_folder: Path, temp_name: str, final_name: str
    ) -> Path:
        """Assign the final name without overwriting; conflict leaves the temp file intact."""
        ...

    def delete_verified_file(
        self,
        source_root: Path,
        destination_folder: Path,
        name: str,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        """Unlink only a regular file whose current size/hash match expected evidence (NFR-003)."""
        ...

    def delete_modified_copy(self, source_root: Path, destination_folder: Path, name: str) -> None:
        """Unlink a confirmed modified regular file in the destination folder (FR-049)."""
        ...

    def delete_own_temp_file(self, source_root: Path, destination_folder: Path, name: str) -> None:
        """Unlink only a reserved application temp file in the destination folder (FR-046)."""
        ...
