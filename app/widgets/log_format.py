"""Color-aware console logging helpers for VXPEngine."""
from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

ERROR_COLOR = QColor("#FF6B72")
WARNING_COLOR = QColor("#F5B84B")
SUCCESS_COLOR = QColor("#62D690")
INFO_COLOR = QColor("#D7DFEB")

_ERROR_PATTERNS = (
    r"\[error\]",
    r"\berror\b",
    r"\bexception\b",
    r"\btraceback\b",
    r"build failed",
    r"\bfailed\b",
    r"\bfailure\b",
    r"thất bại",
    r"\blỗi\b",
    r"cannot ",
    r"could not ",
    r"not recognized as an internal or external command",
)
_WARNING_PATTERNS = (
    r"\[warning\]",
    r"\bwarning\b",
    r"\bwarn\b",
    r"cảnh báo",
    r"deprecated",
)
_SUCCESS_PATTERNS = (
    r"\[success\]",
    r"build successful",
    r"\bsuccessful\b",
    r"\bsucceeded\b",
    r"hoàn tất",
    r"thành công",
    r"mã thoát 0",
    r"exit code 0",
    r"loaded successfully",
    r"up-to-date",
    r"\bready\b",
)


def classify_log_line(line: str) -> str:
    """Return error, warning, success or info for a single log line."""
    value = line.strip().lower()
    if re.search(r"\b(?:0|no) errors?\b|không có lỗi", value):
        return "success"
    if re.search(r"\b(?:0|no) warnings?\b|không có cảnh báo", value):
        return "success"
    if any(re.search(pattern, value) for pattern in _ERROR_PATTERNS):
        return "error"
    if any(re.search(pattern, value) for pattern in _WARNING_PATTERNS):
        return "warning"
    if any(re.search(pattern, value) for pattern in _SUCCESS_PATTERNS):
        return "success"
    return "info"


def _format_for(level: str) -> QTextCharFormat:
    text_format = QTextCharFormat()
    if level == "error":
        text_format.setForeground(ERROR_COLOR)
        text_format.setFontWeight(QFont.Weight.DemiBold)
    elif level == "warning":
        text_format.setForeground(WARNING_COLOR)
        text_format.setFontWeight(QFont.Weight.DemiBold)
    elif level == "success":
        text_format.setForeground(SUCCESS_COLOR)
        text_format.setFontWeight(QFont.Weight.DemiBold)
    else:
        text_format.setForeground(INFO_COLOR)
    return text_format


def append_colored_log(editor: QPlainTextEdit, text: str) -> None:
    """Append multiline text while coloring each line by detected status."""
    if not text:
        return
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.rstrip("\n").split("\n")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    has_existing_text = not editor.document().isEmpty()

    for index, line in enumerate(lines):
        if has_existing_text or index > 0:
            cursor.insertBlock()
        cursor.insertText(line, _format_for(classify_log_line(line)))

    editor.setTextCursor(cursor)
    editor.ensureCursorVisible()
