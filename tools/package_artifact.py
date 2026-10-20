"""Create the named platform archive and a SHA-256 digest."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("version")
    parser.add_argument("platform", choices=("linux", "windows", "macos"))
    parser.add_argument("architecture", choices=("x86_64", "arm64"))
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if not args.artifact.exists():
        parser.error(f"artifact path does not exist: {args.artifact}")

    args.output.mkdir(parents=True, exist_ok=True)
    extension = ".tar.gz" if args.platform == "linux" else ".zip"
    archive = args.output / (
        f"VueChoixGarde-{args.version}-{args.platform}-{args.architecture}{extension}"
    )
    if archive.exists():
        archive.unlink()
    if args.platform == "linux":
        with tarfile.open(archive, "w:gz") as output:
            output.add(args.artifact, arcname=args.artifact.name)
    elif args.platform == "macos" and sys.platform == "darwin":
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(args.artifact),
                str(archive),
            ],
            check=True,
        )
    else:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for path in sorted(args.artifact.rglob("*")):
                if path.is_file():
                    output.write(path, Path(args.artifact.name) / path.relative_to(args.artifact))
    digest = _sha256(archive)
    (args.output / f"{archive.name}.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="ascii"
    )
    print(f"{archive} {archive.stat().st_size} bytes sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
