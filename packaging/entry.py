"""PyInstaller entry point with a non-interactive release smoke test."""

from __future__ import annotations

import os
import sys
import tempfile
from importlib.metadata import version
from importlib.resources import as_file, files
from io import BytesIO
from pathlib import Path


def _smoke_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    from vuechoixgarde.bootstrap import create_runtime
    from vuechoixgarde.ports.log import LogEvent, LogLevel
    from vuechoixgarde.ui.main_window import MainWindow
    from vuechoixgarde.ui.sound import SoundPlayer
    from vuechoixgarde.ui.texts import set_language, text

    runtime = None
    window = None
    result = "failed"
    try:
        app = QApplication.instance() or QApplication(["VueChoixGarde-smoke-test"])
        with tempfile.TemporaryDirectory(prefix="vuechoixgarde-smoke-") as directory:
            runtime = create_runtime(Path(directory) / "app-data", damaged_choice=False)
            app.processEvents()
            for language in ("de", "en", "fr"):
                set_language(language)
                if not text("app_title"):
                    raise RuntimeError(f"empty {language} catalog")
            set_language(runtime.settings.language)

            with as_file(
                files("vuechoixgarde").joinpath("resources", "sounds", "added.wav")
            ) as wav:
                if not wav.is_file():
                    raise RuntimeError("bundled WAV resource is missing")

            buffer = BytesIO()
            Image.new("RGB", (2, 2), (20, 80, 140)).save(buffer, format="JPEG")
            buffer.seek(0)
            with Image.open(buffer) as image:
                image.load()
                if image.size != (2, 2):
                    raise RuntimeError("in-memory JPEG decode returned an unexpected size")

            heif_available = (
                __import__("importlib.util", fromlist=["find_spec"]).find_spec("pi_heif")
                is not None
            )
            if heif_available:
                from pi_heif import register_heif_opener

                register_heif_opener()

            window = MainWindow(runtime)
            SoundPlayer(window)
            window.show()
            app.processEvents()
            if not window.isVisible():
                raise RuntimeError("main window did not become visible")
            result = "passed"
            runtime.logger.log(
                LogLevel.INFO,
                LogEvent.APP_START,
                "packaged smoke test passed",
                version=version("vuechoixgarde"),
                heif_plugin_available=heif_available,
            )
        return 0
    except Exception as error:
        if runtime is not None:
            runtime.logger.log(
                LogLevel.ERROR,
                LogEvent.ERROR,
                "packaged smoke test failed",
                reason=type(error).__name__,
            )
        print(f"VueChoixGarde smoke test failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        if window is not None:
            window.workers.shutdown()
        if runtime is not None:
            runtime.shutdown()
        print(f"VueChoixGarde smoke test {result}")


def main() -> int:
    """Start the normal application or run the packaged smoke test."""
    if "--smoke-test" in sys.argv[1:]:
        return _smoke_test()
    from vuechoixgarde.__main__ import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
