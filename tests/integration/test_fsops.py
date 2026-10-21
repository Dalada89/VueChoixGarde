import errno
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

import vuechoixgarde.fsops.filesystem as filesystem
from vuechoixgarde.core.temp_names import temp_file_name
from vuechoixgarde.fsops.filesystem import LocalFileSystem
from vuechoixgarde.fsops.lock import LocalFolderLock
from vuechoixgarde.ports.errors import FileSystemError, FileSystemErrorReason
from vuechoixgarde.ports.models import DestinationFault, DestinationStatus, EntryKind


def _make_exif_jpeg(path: Path) -> bytes:
    image = Image.new("RGB", (16, 12), color=(25, 90, 140))
    exif = Image.Exif()
    exif[271] = "Test Camera"
    exif[272] = "Model 1"
    exif[306] = "2025:01:02 03:04:05"
    exif[34853] = {
        1: "N",
        2: (Fraction(37), Fraction(48), Fraction(0)),
        3: "W",
        4: (Fraction(122), Fraction(24), Fraction(0)),
    }
    image.save(path, format="JPEG", exif=exif)
    return path.read_bytes()


def _safe_copy(source_root: Path, destination: Path, source_name: str) -> tuple[str, str]:
    operation_id = uuid4().hex
    temp_name = temp_file_name(operation_id, 0)
    fingerprint = LocalFileSystem.copy_to_temp(source_root, destination, source_name, temp_name)
    LocalFileSystem.finalize_temp_file(source_root, destination, temp_name, source_name)
    return fingerprint.sha256, temp_name


def test_verified_copy_is_byte_identical_and_preserves_mtime(source_guard, tmp_path: Path) -> None:
    source_root = source_guard.root
    source_file = source_root / "camera.jpg"
    original = _make_exif_jpeg(source_file)
    expected_mtime = 1_735_789_445_987_654_321
    os.utime(source_file, ns=(expected_mtime, expected_mtime))
    destination = LocalFileSystem.create_destination_folder(source_root, "Best")
    source_guard.seal(allowed_destinations={"Best"})

    fingerprint = LocalFileSystem.copy_to_temp(
        source_root, destination, source_file.name, temp_file_name(uuid4().hex, 0)
    )
    temp_name = next(path.name for path in destination.iterdir())
    LocalFileSystem.finalize_temp_file(source_root, destination, temp_name, source_file.name)

    copied = destination / source_file.name
    assert copied.read_bytes() == original
    assert copied.stat().st_mtime_ns == expected_mtime
    assert fingerprint.size == len(original)
    assert len(fingerprint.sha256) == 64
    with Image.open(copied) as image:
        exif = image.getexif()
        assert exif[271] == "Test Camera"
        assert exif[272] == "Model 1"
        assert exif[306] == "2025:01:02 03:04:05"
        assert exif.get_ifd(34853)[1] == "N"


@pytest.mark.parametrize("failure", ["write", "fsync", "reread", "utime", "source_missing"])
def test_copy_failures_leave_no_temp_or_final_file(
    source_guard, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    source_root = source_guard.root
    source_file = source_root / "photo.jpg"
    original = _make_exif_jpeg(source_file)
    original_mtime = source_file.stat().st_mtime_ns
    destination = LocalFileSystem.create_destination_folder(source_root, "Best")
    source_guard.seal(allowed_destinations={"Best"})
    name = temp_file_name(uuid4().hex, 0)

    if failure == "write":
        monkeypatch.setattr(
            filesystem.os,
            "write",
            lambda *_args: (_ for _ in ()).throw(OSError(errno.EIO, "write fault")),
        )
    elif failure == "fsync":
        monkeypatch.setattr(
            filesystem.os,
            "fsync",
            lambda *_args: (_ for _ in ()).throw(OSError(errno.EIO, "fsync fault")),
        )
    elif failure == "reread":
        monkeypatch.setattr(
            filesystem, "_hash_stream", lambda stream: (len(stream.read()), "0" * 64)
        )
    elif failure == "utime":
        monkeypatch.setattr(
            filesystem.os,
            "utime",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(errno.EIO, "utime fault")),
        )
    else:
        original_open = Path.open

        def disappear_on_source_open(path: Path, *args, **kwargs):
            if path == source_file:
                source_file.unlink()
                raise FileNotFoundError(source_file)
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", disappear_on_source_open)

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.copy_to_temp(source_root, destination, source_file.name, name)
    assert caught.value.reason in {
        FileSystemErrorReason.COPY_FAILED,
        FileSystemErrorReason.FILE_CHANGED,
    }
    assert list(destination.iterdir()) == []

    if failure == "source_missing":
        monkeypatch.undo()
        source_file.write_bytes(original)
        os.utime(source_file, ns=(original_mtime, original_mtime))


