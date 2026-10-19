"""Load startup data while leaving damaged stores untouched until explicit acceptance."""

from vuechoixgarde.app.results import StartupReport
from vuechoixgarde.ports.log import EventLogger, LogEvent, LogLevel
from vuechoixgarde.ports.models import LoadStatus, Settings
from vuechoixgarde.ports.settings import SettingsStore
from vuechoixgarde.ports.state import StateStore


def load_startup(
    settings_store: SettingsStore,
    state_store: StateStore,
    *,
    locale_name: str | None = None,
    logger: EventLogger | None = None,
) -> StartupReport:
    """Load both stores; damaged data is only reported, never reset in this function."""
    settings_result = settings_store.load(locale_name)
    state_result = state_store.load()
    settings_damaged = settings_result.status is LoadStatus.DAMAGED
    state_damaged = state_result.status is LoadStatus.DAMAGED
    _safe_log(
        logger,
        LogLevel.WARNING if settings_damaged or state_damaged else LogLevel.INFO,
        LogEvent.DAMAGED_DATA if settings_damaged or state_damaged else LogEvent.APP_START,
        "application data requires attention"
        if settings_damaged or state_damaged
        else "application started",
        settings_damaged=settings_damaged,
        state_damaged=state_damaged,
    )
    return StartupReport(
        settings_status=settings_result.status.value,
        state_status=state_result.status.value,
        settings=settings_result.settings,
        settings_damaged=settings_damaged,
        state_damaged=state_damaged,
        register_available=state_result.register_available,
    )


def accept_damaged_data(
    report: StartupReport,
    settings_store: SettingsStore,
    state_store: StateStore,
    *,
    locale_name: str | None = None,
    logger: EventLogger | None = None,
) -> StartupReport:
    """Quarantine damaged stores only after the user explicitly chooses defaults."""
    settings: Settings | None = report.settings if isinstance(report.settings, Settings) else None
    settings_damaged = report.settings_damaged
    state_damaged = report.state_damaged
    settings_status = report.settings_status
    state_status = report.state_status
    if settings_damaged:
        settings_store.reset_damaged()
        loaded_settings = settings_store.load(locale_name)
        settings = loaded_settings.settings
        settings_damaged = loaded_settings.status is LoadStatus.DAMAGED
        settings_status = loaded_settings.status.value
    if state_damaged:
        state_store.reset_damaged()
        state_result = state_store.load()
        state_damaged = state_result.status is LoadStatus.DAMAGED
        state_status = state_result.status.value
        register_available = state_result.register_available
    else:
        register_available = report.register_available
    _safe_log(
        logger,
        LogLevel.INFO if not settings_damaged and not state_damaged else LogLevel.ERROR,
        LogEvent.DAMAGED_DATA,
        "default data accepted",
        settings_damaged=settings_damaged,
        state_damaged=state_damaged,
    )
    return StartupReport(
        settings_status=settings_status,
        state_status=state_status,
        settings=settings,
        settings_damaged=settings_damaged,
        state_damaged=state_damaged,
        register_available=register_available,
        accepted_defaults=True,
    )


def stop_application(logger: EventLogger | None = None) -> None:
    """Emit a privacy-safe shutdown event without allowing logger errors to escape."""
    _safe_log(logger, LogLevel.INFO, LogEvent.APP_STOP, "application stopped")


def decline_damaged_data(report: StartupReport) -> StartupReport:
    """Keep damaged files unchanged and prevent use of an unavailable copy register."""
    return StartupReport(
        report.settings_status,
        report.state_status,
        report.settings,
        report.settings_damaged,
        report.state_damaged,
        False if report.state_damaged else report.register_available,
        accepted_defaults=False,
    )


def _safe_log(
    logger: EventLogger | None,
    level: LogLevel,
    event: LogEvent,
    message: str,
    **fields: object,
) -> None:
    if logger is None:
        return
    try:
        logger.log(level, event, message, **fields)
    except Exception:
        return
