"""Contained scanning and safe byte-level file operations (FR-002 to FR-058, NFR-002).

The no-replace constants are verified against Linux UAPI `include/uapi/linux/fcntl.h`
(AT_FDCWD=-100, AT_RENAME_NOREPLACE=0x0001) and the Linux rename(2) man page
(RENAME_NOREPLACE semantics), plus Apple's XNU `bsd/sys/stdio.h`
(RENAME_EXCL=0x00000004): https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/stdio.h
"""

import contextlib
import ctypes
import errno
import hashlib
import ntpath
import os
import stat
import sys
import unicodedata
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from vuechoixgarde.core.comparison import comparison_key
from vuechoixgarde.core.folder_names import validate_folder_name
from vuechoixgarde.core.formats import is_supported_image
from vuechoixgarde.core.temp_names import is_reserved_temp_name
from vuechoixgarde.ports.errors import FileSystemError, FileSystemErrorReason
from vuechoixgarde.ports.models import (
    DestinationEntry,
    DestinationFault,
    DestinationResolution,
    DestinationStatus,
    EntryKind,
    FileFingerprint,
    FileMetadata,
    SourceScan,
)

_CHUNK_SIZE = 1024 * 1024
_FILE_ATTRIBUTE_HIDDEN = 0x2
_UF_HIDDEN = 0x00008000
_LINK_FALLBACK_ERRNOS = frozenset(
    code
    for code in (
        getattr(errno, "EPERM", None),
        getattr(errno, "EOPNOTSUPP", None),
        getattr(errno, "ENOTSUP", None),
        getattr(errno, "EMLINK", None),
        getattr(errno, "EXDEV", None),
    )
    if code is not None
)


def extended_path(path: Path) -> Path:
    """Return a Windows extended-length path, or the identical path elsewhere (NFR-002)."""
    if sys.platform != "win32":
        return path
    absolute = ntpath.abspath(os.fspath(path))
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _without_extended_prefix(path: Path) -> Path:
    if sys.platform != "win32":
        return path
    value = os.fspath(path)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if value.startswith("\\\\?\\"):
        return Path(value[4:])
    return path


def is_inside(path: Path, root: Path) -> bool:
    """Return whether a path resolves at or below a root, following links (NFR-002)."""
    try:
        resolved_path = extended_path(path).resolve(strict=False)
        resolved_root = extended_path(root).resolve(strict=True)
        resolved_path.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _raise_fs_error(
    reason: FileSystemErrorReason, path: Path | None = None, detail: str | None = None
) -> FileSystemError:
    return FileSystemError(reason, path=path, detail=detail)


def _entry_is_junction(path: Path) -> bool:
    try:
        return path.is_junction()
    except (OSError, NotImplementedError):
        return False


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or _entry_is_junction(path)


def check_source_folder(path: Path) -> None:
    """Validate existence, directory type and read/search access of a source folder (FR-002)."""
    candidate = extended_path(path)
    if not candidate.exists():
        raise _raise_fs_error(FileSystemErrorReason.SOURCE_MISSING, path)
    if not candidate.is_dir():
        raise _raise_fs_error(FileSystemErrorReason.SOURCE_NOT_DIRECTORY, path)
    if not os.access(candidate, os.R_OK | os.X_OK):
        raise _raise_fs_error(FileSystemErrorReason.SOURCE_NOT_READABLE, path)


def folder_identity(path: Path) -> str:
    """Resolve a folder and recover exact component spellings before NFC normalization (8.4)."""
    try:
        resolved = _without_extended_prefix(extended_path(path).resolve(strict=True))
    except (OSError, RuntimeError) as error:
        raise _raise_fs_error(FileSystemErrorReason.SOURCE_MISSING, path, str(error)) from error

    anchor = Path(resolved.anchor)
    current = anchor
    for component in resolved.parts[1:]:
        exact_component = component
        try:
            names = [entry.name for entry in extended_path(current).iterdir()]
        except OSError:
            names = []
        if component not in names:
            matches = [name for name in names if comparison_key(name) == comparison_key(component)]
            if len(matches) == 1:
                exact_component = matches[0]
        current = current / exact_component
    identity = unicodedata.normalize("NFC", os.fspath(current))
    return identity