def test_temp_creation_collision_does_not_delete_an_existing_temp(source_guard) -> None:
    source_root = source_guard.root
    source_file = source_root / "photo.jpg"
    source_file.write_bytes(b"source")
    destination = LocalFileSystem.create_destination_folder(source_root, "Best")
    name = temp_file_name(uuid4().hex, 0)
    existing = destination / name
    existing.write_bytes(b"not ours")
    source_guard.seal(allowed_destinations={"Best"})

    with pytest.raises(FileSystemError):
        LocalFileSystem.copy_to_temp(source_root, destination, source_file.name, name)
    assert existing.read_bytes() == b"not ours"


def test_finalize_exact_and_casefold_conflicts_never_overwrite(source_guard) -> None:
    source_root = source_guard.root
    source_file = source_root / "photo.jpg"
    source_file.write_bytes(b"source")
    destination = LocalFileSystem.create_destination_folder(source_root, "Best")
    (destination / "photo.jpg").write_bytes(b"exact occupant")
    (destination / "PHOTO.JPG").write_bytes(b"case occupant")
    temp_name = temp_file_name(uuid4().hex, 0)
    (destination / temp_name).write_bytes(b"new copy")
    source_guard.seal(allowed_destinations={"Best"})

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.finalize_temp_file(source_root, destination, temp_name, "photo.jpg")
    assert caught.value.reason is FileSystemErrorReason.NAME_CONFLICT
    assert (destination / temp_name).read_bytes() == b"new copy"
    assert (destination / "photo.jpg").read_bytes() == b"exact occupant"
    assert (destination / "PHOTO.JPG").read_bytes() == b"case occupant"


def test_linux_hardlink_fallback_uses_renameat2_without_replacement(
    source_guard, monkeypatch
) -> None:
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux renameat2 fallback only")
    source_root = source_guard.root
    source_file = source_root / "photo.jpg"
    source_file.write_bytes(b"source")
    destination = LocalFileSystem.create_destination_folder(source_root, "Best")
    temp_name = temp_file_name(uuid4().hex, 0)
    (destination / temp_name).write_bytes(b"copied")
    source_guard.seal(allowed_destinations={"Best"})
    original_link = filesystem.os.link

    def unsupported_link(*_args, **_kwargs):
        raise OSError(errno.EPERM, "hardlinks unsupported")

    monkeypatch.setattr(filesystem.os, "link", unsupported_link)
    final_path = LocalFileSystem.finalize_temp_file(
        source_root, destination, temp_name, "photo.jpg"
    )
    monkeypatch.setattr(filesystem.os, "link", original_link)
    assert final_path.read_bytes() == b"copied"
    assert not (destination / temp_name).exists()


