"""Build diagnostic parsing shared by the editor and the VXP runner."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re


@dataclass(slots=True, frozen=True)
class Diagnostic:
    file: str
    line: int
    column: int
    severity: str
    message: str
    source: str = "compiler"

    def to_dict(self) -> dict:
        return asdict(self)


_DIAGNOSTIC_PATTERNS = (
    # GCC and Clang diagnostics on Windows/Unix:
    # C:\game\src\main.c:12: error: message
    # /game/src/game.c:12:5: warning: message
    re.compile(
        r"^(?P<file>.+?\.(?:c|cc|cpp|cxx|h|hh|hpp|hxx|m|mm))"
        r":(?P<line>\d+)(?::(?P<column>\d+))?:\s*"
        r"(?P<severity>fatal error|error|warning|note):\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
    # MSVC/clang-cl: C:\game\foo.cpp(12,5): error C2065: message
    re.compile(
        r"^(?P<file>.+?\.(?:c|cc|cpp|cxx|h|hh|hpp|hxx))"
        r"\((?P<line>\d+)(?:,(?P<column>\d+))?\):\s*"
        r"(?P<severity>fatal error|error|warning|note)(?:\s+[A-Z]+\d+)?:\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
    # CMake scripts and config files.
    re.compile(
        r"^(?P<file>.+?\.(?:cmake|xml|properties))"
        r":(?P<line>\d+)(?::(?P<column>\d+))?:\s*"
        r"(?P<severity>error|warning):\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
)

_NATIVE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".m", ".mm"
}
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def _normalize_path(raw_file: str, project_root: str | Path | None) -> Path:
    """Resolve relative compiler paths without corrupting Windows drive paths."""
    raw_file = raw_file.strip().strip('"')
    # Path.is_absolute() follows the host OS. During tests on Linux a Windows drive
    # path is not considered absolute, therefore detect it explicitly.
    if _WINDOWS_ABSOLUTE.match(raw_file):
        return Path(raw_file)
    path = Path(raw_file)
    if not path.is_absolute() and project_root:
        path = Path(project_root) / path
    try:
        return path.expanduser().resolve()
    except OSError:
        return path


def parse_diagnostic_line(line: str, project_root: str | Path | None = None) -> Diagnostic | None:
    text = line.strip()
    if not text:
        return None
    for pattern in _DIAGNOSTIC_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        path = _normalize_path(match.group("file"), project_root)
        severity = match.group("severity").lower()
        if severity == "fatal error":
            severity = "error"
        return Diagnostic(
            file=str(path),
            line=max(1, int(match.group("line"))),
            column=max(1, int(match.group("column") or 1)),
            severity=severity,
            message=match.group("message").strip(),
            source="native compiler" if path.suffix.lower() in _NATIVE_SUFFIXES else "build tool",
        )
    return None


def parse_diagnostics(text: str, project_root: str | Path | None = None) -> list[Diagnostic]:
    result: list[Diagnostic] = []
    seen: set[tuple[str, int, int, str, str]] = set()
    for line in text.splitlines():
        diagnostic = parse_diagnostic_line(line, project_root)
        if diagnostic is None:
            continue
        key = (
            diagnostic.file,
            diagnostic.line,
            diagnostic.column,
            diagnostic.severity,
            diagnostic.message,
        )
        if key not in seen:
            seen.add(key)
            result.append(diagnostic)
    return result