def _source_root(path: Path) -> Path:
    try:
        root = _without_extended_prefix(extended_path(path).resolve(strict=True))
    except (OSError, RuntimeError) as error:
        raise _raise_fs_error(FileSystemErrorReason.SOURCE_MISSING, path, str(error)) from error
    if not extended_path(root).is_dir():
        raise _raise_fs_error(FileSystemErrorReason.SOURCE_NOT_DIRECTORY, path)
    return root


def _entry_hidden(name: str, entry_stat: os.stat_result) -> bool:
    if name.startswith("."):
        return True
    if sys.platform == "win32" and entry_stat.st_file_attributes & _FILE_ATTRIBUTE_HIDDEN:
        return True
    return sys.platform == "darwin" and bool(getattr(entry_stat, "st_flags", 0) & _UF_HIDDEN)


def scan_source_folder(path: Path) -> SourceScan:
    """Scan a source folder once at top level, keeping only visible safe entries (8.3)."""
    check_source_folder(path)
    try:
        root = _source_root(path)
        images: list[str] = []
        candidates: list[str] = []
        directories: list[str] = []
        with os.scandir(extended_path(root)) as entries:
            for entry in entries:
                name = entry.name
                if is_reserved_temp_name(name):
                    continue
                entry_path = Path(entry.path)
                try:
                    item_stat = entry.stat(follow_symlinks=False)
                    if _entry_hidden(name, item_stat):
                        continue
                    linked = entry.is_symlink() or _entry_is_junction(entry_path)
                    if linked:
                        try:
                            if not entry.is_file(follow_symlinks=True):
                                continue
                            resolved_target = entry_path.resolve(strict=True)
                            if not is_inside(resolved_target, root):
                                continue
                        except (OSError, RuntimeError):
                            continue
                        candidates.append(name)
                        if is_supported_image(name):
                            images.append(name)
                        continue
                    if stat.S_ISDIR(item_stat.st_mode):
                        directories.append(name)
                    elif stat.S_ISREG(item_stat.st_mode):
                        candidates.append(name)
                        if is_supported_image(name):
                            images.append(name)
                except OSError:
                    continue
    except FileSystemError:
        raise
    except OSError as error:
        reason = (
            FileSystemErrorReason.SOURCE_NOT_READABLE
            if error.errno in {errno.EACCES, errno.EPERM}
            else FileSystemErrorReason.IO_ERROR
        )
        raise _raise_fs_error(reason, path, str(error)) from error
    return SourceScan(tuple(images), tuple(candidates), tuple(directories))


def _regular_file(path: Path) -> bool:
    try:
        file_stat = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(file_stat.st_mode) and not _is_link_or_junction(path)


def _is_simple_name(name: str) -> bool:
    return (
        bool(name)
        and name not in {".", ".."}
        and Path(name).name == name
        and "/" not in name
        and chr(92) not in name
    )


def _contained_destination(source_root: Path, destination_folder: Path) -> Path:
    root = _source_root(source_root)
    destination = extended_path(destination_folder)
    if not is_inside(destination, root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, destination_folder)
    if _is_link_or_junction(destination) or not destination.is_dir():
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, destination_folder)
    return destination


def _hash_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(_CHUNK_SIZE):
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def fingerprint_file(source_root: Path, path: Path) -> FileFingerprint:
    """Return streamed SHA-256, file size, and nanosecond mtime for a contained regular file."""
    if not is_inside(path, source_root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, path)
    candidate = extended_path(path)
    try:
        file_stat = candidate.stat()
        if not stat.S_ISREG(file_stat.st_mode):
            raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, path, "not a regular file")
        with candidate.open("rb") as source:
            size, digest = _hash_stream(source)
    except FileSystemError:
        raise
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, path, str(error)) from error
    return FileFingerprint(size, digest, file_stat.st_mtime_ns)


