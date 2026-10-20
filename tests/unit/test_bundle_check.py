import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "check_bundle.py"


def _scan(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle)], capture_output=True, text=True, check=False
    )


def test_bundle_scan_ignores_documentation_mentions(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "THIRD_PARTY_NOTICES.md").write_text(
        "x265 and QtNetwork are not bundled", encoding="utf-8"
    )

    result = _scan(bundle)

    assert result.returncode == 0
    assert "scan passed" in result.stdout


def test_qtnetwork_is_allowed_with_qtmultimedia(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "Qt6Network.dll").write_bytes(b"network module")
    (bundle / "Qt6Multimedia.dll").write_bytes(b"multimedia module")

    result = _scan(bundle)

    assert result.returncode == 0
    assert "QtMultimedia dependency" in result.stdout


def test_qtnetwork_without_qtmultimedia_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "Qt6Network.dll").write_bytes(b"network module")

    result = _scan(bundle)

    assert result.returncode == 1
    assert "unexplained QtNetwork" in result.stdout


def test_tls_libraries_and_plugins_are_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    tls = bundle / "PySide6" / "Qt" / "plugins" / "tls"
    tls.mkdir(parents=True)
    (bundle / "Qt6Network.dll").write_bytes(b"network module")
    (bundle / "Qt6Multimedia.dll").write_bytes(b"multimedia module")
    (bundle / "libssl.so.3").write_bytes(b"TLS")
    (tls / "libqopensslbackend.so").write_bytes(b"TLS plugin")

    result = _scan(bundle)

    assert result.returncode == 1
    assert "libssl" in result.stdout
    assert "plugins/tls/" in result.stdout


def test_qt_websockets_are_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "Qt6WebSockets.dll").write_bytes(b"websocket module")

    result = _scan(bundle)

    assert result.returncode == 1
    assert "qt6websockets" in result.stdout


def test_x265_filename_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "libx265.so").write_bytes(b"encoder")

    result = _scan(bundle)

    assert result.returncode == 1
    assert "x265" in result.stdout


def test_x265_encoder_binary_symbol_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "libdecoder.so").write_bytes(b"x265_encoder_open")

    result = _scan(bundle)

    assert result.returncode == 1
    assert "x265_encoder_open" in result.stdout
