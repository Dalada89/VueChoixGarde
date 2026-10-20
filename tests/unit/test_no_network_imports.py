import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCAN_ROOTS = (ROOT / "src", ROOT / "packaging", ROOT / "tools")
FORBIDDEN_ROOTS = {
    "socket",
    "urllib",
    "http",
    "ssl",
    "ftplib",
    "smtplib",
    "requests",
    "httpx",
    "aiohttp",
    "telnetlib",
    "xmlrpc",
    "websocket",
    "websockets",
}


def _import_name_is_forbidden(name: str) -> bool:
    if name == "PySide6.QtNetwork" or name.startswith("PySide6.QtNetwork."):
        return True
    return name.split(".", maxsplit=1)[0] in FORBIDDEN_ROOTS


def _dynamic_qtnetwork_import(node: ast.Call) -> bool:
    function = node.func
    is_import_module = (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
        and isinstance(function.value, ast.Name)
        and function.value.id == "importlib"
    ) or (isinstance(function, ast.Name) and function.id == "import_module")
    return (
        is_import_module
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "PySide6.QtNetwork"
    )


def test_application_and_packaging_code_do_not_import_network_modules() -> None:
    findings: list[str] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    findings.extend(
                        f"{path}:{node.lineno}: import {alias.name}"
                        for alias in node.names
                        if _import_name_is_forbidden(alias.name)
                    )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if _import_name_is_forbidden(module):
                        findings.append(f"{path}:{node.lineno}: from {module} import …")
                    imports_qtnetwork = any(alias.name == "QtNetwork" for alias in node.names)
                    if module == "PySide6" and imports_qtnetwork:
                        findings.append(f"{path}:{node.lineno}: from PySide6 import QtNetwork")
                elif isinstance(node, ast.Call) and _dynamic_qtnetwork_import(node):
                    findings.append(f"{path}:{node.lineno}: dynamic PySide6.QtNetwork import")

    assert not findings, "Network imports violate NFR-005:\n" + "\n".join(findings)