def file_metadata(source_root: Path, path: Path) -> FileMetadata | None:
    """Return size and mtime_ns of a contained regular file without reading its contents."""
    if not is_inside(path.parent, source_root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, path)
    candidate = extended_path(path)
    try:
        file_stat = candidate.lstat()
        if _is_link_or_junction(candidate):
            raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, path, "not a regular file")
        if not is_inside(path, source_root):
            raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, path)
        if not stat.S_ISREG(file_stat.st_mode):
            raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, path, "not a regular file")
    except FileNotFoundError:
        return None
    except FileSystemError:
        raise
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, path, str(error)) from error
    return FileMetadata(file_stat.st_size, file_stat.st_mtime_ns)


def _destination_names(destination: Path) -> tuple[str, ...]:
    try:
        with os.scandir(extended_path(destination)) as entries:
            return tuple(entry.name for entry in entries)
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, destination, str(error)) from error


def _fault_for(path: Path, root: Path) -> DestinationFault | None:
    candidate = extended_path(path)
    if _is_link_or_junction(candidate):
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return DestinationFault.LINK
        return DestinationFault.LINK if is_inside(resolved, root) else DestinationFault.OUTSIDE
    try:
        if not candidate.is_dir():
            return DestinationFault.FILE
        if not is_inside(candidate, root):
            return DestinationFault.OUTSIDE
    except OSError:
        return DestinationFault.FILE
    return None


def resolve_destination_folder(source_root: Path, destination_name: str) -> DestinationResolution:
    """Resolve a direct child by comparison key; ambiguous names are faulty (FR-036 to FR-038)."""
    root = _source_root(source_root)
    try:
        with os.scandir(extended_path(root)) as entries:
            matches = [
                entry
                for entry in entries
                if comparison_key(entry.name) == comparison_key(destination_name)
            ]
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, source_root, str(error)) from error
    if not matches:
        return DestinationResolution(DestinationStatus.NOT_FOUND)
    real_subfolders = [
        entry
        for entry in matches
        if not entry.is_symlink()
        and not _entry_is_junction(Path(entry.path))
        and entry.is_dir(follow_symlinks=False)
    ]
    if len(real_subfolders) > 1:
        return DestinationResolution(DestinationStatus.FAULTY, reason=DestinationFault.AMBIGUOUS)
    if len(matches) > 1:
        for entry in matches:
            fault = _fault_for(root / entry.name, root)
            if fault is not None:
                return DestinationResolution(DestinationStatus.FAULTY, entry.name, fault)
        return DestinationResolution(DestinationStatus.FAULTY, reason=DestinationFault.AMBIGUOUS)
    exact_name = matches[0].name
    fault = _fault_for(root / exact_name, root)
    if fault is not None:
        return DestinationResolution(DestinationStatus.FAULTY, exact_name, fault)
    return DestinationResolution(DestinationStatus.FOUND, exact_name)


def create_destination_folder(source_root: Path, destination_name: str) -> Path:
    """Create exactly one portable destination child, then re-check containment (5.4/NFR-002)."""
    name_error = validate_folder_name(destination_name)
    if name_error is not None:
        raise _raise_fs_error(
            FileSystemErrorReason.INVALID_NAME, source_root / destination_name, str(name_error)
        )
    root = _source_root(source_root)
    destination = root / destination_name
    if not is_inside(destination, root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, destination)
    try:
        extended_path(destination).mkdir()
    except FileExistsError as error:
        raise _raise_fs_error(
            FileSystemErrorReason.NAME_CONFLICT, destination, str(error)
        ) from error
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, destination, str(error)) from error
    if not is_inside(destination, root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, destination)
    return destination


def list_destination_names(source_root: Path, destination_folder: Path) -> tuple[str, ...]:
    """List exact direct-child names from a safe destination folder."""
    destination = _contained_destination(source_root, destination_folder)
    return _destination_names(destination)


