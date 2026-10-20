# PyInstaller one-folder build for Linux, Windows and Apple-silicon macOS.
from pathlib import Path
import sys

import PySide6
import pi_heif
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
SOURCE = ROOT / "src" / "vuechoixgarde"
QT_TRANSLATIONS = Path(PySide6.__file__).parent / "Qt" / "translations"

_datas = [
    (str(path), f"vuechoixgarde/{path.parent.relative_to(SOURCE).as_posix()}")
    for path in sorted((SOURCE / "i18n").glob("*.json"))
]
_datas.extend(
    (
        (str(SOURCE / "resources" / "dark.qss"), "vuechoixgarde/resources"),
        (str(SOURCE / "resources" / "sounds" / "added.wav"), "vuechoixgarde/resources/sounds"),
        (str(SOURCE / "resources" / "sounds" / "README.txt"), "vuechoixgarde/resources/sounds"),
        (str(ROOT / "README.md"), "."),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    )
)
for _language in ("de", "fr"):
    _translation = QT_TRANSLATIONS / f"qtbase_{_language}.qm"
    if not _translation.is_file():
        raise SystemExit(f"Required Qt translation is missing: {_translation}")
    _datas.append((str(_translation), "PySide6/Qt/translations"))

_binaries = []
_heif_lib_dir = Path(pi_heif.__file__).parent.parent / "pi_heif.libs"
if _heif_lib_dir.is_dir():
    for _library in _heif_lib_dir.iterdir():
        if _library.is_file() and (
            _library.suffix.lower() in {".dll", ".dylib"} or ".so" in _library.name
        ):
            _binaries.append((str(_library), "."))

_metadata = [
    metadata
    for package in (
        "vuechoixgarde",
        "PySide6",
        "PySide6_Essentials",
        "PySide6_Addons",
        "shiboken6",
        "Pillow",
        "pi-heif",
        "filelock",
        "platformdirs",
    )
    for metadata in copy_metadata(package)
]

_hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtNetwork",
    "_pi_heif",
    *collect_submodules("PIL"),
    *collect_submodules("pi_heif"),
]
_excludes = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
]

_analysis = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=_binaries,
    datas=_datas + _metadata,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
    noarchive=False,
)

_filtered_qt_dependencies = (
    "libssl",
    "libcrypto",
    ".dll/libssl-",
    "/plugins/tls/",
    "qopensslbackend",
    "qcertonlybackend",
    "networkinformation",
    "libqnetworklistmanager",
)


def _keep_runtime_entry(entry: tuple) -> bool:
    normalized = "/".join(str(part) for part in entry[:2]).casefold().replace("\\", "/")
    return not any(marker in normalized for marker in _filtered_qt_dependencies)


_analysis.binaries = [entry for entry in _analysis.binaries if _keep_runtime_entry(entry)]
_analysis.datas = [entry for entry in _analysis.datas if _keep_runtime_entry(entry)]

_pyz = PYZ(_analysis.pure)
_exe = EXE(
    _pyz,
    _analysis.scripts,
    [],
    exclude_binaries=True,
    name="VueChoixGarde",
    icon=(str(ROOT / "build" / "VueChoixGarde.ico") if sys.platform == "win32" else None),
    version_file=(
        str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None
    ),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
_coll = COLLECT(
    _exe,
    _analysis.binaries,
    _analysis.datas,
    strip=False,
    upx=False,
    name="VueChoixGarde",
)
if sys.platform == "darwin":
    _bundle = BUNDLE(
        _coll,
        name="VueChoixGarde.app",
        icon=str(ROOT / "build" / "VueChoixGarde.icns"),
        bundle_identifier="org.vuechoixgarde.app",
        info_plist={"NSHighResolutionCapable": True},
    )