def test_unavailable_link_and_noreplace_methods_report_unsupported(
    source_guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name == "nt":
        pytest.skip("POSIX fallback test")
    source_root = source_guard.root
    source_file = source_root / "photo.jpg"
    source_file.write_bytes(b"source")
    destination = LocalFileSystem.create_destination_folder(source_root, "Best")
    temp_name = temp_file_name(uuid4().hex, 0)
    (destination / temp_name).write_bytes(b"copied")
    source_guard.seal(allowed_destinations={"Best"})

    def unsupported_link(*_args, **_kwargs):
        raise OSError(errno.EPERM, "hardlinks unsupported")

    def unsupported_rename(*_args, **_kwargs):
        raise OSError(errno.ENOSYS, "no no-replace syscall")

    monkeypatch.setattr(filesystem.os, "link", unsupported_link)
    monkeypatch.setattr(filesystem, "_ctypes_no_replace", unsupported_rename)
    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.finalize_temp_file(source_root, destination, temp_name, "photo.jpg")
    assert caught.value.reason is FileSystemErrorReason.FINALIZE_UNSUPPORTED
    assert not (destination / "photo.jpg").exists()
    assert (destination / temp_name).read_bytes() == b"copied"


def test_source_folder_validation_returns_typed_errors(source_guard) -> None:
    root = source_guard.root
    regular_file = root / "not-a-folder"
    regular_file.write_text("data", encoding="utf-8")
    source_guard.seal()

    with pytest.raises(FileSystemError) as missing:
        LocalFileSystem.check_source_folder(root / "missing")
    assert missing.value.reason is FileSystemErrorReason.SOURCE_MISSING
    with pytest.raises(FileSystemError) as not_directory:
        LocalFileSystem.check_source_folder(regular_file)
    assert not_directory.value.reason is FileSystemErrorReason.SOURCE_NOT_DIRECTORY


def test_unreadable_source_folder_is_rejected(source_guard, monkeypatch) -> None:
    source_guard.seal()
    monkeypatch.setattr(filesystem.os, "access", lambda *_args: False)
    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.check_source_folder(source_guard.root)
    assert caught.value.reason is FileSystemErrorReason.SOURCE_NOT_READABLE


def test_scan_uses_one_scandir_pass(source_guard, monkeypatch) -> None:
    (source_guard.root / "photo.jpg").write_bytes(b"image")
    source_guard.seal()
    original_scandir = filesystem.os.scandir
    calls = 0

    def counted_scandir(path):
        nonlocal calls
        calls += 1
        return original_scandir(path)

    monkeypatch.setattr(filesystem.os, "scandir", counted_scandir)
    LocalFileSystem.scan_source_folder(source_guard.root)
    assert calls == 1


def test_folder_identity_is_nfc_and_paths_are_contained(source_guard, tmp_path: Path) -> None:
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "café")
    folder = source_guard.root / decomposed
    folder.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    source_guard.seal()

    identity = LocalFileSystem.folder_identity(folder)
    assert identity.endswith(unicodedata.normalize("NFC", decomposed))
    assert unicodedata.is_normalized("NFC", identity)
    assert filesystem.is_inside(folder / "not-yet-created", source_guard.root)
    assert not filesystem.is_inside(outside, source_guard.root)


def test_scanner_filters_hidden_unsupported_reserved_and_folders(
    source_guard, tmp_path: Path
) -> None:
    root = source_guard.root
    _make_exif_jpeg(root / "IMG_2.JPG")
    (root / "photo.xmp").write_text("sidecar", encoding="utf-8")
    (root / "readme.txt").write_text("candidate", encoding="utf-8")
    (root / ".hidden.jpg").write_bytes(b"hidden")
    (root / temp_file_name(uuid4().hex, 1)).write_bytes(b"temp")
    (root / "nested").mkdir()
    outside = tmp_path / "external.jpg"
    outside.write_bytes(b"outside")
    inside = root / "inside.jpg"
    inside.write_bytes(b"inside")
    for link_name, target in (
        ("internal.jpg", inside),
        ("external.jpg", outside),
        ("broken.jpg", root / "missing.jpg"),
        ("folder-link.jpg", root / "nested"),
    ):
        try:
            (root / link_name).symlink_to(target, target_is_directory=target.is_dir())
        except OSError as error:
            source_guard.seal()
            pytest.skip(f"symlink creation is unavailable: {error}")
    source_guard.seal()

    result = LocalFileSystem.scan_source_folder(root)
    assert set(result.images) == {"IMG_2.JPG", "inside.jpg", "internal.jpg"}
    assert {"photo.xmp", "readme.txt", "IMG_2.JPG"}.issubset(set(result.sidecar_candidates))
    assert result.directories == ("nested",)
    assert not {".hidden.jpg", "external.jpg", "broken.jpg", "folder-link.jpg"}.intersection(
        result.images
    )