def _verified_destination_child(source_root: Path, exact_name: str) -> tuple[Path, Path]:
    """Resolve one exact, real direct-child destination folder without following links."""
    if not _is_simple_name(exact_name):
        raise _raise_fs_error(FileSystemErrorReason.INVALID_NAME, source_root / exact_name)
    root = _source_root(source_root)
    candidate = extended_path(root / exact_name)
    try:
        candidate_stat = candidate.lstat()
    except OSError as error:
        if isinstance(error, FileNotFoundError):
            raise _raise_fs_error(FileSystemErrorReason.DESTINATION_FILE, candidate) from error
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, candidate, str(error)) from error
    if _is_link_or_junction(candidate):
        raise _raise_fs_error(FileSystemErrorReason.DESTINATION_LINK, candidate)
    if not is_inside(candidate, root):
        raise _raise_fs_error(FileSystemErrorReason.DESTINATION_OUTSIDE, candidate)
    if not stat.S_ISDIR(candidate_stat.st_mode):
        raise _raise_fs_error(FileSystemErrorReason.DESTINATION_FILE, candidate)
    if exact_name not in _destination_names(root):
        raise _raise_fs_error(FileSystemErrorReason.DESTINATION_FILE, candidate)
    return root, candidate


def _rename_directory_no_replace(source: Path, target: Path) -> None:
    """Use only platform-specific no-replace directory rename primitives."""
    if sys.platform == "win32":
        extended_path(source).rename(extended_path(target))
        return
    _ctypes_no_replace(source, target)


def _raise_rename_os_error(error: OSError, path: Path) -> FileSystemError:
    if isinstance(error, FileExistsError) or error.errno in {
        errno.EEXIST,
        errno.ENOTEMPTY,
    }:
        return _raise_fs_error(FileSystemErrorReason.NAME_CONFLICT, path, str(error))
    if sys.platform != "win32" and error.errno in {errno.ENOSYS, errno.EINVAL}:
        return _raise_fs_error(FileSystemErrorReason.FINALIZE_UNSUPPORTED, path, str(error))
    return _raise_fs_error(FileSystemErrorReason.IO_ERROR, path, str(error))


def rename_destination_folder(
    source_root: Path,
    old_exact_name: str,
    new_name: str,
    intermediate_name: str | None = None,
) -> Path:
    """Rename one verified direct child without replacement (FR-100, NFR-002)."""
    root, old_path = _verified_destination_child(source_root, old_exact_name)
    name_error = validate_folder_name(new_name)
    if name_error is not None:
        raise _raise_fs_error(FileSystemErrorReason.INVALID_NAME, root / new_name, str(name_error))

    existing_names = _destination_names(root)
    if any(
        name != old_exact_name and comparison_key(name) == comparison_key(new_name)
        for name in existing_names
    ):
        raise _raise_fs_error(FileSystemErrorReason.NAME_CONFLICT, root / new_name)
    if old_exact_name == new_name:
        return root / new_name

    case_only = comparison_key(old_exact_name) == comparison_key(new_name)
    if case_only:
        if intermediate_name is None:
            intermediate_name = f".vcg-rename-{uuid4().hex}"
        if not _is_simple_name(intermediate_name):
            raise _raise_fs_error(FileSystemErrorReason.INVALID_NAME, root / intermediate_name)
        if any(
            comparison_key(name) == comparison_key(intermediate_name) for name in existing_names
        ):
            raise _raise_fs_error(FileSystemErrorReason.NAME_CONFLICT, root / intermediate_name)
        assert intermediate_name is not None

    final_path = root / new_name
    if case_only:
        assert intermediate_name is not None
        intermediate_path = root / intermediate_name
        try:
            _rename_directory_no_replace(old_path, intermediate_path)
            _rename_directory_no_replace(intermediate_path, final_path)
        except OSError as error:
            if intermediate_path.exists():
                try:
                    _rename_directory_no_replace(intermediate_path, old_path)
                except OSError as rollback_error:
                    raise _raise_fs_error(
                        FileSystemErrorReason.IO_ERROR,
                        intermediate_path,
                        f"rename failed: {error}; rollback failed: {rollback_error}",
                    ) from rollback_error
            raise _raise_rename_os_error(error, final_path) from error
    else:
        try:
            _rename_directory_no_replace(old_path, final_path)
        except OSError as error:
            raise _raise_rename_os_error(error, final_path) from error

    try:
        collisions = tuple(
            name
            for name in _destination_names(root)
            if name != new_name and comparison_key(name) == comparison_key(new_name)
        )
    except FileSystemError as error:
        try:
            _rename_directory_no_replace(final_path, old_path)
        except OSError as rollback_error:
            raise _raise_fs_error(
                FileSystemErrorReason.IO_ERROR,
                final_path,
                f"post-rename check failed: {error}; rollback failed: {rollback_error}",
            ) from rollback_error
        raise
    if collisions:
        try:
            _rename_directory_no_replace(final_path, old_path)
        except OSError as error:
            raise _raise_fs_error(
                FileSystemErrorReason.IO_ERROR,
                final_path,
                f"collision appeared during rename; rollback failed: {error}",
            ) from error
        raise _raise_fs_error(FileSystemErrorReason.NAME_CONFLICT, final_path)
    return final_path


