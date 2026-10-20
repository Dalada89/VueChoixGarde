"""Generate the project's original application icon and Windows version resource."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def _icon() -> Image.Image:
    image = Image.new("RGBA", (1024, 1024), (43, 43, 43, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 80, 944, 944), radius=180, fill=(56, 56, 56, 255))
    draw.rounded_rectangle((205, 245, 685, 785), radius=36, fill=(242, 242, 242, 255))
    draw.rounded_rectangle((340, 165, 820, 705), radius=36, fill=(220, 232, 245, 255))
    draw.rounded_rectangle((275, 305, 755, 845), radius=36, fill=(255, 255, 255, 255))
    draw.rectangle((275, 650, 755, 845), fill=(111, 168, 220, 255))
    draw.ellipse((430, 440, 600, 610), fill=(229, 115, 115, 255))
    return image


def _version_resource(version: str) -> str:
    parts = tuple(int(part) for part in version.split("."))
    if len(parts) != 3 or any(part > 65535 for part in parts):
        raise ValueError(f"Windows version resource requires a three-part version: {version}")
    version_tuple = (*parts, 0)
    version_text = f"{version}.0"
    return f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u"040904B0",
        [StringStruct(u"CompanyName", u"VueChoixGarde contributors"),
         StringStruct(u"FileDescription", u"VueChoixGarde image sorting application"),
         StringStruct(u"FileVersion", u"{version_text}"),
         StringStruct(u"InternalName", u"VueChoixGarde"),
         StringStruct(u"OriginalFilename", u"VueChoixGarde.exe"),
         StringStruct(u"ProductName", u"VueChoixGarde"),
         StringStruct(u"ProductVersion", u"{version_text}")]
      )
    ]),
    VarFileInfo([VarStruct(u"Translation", [1033, 1200])])
  ]
)\n'''


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("project version must use MAJOR.MINOR.PATCH")
    icon = _icon()
    png = BUILD / "VueChoixGarde.png"
    icon.save(png)
    icon.save(
        BUILD / "VueChoixGarde.ico",
        format="ICO",
        sizes=[(size, size) for size in (16, 32, 48, 64, 128, 256)],
    )
    (ROOT / "packaging" / "version_info.txt").write_text(
        _version_resource(version), encoding="utf-8"
    )
    if sys.platform == "darwin":
        iconset = BUILD / "VueChoixGarde.iconset"
        iconset.mkdir(exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            icon.resize((size, size), Image.Resampling.LANCZOS).save(
                iconset / f"icon_{size}x{size}.png"
            )
            double = size * 2
            icon.resize((double, double), Image.Resampling.LANCZOS).save(
                iconset / f"icon_{size}x{size}@2x.png"
            )
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(BUILD / "VueChoixGarde.icns")],
            check=True,
        )


if __name__ == "__main__":
    main()
