"""Pure command builders used by the Windows run/build pipeline."""
from __future__ import annotations

import os
from pathlib import Path


def windows_batch_invocation(
    working_dir: str | Path,
    executable: str | Path,
    arguments: list[str] | tuple[str, ...],
    *,
    comspec: str | None = None,
) -> tuple[str, list[str]]:
    """Return a safe ``cmd.exe`` invocation for a BAT/CMD file.

    The command is deliberately expressed as separate argv tokens.  Do not pass a
    pre-quoted command string to ``cmd /s /c`` because QProcess will quote that
    string again on Windows and paths containing spaces can become literal values
    such as ``\\\"C:\\My Project\\run_vxpemu.bat\\\"``.
    """

    cwd = Path(working_dir).expanduser().resolve(strict=False)
    script = Path(executable).expanduser().resolve(strict=False)
    if script.suffix.lower() not in {".bat", ".cmd"}:
        raise ValueError(f"Không phải Windows batch file: {script}")

    try:
        same_directory = script.parent == cwd
    except OSError:
        same_directory = False

    script_argument = f".\\{script.name}" if same_directory else str(script)
    program = (comspec or os.environ.get("COMSPEC") or "cmd.exe").strip()
    return program, ["/d", "/c", "call", script_argument, *map(str, arguments)]


def display_command(executable: str | Path, arguments: list[str] | tuple[str, ...]) -> str:
    """Return the concise command shown in the editor Console."""

    script = Path(executable)
    prefix = f"call .\\{script.name}" if script.suffix.lower() in {".bat", ".cmd"} else script.name
    suffix = " ".join(map(str, arguments)).strip()
    return f"{prefix} {suffix}".rstrip()