def list_destination_entries(
    source_root: Path, destination_folder: Path
) -> tuple[DestinationEntry, ...]:
    """List all direct entries, including hidden ones, classified without following links."""
    destination = _contained_destination(source_root, destination_folder)
    classified: list[DestinationEntry] = []
    try:
        with os.scandir(extended_path(destination)) as entries:
            for entry in entries:
                entry_path = Path(entry.path)
                if entry.is_symlink() or _entry_is_junction(entry_path):
                    kind = EntryKind.LINK
                else:
                    entry_stat = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(entry_stat.st_mode):
                        kind = EntryKind.DIRECTORY
                    elif stat.S_ISREG(entry_stat.st_mode):
                        kind = EntryKind.FILE
                    else:
                        kind = EntryKind.OTHER
                classified.append(DestinationEntry(entry.name, kind))
    except OSError as error:
        raise _raise_fs_error(
            FileSystemErrorReason.IO_ERROR, destination_folder, str(error)
        ) from error
    return tuple(classified)


def remove_empty_destination_folder(source_root: Path, exact_name: str) -> None:
    """Remove one verified direct child folder, and never recursively remove contents."""
    _, destination = _verified_destination_child(source_root, exact_name)
    try:
        extended_path(destination).rmdir()
    except OSError as error:
        if error.errno in {errno.ENOTEMPTY, errno.EEXIST}:
            raise _raise_fs_error(
                FileSystemErrorReason.FOLDER_NOT_EMPTY, destination, str(error)
            ) from error
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, destination, str(error)) from error