def test_resolve_destination_folder_reports_all_outcomes(source_guard, tmp_path: Path) -> None:
    root = source_guard.root
    (root / "Best").mkdir()
    (root / "Occupied").write_text("file", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    inside = root / "InsideTarget"
    inside.mkdir()
    try:
        (root / "Linked").symlink_to(outside, target_is_directory=True)
        (root / "InsideLink").symlink_to(inside, target_is_directory=True)
    except OSError as error:
        source_guard.seal()
        pytest.skip(f"symlink creation is unavailable: {error}")
    source_guard.seal()

    found = LocalFileSystem.resolve_destination_folder(root, "best")
    assert found.status is DestinationStatus.FOUND
    assert found.exact_name == "Best"
    assert (
        LocalFileSystem.resolve_destination_folder(root, "Missing").status
        is DestinationStatus.NOT_FOUND
    )
    faulty_file = LocalFileSystem.resolve_destination_folder(root, "Occupied")
    assert faulty_file.status is DestinationStatus.FAULTY
    assert faulty_file.reason is DestinationFault.FILE
    faulty_link = LocalFileSystem.resolve_destination_folder(root, "InsideLink")
    assert faulty_link.status is DestinationStatus.FAULTY
    assert faulty_link.reason is DestinationFault.LINK
    outside_link = LocalFileSystem.resolve_destination_folder(root, "Linked")
    assert outside_link.status is DestinationStatus.FAULTY
    assert outside_link.reason is DestinationFault.OUTSIDE


def test_casefold_ambiguous_destination_is_faulty_on_case_sensitive_filesystem(
    source_guard,
) -> None:
    root = source_guard.root
    (root / "Best").mkdir()
    try:
        (root / "best").mkdir()
    except FileExistsError:
        source_guard.seal()
        pytest.skip("filesystem is case-insensitive")
    source_guard.seal()
    resolution = LocalFileSystem.resolve_destination_folder(root, "BEST")
    assert resolution.status is DestinationStatus.FAULTY
    assert resolution.reason is DestinationFault.AMBIGUOUS


def test_verified_delete_and_modified_delete_safeguards(source_guard) -> None:
    root = source_guard.root
    source_file = root / "source.jpg"
    source_file.write_bytes(b"original")
    destination = LocalFileSystem.create_destination_folder(root, "Best")
    copied = destination / "copy.jpg"
    copied.write_bytes(b"original")
    good = LocalFileSystem.fingerprint_file(root, copied)
    changed = destination / "changed.jpg"
    changed.write_bytes(b"changed")
    temp_name = temp_file_name(uuid4().hex, 0)
    (destination / temp_name).write_bytes(b"temp")
    source_guard.seal(allowed_destinations={"Best"})

    LocalFileSystem.delete_verified_file(root, destination, copied.name, good.size, good.sha256)
    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.delete_verified_file(
            root, destination, changed.name, good.size, good.sha256
        )
    assert caught.value.reason is FileSystemErrorReason.FILE_CHANGED
    assert changed.exists()
    with pytest.raises(FileSystemError):
        LocalFileSystem.delete_own_temp_file(root, destination, changed.name)
    LocalFileSystem.delete_own_temp_file(root, destination, temp_name)
    assert not copied.exists()
    assert not (destination / temp_name).exists()


def test_delete_modified_copy_requires_contained_regular_file(source_guard) -> None:
    root = source_guard.root
    source_file = root / "source.jpg"
    source_file.write_bytes(b"source")
    destination = LocalFileSystem.create_destination_folder(root, "Best")
    (destination / "modified.jpg").write_bytes(b"modified")
    (destination / "nested").mkdir()
    source_guard.seal(allowed_destinations={"Best"})

    LocalFileSystem.delete_modified_copy(root, destination, "modified.jpg")
    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.delete_modified_copy(root, destination, "nested")
    assert caught.value.reason is FileSystemErrorReason.DELETE_REFUSED


def test_folder_lock_conflicts_across_process_and_releases(tmp_path: Path) -> None:
    app_data = tmp_path / "appdata"
    identity = str(tmp_path / "source")
    first = LocalFolderLock(app_data, identity)
    first.acquire()
    script = (
        "from pathlib import Path; "
        "from vuechoixgarde.fsops.lock import LocalFolderLock; "
        "from vuechoixgarde.ports.errors import FolderLockError; "
        "lock=LocalFolderLock(Path(r'" + str(app_data) + "'), " + repr(identity) + "); "
        "\ntry: lock.acquire()\nexcept FolderLockError: print('locked')\nelse: print('acquired')"
    )
    busy = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert busy.stdout.strip() == "locked"
    first.release()
    free = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert free.stdout.strip() == "acquired"


@pytest.mark.skipif(sys.platform != "win32", reason="extended-length paths are Windows-specific")
def test_windows_extended_path_prefix_supports_long_paths(source_guard) -> None:
    root = source_guard.root
    current = root
    for index in range(12):
        current = current / f"segment-{index:02d}-{'x' * 12}"
        filesystem.extended_path(current).mkdir()
    assert len(str(current)) > 260
    assert filesystem.extended_path(current).is_absolute()
    source_guard.seal()
    LocalFileSystem.check_source_folder(current)


def test_file_metadata_returns_fingerprint_size_and_mtime_without_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    path = root / "photo.jpg"
    path.write_bytes(b"image bytes")
    expected_mtime = 1_735_789_445_987_654_321
    os.utime(path, ns=(expected_mtime, expected_mtime))
    fingerprint = LocalFileSystem.fingerprint_file(root, path)

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError("metadata lookup must not read file contents")

    monkeypatch.setattr(Path, "open", unexpected_read)
    monkeypatch.setattr(filesystem, "_hash_stream", unexpected_read)

    metadata = LocalFileSystem.file_metadata(root, path)
    assert metadata is not None
    assert metadata.size == fingerprint.size == len(b"image bytes")
    assert metadata.mtime_ns == fingerprint.mtime_ns == expected_mtime


def test_file_metadata_returns_none_for_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()

    assert LocalFileSystem.file_metadata(root, root / "missing.jpg") is None


def test_file_metadata_rejects_outside_path(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.file_metadata(root, outside)
    assert caught.value.reason is FileSystemErrorReason.PATH_OUTSIDE_ROOT


def test_file_metadata_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    link = root / "linked.jpg"
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.file_metadata(root, link)
    assert caught.value.reason is FileSystemErrorReason.IO_ERROR
    assert caught.value.detail == "not a regular file"


def test_file_metadata_rejects_non_regular_file(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    folder = root / "folder"
    folder.mkdir()

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.file_metadata(root, folder)
    assert caught.value.reason is FileSystemErrorReason.IO_ERROR
    assert caught.value.detail == "not a regular file"


def test_rename_destination_folder_moves_child_without_replacing(source_guard) -> None:
    root = source_guard.root
    old = root / "Old"
    old.mkdir()
    (old / "photo.jpg").write_bytes(b"managed bytes")
    source_guard.seal(allowed_destinations={"Old", "New"})

    result = LocalFileSystem.rename_destination_folder(root, "Old", "New")

    assert result == root / "New"
    assert not old.exists()
    assert (result / "photo.jpg").read_bytes() == b"managed bytes"


def test_case_only_destination_rename_uses_intermediate_name(source_guard) -> None:
    root = source_guard.root
    old = root / "Best"
    old.mkdir()
    (old / "photo.jpg").write_bytes(b"image")
    source_guard.seal(allowed_destinations={"Best", "best"})

    result = LocalFileSystem.rename_destination_folder(
        root, "Best", "best", ".vcg-rename-test-intermediate"
    )

    assert result == root / "best"
    assert result.is_dir()
    assert (result / "photo.jpg").read_bytes() == b"image"
    assert not (root / ".vcg-rename-test-intermediate").exists()


@pytest.mark.parametrize("occupied_kind", ["file", "directory"])
def test_destination_folder_rename_conflict_preserves_both_entries(
    source_guard, occupied_kind: str
) -> None:
    root = source_guard.root
    old = root / "Old"
    old.mkdir()
    (old / "contents").write_text("source", encoding="utf-8")
    occupied = root / "New"
    if occupied_kind == "file":
        occupied.write_text("do not replace", encoding="utf-8")
    else:
        occupied.mkdir()
        (occupied / "contents").write_text("keep", encoding="utf-8")
    source_guard.seal()

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.rename_destination_folder(root, "Old", "New")

    assert caught.value.reason is FileSystemErrorReason.NAME_CONFLICT
    assert (old / "contents").read_text(encoding="utf-8") == "source"
    if occupied_kind == "file":
        assert occupied.read_text(encoding="utf-8") == "do not replace"
    else:
        assert (occupied / "contents").read_text(encoding="utf-8") == "keep"


def test_rename_rejects_link_and_reports_unsupported_noreplace(
    source_guard, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = source_guard.root
    real = root / "Real"
    real.mkdir()
    try:
        (root / "Linked").symlink_to(real, target_is_directory=True)
    except OSError as error:
        source_guard.seal()
        pytest.skip(f"symlink creation is unavailable: {error}")
    source_guard.seal(allowed_destinations={"Real", "Renamed"})

    with pytest.raises(FileSystemError) as linked:
        LocalFileSystem.rename_destination_folder(root, "Linked", "Renamed")
    assert linked.value.reason is FileSystemErrorReason.DESTINATION_LINK

    if os.name != "nt":

        def unsupported(*_args, **_kwargs):
            raise OSError(errno.ENOSYS, "no atomic no-replace rename")

        monkeypatch.setattr(filesystem, "_ctypes_no_replace", unsupported)
        with pytest.raises(FileSystemError) as unavailable:
            LocalFileSystem.rename_destination_folder(root, "Real", "Renamed")
        assert unavailable.value.reason is FileSystemErrorReason.FINALIZE_UNSUPPORTED
        assert real.is_dir()
        assert not (root / "Renamed").exists()


def test_destination_entries_classify_hidden_files_directories_and_links(source_guard) -> None:
    root = source_guard.root
    destination = root / "Best"
    destination.mkdir()
    (destination / "photo.jpg").write_bytes(b"image")
    (destination / ".hidden").write_text("hidden", encoding="utf-8")
    (destination / "nested").mkdir()
    if hasattr(os, "mkfifo"):
        os.mkfifo(destination / "pipe")
    try:
        (destination / "linked").symlink_to(root / "photo.jpg")
    except OSError as error:
        source_guard.seal(allowed_destinations={"Best"})
        pytest.skip(f"symlink creation is unavailable: {error}")
    source_guard.seal(allowed_destinations={"Best"})

    entries = LocalFileSystem.list_destination_entries(root, destination)

    classified = {(entry.name, entry.kind) for entry in entries}
    assert classified >= {
        ("photo.jpg", EntryKind.FILE),
        (".hidden", EntryKind.FILE),
        ("nested", EntryKind.DIRECTORY),
        ("linked", EntryKind.LINK),
    }
    if hasattr(os, "mkfifo"):
        assert ("pipe", EntryKind.OTHER) in classified


def test_remove_empty_destination_folder_and_refuse_nonempty(source_guard) -> None:
    root = source_guard.root
    empty = root / "Empty"
    empty.mkdir()
    nonempty = root / "Nonempty"
    nonempty.mkdir()
    child = nonempty / ".hidden"
    child.write_bytes(b"keep")
    source_guard.seal(allowed_destinations={"Empty", "Nonempty"})

    LocalFileSystem.remove_empty_destination_folder(root, "Empty")
    assert not empty.exists()
    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.remove_empty_destination_folder(root, "Nonempty")
    assert caught.value.reason is FileSystemErrorReason.FOLDER_NOT_EMPTY
    assert child.read_bytes() == b"keep"


def test_remove_destination_folder_rejects_symlink(source_guard) -> None:
    root = source_guard.root
    real = root / "Real"
    real.mkdir()
    try:
        (root / "Linked").symlink_to(real, target_is_directory=True)
    except OSError as error:
        source_guard.seal()
        pytest.skip(f"symlink creation is unavailable: {error}")
    source_guard.seal()

    with pytest.raises(FileSystemError) as caught:
        LocalFileSystem.remove_empty_destination_folder(root, "Linked")
    assert caught.value.reason is FileSystemErrorReason.DESTINATION_LINK
    assert real.is_dir()
