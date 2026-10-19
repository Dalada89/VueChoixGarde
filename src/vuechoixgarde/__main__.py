"""Start the local Qt desktop application."""

import sys
import traceback
from types import TracebackType

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QMessageBox

from vuechoixgarde.bootstrap import Runtime, create_runtime
from vuechoixgarde.ports.log import LogEvent, LogLevel
from vuechoixgarde.ui.main_window import MainWindow
from vuechoixgarde.ui.texts import text


def main() -> int:
    """Compose adapters, present the main window and run Qt's event loop."""
    application = QApplication(sys.argv)
    runtime: Runtime | None = None
    try:
        runtime = create_runtime(locale_name=QLocale.system().name())
        window = MainWindow(runtime)
        window.show()
    except Exception as error:
        if runtime is not None:
            runtime.logger.log(
                LogLevel.ERROR,
                LogEvent.ERROR,
                "application startup failed",
                reason=type(error).__name__,
            )
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(text("error_title"))
        box.setText(text("error_title"))
        box.setDetailedText(str(error))
        box.exec()
        if runtime is not None:
            runtime.shutdown()
        return 1

    previous_hook = sys.excepthook

    def handle_exception(
        exception_type: type[BaseException],
        error: BaseException,
        traceback_value: TracebackType | None,
    ) -> None:
        if runtime is not None:
            runtime.logger.log(
                LogLevel.ERROR,
                LogEvent.ERROR,
                "unhandled application exception",
                reason=exception_type.__name__,
            )
        traceback.print_exception(exception_type, error, traceback_value)
        box = QMessageBox(window)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(text("error_title"))
        box.setText(text("error_title"))
        box.setDetailedText(str(error))
        box.exec()
        previous_hook(exception_type, error, traceback_value)

    sys.excepthook = handle_exception
    try:
        return application.exec()
    finally:
        sys.excepthook = previous_hook