def copy_to_temp(
    source_root: Path, destination_folder: Path, source_name: str, temp_name: str
) -> FileFingerprint:
    """Write, verify and timestamp an exclusive temp copy (FR-045/FR-046/FR-055)."""
    if not _is_simple_name(source_name):
        raise _raise_fs_error(FileSystemErrorReason.INVALID_NAME, source_root / source_name)
    if not is_reserved_temp_name(temp_name):
        raise _raise_fs_error(
            FileSystemErrorReason.INVALID_TEMP_NAME, destination_folder / temp_name
        )
    root = _source_root(source_root)
    source = extended_path(root / source_name)
    destination = _contained_destination(root, destination_folder)
    source_path = root / source_name
    if not is_inside(source_path, root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, source_path)
    temp_path = destination / temp_name
    if not is_inside(temp_path, root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, temp_path)

    created = False
    try:
        source_stat = source.stat()
        if not stat.S_ISREG(source_stat.st_mode):
            raise _raise_fs_error(
                FileSystemErrorReason.COPY_FAILED, source_path, "not a regular file"
            )
        source_digest = hashlib.sha256()
        source_size = 0
        descriptor = os.open(
            extended_path(temp_path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        created = True
        try:
            with source.open("rb") as origin:
                while chunk := origin.read(_CHUNK_SIZE):
                    remaining = memoryview(chunk)
                    while remaining:
                        written = os.write(descriptor, remaining)
                        if written <= 0:
                            raise OSError(errno.EIO, "short write while copying")
                        remaining = remaining[written:]
                    source_size += len(chunk)
                    source_digest.update(chunk)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        with extended_path(temp_path).open("rb") as copied:
            copied_size, copied_digest = _hash_stream(copied)
        expected_digest = source_digest.hexdigest()
        if copied_size != source_size or copied_digest != expected_digest:
            raise _raise_fs_error(
                FileSystemErrorReason.FILE_CHANGED, temp_path, "copy verification failed"
            )
        os.utime(extended_path(temp_path), ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        return FileFingerprint(source_size, expected_digest, source_stat.st_mtime_ns)
    except FileSystemError:
        if created:
            with contextlib.suppress(OSError):
                extended_path(temp_path).unlink()
        raise
    except Exception as error:
        if created:
            with contextlib.suppress(OSError):
                extended_path(temp_path).unlink()
        raise _raise_fs_error(FileSystemErrorReason.COPY_FAILED, source_path, str(error)) from error


def _ctypes_no_replace(temp_path: Path, final_path: Path) -> None:
    """Invoke the platform's atomic no-replace rename or raise its exact errno."""
    library = ctypes.CDLL(None, use_errno=True)
    source = os.fsencode(extended_path(temp_path))
    target = os.fsencode(extended_path(final_path))
    if sys.platform.startswith("linux"):
        try:
            renameat2 = library.renameat2
        except AttributeError as error:
            raise OSError(errno.ENOSYS, "renameat2 is unavailable") from error
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(-100, source, -100, target, 0x1)
    elif sys.platform == "darwin":
        try:
            renamex_np = library.renamex_np
        except AttributeError as error:
            raise OSError(errno.ENOSYS, "renamex_np is unavailable") from error
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source, target, 0x4)
    else:
        raise OSError(errno.ENOSYS, "no atomic no-replace rename is available")
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), os.fspath(final_path))


def finalize_temp_file(
    source_root: Path, destination_folder: Path, temp_name: str, final_name: str
) -> Path:
    """Finalize without replacement; on conflict preserve the temp for caller cleanup (8.7)."""
    if not _is_simple_name(final_name):
        raise _raise_fs_error(FileSystemErrorReason.INVALID_NAME, destination_folder / final_name)
    if not is_reserved_temp_name(temp_name):
        raise _raise_fs_error(
            FileSystemErrorReason.INVALID_TEMP_NAME, destination_folder / temp_name
        )
    destination = _contained_destination(source_root, destination_folder)
    temp_path = destination / temp_name
    final_path = destination / final_name
    if not is_inside(temp_path, source_root) or not is_inside(final_path, source_root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, final_path)
    if not _regular_file(extended_path(temp_path)):
        raise _raise_fs_error(
            FileSystemErrorReason.COPY_FAILED, temp_path, "temp file is missing or not regular"
        )
    if any(
        comparison_key(name) == comparison_key(final_name)
        for name in _destination_names(destination)
    ):
        raise _raise_fs_error(FileSystemErrorReason.NAME_CONFLICT, final_path)

    if sys.platform == "win32":
        try:
            extended_path(temp_path).rename(extended_path(final_path))
            return final_path
        except FileExistsError as error:
            raise _raise_fs_error(
                FileSystemErrorReason.NAME_CONFLICT, final_path, str(error)
            ) from error
        except OSError as error:
            raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, final_path, str(error)) from error

    try:
        os.link(extended_path(temp_path), extended_path(final_path), follow_symlinks=False)
    except FileExistsError as error:
        raise _raise_fs_error(
            FileSystemErrorReason.NAME_CONFLICT, final_path, str(error)
        ) from error
    except OSError as error:
        if error.errno not in _LINK_FALLBACK_ERRNOS:
            raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, final_path, str(error)) from error
        try:
            _ctypes_no_replace(temp_path, final_path)
        except OSError as fallback_error:
            if fallback_error.errno == errno.EEXIST:
                raise _raise_fs_error(
                    FileSystemErrorReason.NAME_CONFLICT, final_path, str(fallback_error)
                ) from fallback_error
            if fallback_error.errno in _LINK_FALLBACK_ERRNOS or fallback_error.errno in {
                errno.ENOSYS,
                errno.EINVAL,
            }:
                raise _raise_fs_error(
                    FileSystemErrorReason.FINALIZE_UNSUPPORTED, final_path, str(fallback_error)
                ) from fallback_error
            raise _raise_fs_error(
                FileSystemErrorReason.IO_ERROR, final_path, str(fallback_error)
            ) from fallback_error
        return final_path

    try:
        extended_path(temp_path).unlink()
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, temp_path, str(error)) from error
    return final_path


