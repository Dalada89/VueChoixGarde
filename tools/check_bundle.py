"""Check frozen bundle names and contents against the release allowlist."""

from __future__ import annotations

import argparse
from pathlib import Path

_ALLOWED_WITH_MULTIMEDIA = ("qt6network", "qtnetwork")
_MULTIMEDIA_MARKERS = ("qt6multimedia", "qtmultimedia")
_FORBIDDEN_NAMES = (
    "qt6websockets",
    "qt5websockets",
    "qt6httpserver",
    "qt5httpserver",
    "qt6networkauth",
    "qt5networkauth",
    "qt6webengine",
    "qt5webengine",
    "qt6webchannel",
    "qt5webchannel",
    "qt6webview",
    "qt5webview",
    "qt6qml",
    "qt5qml",
    "qt6quick",
    "qt5quick",
    "libssl",
    "libcrypto",
    "ssleay",
    "plugins/tls/",
    "qopensslbackend",
    "qcertonlybackend",
    "networkinformation",
    "libqnetworklistmanager",
    "x265",
)
_FORBIDDEN_CONTENT = (b"x265_encoder_open", b"x265_encoder_encode")
_BINARY_SUFFIXES = {".dll", ".dylib", ".so", ".pyd", ".exe", ".zip", ".pyz", ".pyc"}


def _bundle_files(bundle: Path) -> list[Path]:
    if bundle.is_file():
        return [bundle]
    return [path for path in bundle.rglob("*") if path.is_file() and not path.is_symlink()]


def _content_findings(path: Path) -> list[str]:
    findings: set[str] = set()
    is_binary = path.suffix.lower() in _BINARY_SUFFIXES or bool(path.stat().st_mode & 0o111)
    if not is_binary:
        return []
    overlap = max(map(len, _FORBIDDEN_CONTENT)) - 1
    tail = b""
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(4 * 1024 * 1024):
                content = (tail + chunk).lower()
                for marker in _FORBIDDEN_CONTENT:
                    if marker in content:
                        findings.add(marker.decode())
                tail = content[-overlap:]
    except OSError as error:
        raise RuntimeError(f"cannot scan bundle file {path}: {error}") from error
    return sorted(findings)


def scan_bundle(bundle: Path) -> tuple[list[Path], list[tuple[Path, list[str]]], list[Path]]:
    """Return scanned files, failures and QtNetwork files allowed through Multimedia."""
    files = _bundle_files(bundle)
    names = {path: path.as_posix().casefold().replace("\\", "/") for path in files}
    has_multimedia = any(
        marker in name for name in names.values() for marker in _MULTIMEDIA_MARKERS
    )
    network_files = [
        path
        for path, name in names.items()
        if any(marker in name for marker in _ALLOWED_WITH_MULTIMEDIA)
    ]
    failures: dict[Path, set[str]] = {path: set() for path in files}

    for path, name in names.items():
        for marker in _FORBIDDEN_NAMES:
            if marker in name:
                failures[path].add(marker)
        failures[path].update(_content_findings(path))

    if network_files and not has_multimedia:
        for path in network_files:
            failures[path].add("unexplained QtNetwork (QtMultimedia not present)")

    failure_list = [(path, sorted(terms)) for path, terms in failures.items() if terms]
    allowed = network_files if has_multimedia else []
    return files, failure_list, allowed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    if not args.bundle.exists():
        parser.error(f"bundle does not exist: {args.bundle}")
    files, failures, allowed = scan_bundle(args.bundle)
    if failures:
        for path, terms in failures:
            print(f"Forbidden bundle content {','.join(terms)}: {path}")
        return 1
    for path in allowed:
        print(f"Allowed (QtMultimedia dependency): {path}")
    print(
        f"Bundle scan passed ({len(files)} files; QtNetwork only as QtMultimedia dependency; "
        "no TLS; no x265)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