def _validate_destination_file(
    source_root: Path, destination_folder: Path, name: str
) -> tuple[Path, Path]:
    destination = _contained_destination(source_root, destination_folder)
    if not _is_simple_name(name):
        raise _raise_fs_error(FileSystemErrorReason.INVALID_NAME, destination_folder / name)
    candidate = destination / name
    if not is_inside(candidate, source_root):
        raise _raise_fs_error(FileSystemErrorReason.PATH_OUTSIDE_ROOT, candidate)
    if not _regular_file(extended_path(candidate)):
        raise _raise_fs_error(FileSystemErrorReason.DELETE_REFUSED, candidate, "not a regular file")
    return destination, candidate


def delete_verified_file(
    source_root: Path,
    destination_folder: Path,
    name: str,
    expected_size: int,
    expected_sha256: str,
) -> None:
    """Verify size and SHA-256 immediately before unlinking a managed copy (NFR-003)."""
    _, candidate = _validate_destination_file(source_root, destination_folder, name)
    current = fingerprint_file(source_root, candidate)
    if current.size != expected_size or current.sha256 != expected_sha256:
        raise _raise_fs_error(FileSystemErrorReason.FILE_CHANGED, candidate)
    try:
        extended_path(candidate).unlink()
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, candidate, str(error)) from error


def delete_modified_copy(source_root: Path, destination_folder: Path, name: str) -> None:
    """Delete only a confirmed modified regular copy inside the destination (FR-049)."""
    _, candidate = _validate_destination_file(source_root, destination_folder, name)
    try:
        extended_path(candidate).unlink()
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, candidate, str(error)) from error


def delete_own_temp_file(source_root: Path, destination_folder: Path, name: str) -> None:
    """Delete an owned reserved temp file only from a contained destination folder (FR-046)."""
    if not is_reserved_temp_name(name):
        raise _raise_fs_error(FileSystemErrorReason.DELETE_REFUSED, destination_folder / name)
    _, candidate = _validate_destination_file(source_root, destination_folder, name)
    try:
        extended_path(candidate).unlink()
    except OSError as error:
        raise _raise_fs_error(FileSystemErrorReason.IO_ERROR, candidate, str(error)) from error


class LocalFileSystem:
    """Concrete implementation of source scanning and safe file operation ports."""

    check_source_folder = staticmethod(check_source_folder)
    folder_identity = staticmethod(folder_identity)
    scan_source_folder = staticmethod(scan_source_folder)
    resolve_destination_folder = staticmethod(resolve_destination_folder)
    create_destination_folder = staticmethod(create_destination_folder)
    list_destination_names = staticmethod(list_destination_names)
    rename_destination_folder = staticmethod(rename_destination_folder)
    list_destination_entries = staticmethod(list_destination_entries)
    remove_empty_destination_folder = staticmethod(remove_empty_destination_folder)
    fingerprint_file = staticmethod(fingerprint_file)
    file_metadata = staticmethod(file_metadata)
    copy_to_temp = staticmethod(copy_to_temp)
    finalize_temp_file = staticmethod(finalize_temp_file)
    delete_verified_file = staticmethod(delete_verified_file)
    delete_modified_copy = staticmethod(delete_modified_copy)
    delete_own_temp_file = staticmethod(delete_own_temp_file)
