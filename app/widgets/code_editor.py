"""IDE-style source editor used by VXPEngine.

Features are dependency-free: line numbers, C/C++ highlighting, breakpoint
markers, build diagnostics, auto indentation, bracket pairing and common editing
shortcuts. The editor intentionally stays lightweight so it can run inside the
PySide6 desktop shell without embedding a full language server.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from PySide6.QtCore import QRect, QSize, Qt, QRegularExpression, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QKeySequence,
    QPainter,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
    QSyntaxHighlighter,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from .custom_dialog import IntInputDialog


@dataclass(frozen=True)
class HighlightRule:
    expression: QRegularExpression
    text_format: QTextCharFormat


def _format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    result = QTextCharFormat()
    result.setForeground(QColor(color))
    if bold:
        result.setFontWeight(QFont.Weight.DemiBold)
    result.setFontItalic(italic)
    return result


class SourceHighlighter(QSyntaxHighlighter):
    """Small dependency-free highlighter for C and C++."""

    GENERIC_KEYWORDS = (
        "auto break case char const continue default do double else enum extern float for goto "
        "if inline int long register return short signed sizeof static struct switch typedef union "
        "unsigned void volatile while bool true false nullptr new delete class namespace template "
        "typename using virtual public private protected this operator"
    ).split()
    CPP_KEYWORDS = (
        "alignas alignof and and_eq asm atomic_cancel atomic_commit atomic_noexcept auto bitand "
        "bitor bool break case catch char char8_t char16_t char32_t class compl concept const "
        "consteval constexpr constinit const_cast continue co_await co_return co_yield decltype "
        "default delete do double dynamic_cast else enum explicit export extern false float for "
        "friend goto if inline int long mutable namespace new noexcept not not_eq nullptr operator "
        "or or_eq private protected public reflexpr register reinterpret_cast requires return short "
        "signed sizeof static static_assert static_cast struct switch synchronized template this "
        "thread_local throw true try typedef typeid typename union unsigned using virtual void "
        "volatile wchar_t while xor xor_eq"
    ).split()

    def __init__(self, document, language: str = "text") -> None:
        super().__init__(document)
        self.language = language.lower()
        keyword_format = _format("#C792EA", bold=True)
        type_format = _format("#82AAFF")
        class_format = _format("#FFCB6B")
        function_format = _format("#82D2CE")
        number_format = _format("#F78C6C")
        string_format = _format("#C3E88D")
        annotation_format = _format("#89DDFF")
        comment_format = _format("#6A737D", italic=True)
        operator_format = _format("#89DDFF")
        preprocessor_format = _format("#F07178")

        keywords = self.CPP_KEYWORDS if self.language in {"c", "cpp", "c++", "h", "hpp"} else self.GENERIC_KEYWORDS
        keyword_pattern = r"\b(?:" + "|".join(map(re.escape, keywords)) + r")\b"
        self.rules: list[HighlightRule] = [
            HighlightRule(QRegularExpression(keyword_pattern), keyword_format),
            HighlightRule(
                QRegularExpression(
                    r"\b(?:int8_t|uint8_t|int16_t|uint16_t|int32_t|uint32_t|int64_t|uint64_t|size_t|"
                    r"VMINT|VMUINT|VMBYTE|VMWSTR|VMSTR|VMBOOL|VMCHAR|VMRESID|"
                    r"Engine|Scene|SceneManager|Actor|Entity|Renderer|Camera2D|Color|Vector2|Fixed16)\b"
                ),
                type_format,
            ),
            HighlightRule(QRegularExpression(r"\b[A-Z][A-Za-z0-9_]*\b"), class_format),
            HighlightRule(QRegularExpression(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()"), function_format),
            HighlightRule(
                QRegularExpression(r"\b(?:0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[fFdDlL]?)\b"),
                number_format,
            ),
            HighlightRule(QRegularExpression(r'"(?:\\.|[^"\\])*"'), string_format),
            HighlightRule(QRegularExpression(r"'(?:\\.|[^'\\])'"), string_format),
            HighlightRule(QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_]*"), annotation_format),
            HighlightRule(QRegularExpression(r"\b(?:true|false|null|nullptr)\b"), number_format),
            HighlightRule(QRegularExpression(r"(?:==|!=|<=|>=|&&|\|\||\+\+|--|->|::|[+\-*/%=&|!<>?:~^])"), operator_format),
            HighlightRule(QRegularExpression(r"//[^\n]*"), comment_format),
        ]
        if self.language in {"c", "cpp", "c++", "h", "hpp"}:
            self.rules.insert(0, HighlightRule(QRegularExpression(r"^\s*#\s*[A-Za-z_]+.*$"), preprocessor_format))

        self.comment_format = comment_format
        self.comment_start = QRegularExpression(r"/\*")
        self.comment_end = QRegularExpression(r"\*/")

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        for rule in self.rules:
            matches = rule.expression.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), rule.text_format)

        self.setCurrentBlockState(0)
        if self.previousBlockState() != 1:
            start_index = self.comment_start.match(text).capturedStart()
        else:
            start_index = 0
        while start_index >= 0:
            end_match = self.comment_end.match(text, start_index)
            end_index = end_match.capturedStart()
            if end_index < 0:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + end_match.capturedLength()
            self.setFormat(start_index, comment_length, self.comment_format)
            if end_index < 0:
                break
            start_index = self.comment_start.match(text, start_index + comment_length).capturedStart()


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("CodeLineNumberArea")
        self.setToolTip("Nhấp vào lề để bật/tắt breakpoint")

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.editor.paint_line_number_area(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.editor.toggle_breakpoint_at_y(int(event.position().y()))
            event.accept()
            return
        super().mousePressEvent(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit with common IDE behavior and debugger metadata."""

    breakpoint_toggled = Signal(int, bool)
    cursor_status_changed = Signal(int, int)

    def __init__(self, language: str = "text", parent=None) -> None:
        super().__init__(parent)
        self.language = language.lower()
        self.source_path: Path | None = None
        self.breakpoints: set[int] = set()
        self.diagnostics: dict[int, list[dict]] = {}
        self.setObjectName("CodeEditor")
        # Word wrap: không cuộn ngang — dòng dài tự xuống dòng theo chiều rộng.
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setFont(QFont("Cascadia Code", 10))
        self.setTabStopDistance(QFontMetricsF(self.font()).horizontalAdvance(" ") * 4)
        self.line_number_area = LineNumberArea(self)
        self.highlighter = SourceHighlighter(self.document(), language)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self._cursor_changed)
        self.update_line_number_area_width(0)
        self._update_extra_selections()

    def set_source_path(self, path: str | Path) -> None:
        self.source_path = Path(path).resolve()

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 28 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(contents.left(), contents.top(), self.line_number_area_width(), contents.height())
        )

    def _cursor_changed(self) -> None:
        cursor = self.textCursor()
        self.cursor_status_changed.emit(cursor.blockNumber() + 1, cursor.positionInBlock() + 1)
        self._update_extra_selections()
        self.line_number_area.update()

    def _update_extra_selections(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        if not self.isReadOnly():
            current = QTextEdit.ExtraSelection()
            current.format.setBackground(QColor("#151D2A"))
            current.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            current.cursor = self.textCursor()
            current.cursor.clearSelection()
            selections.append(current)

        # Diagnostics are intentionally subtle; the gutter icon conveys severity.
        for line_number, entries in self.diagnostics.items():
            block = self.document().findBlockByNumber(line_number - 1)
            if not block.isValid() or not entries:
                continue
            severity = str(entries[0].get("severity", "error")).lower()
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(block)
            selection.cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            selection.format.setBackground(QColor("#3A1E24" if severity == "error" else "#3A321D"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.format.setToolTip("\n".join(str(item.get("message", "")) for item in entries))
            selections.append(selection)

        for line_number in self.breakpoints:
            block = self.document().findBlockByNumber(line_number - 1)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(block)
            selection.cursor.clearSelection()
            selection.format.setBackground(QColor("#241B31"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selections.append(selection)
        self.setExtraSelections(selections)

    def set_diagnostics(self, diagnostics: list[dict]) -> None:
        grouped: dict[int, list[dict]] = {}
        for diagnostic in diagnostics:
            try:
                line = max(1, int(diagnostic.get("line", 1)))
            except (TypeError, ValueError):
                line = 1
            grouped.setdefault(line, []).append(dict(diagnostic))
        self.diagnostics = grouped
        self._update_extra_selections()
        self.line_number_area.update()

    def clear_diagnostics(self) -> None:
        self.diagnostics.clear()
        self._update_extra_selections()
        self.line_number_area.update()

    def set_breakpoints(self, line_numbers: set[int] | list[int]) -> None:
        self.breakpoints = {int(line) for line in line_numbers if int(line) > 0}
        self._update_extra_selections()
        self.line_number_area.update()

    def toggle_breakpoint(self, line_number: int) -> bool:
        line_number = max(1, min(int(line_number), max(1, self.blockCount())))
        if line_number in self.breakpoints:
            self.breakpoints.remove(line_number)
            enabled = False
        else:
            self.breakpoints.add(line_number)
            enabled = True
        self._update_extra_selections()
        self.line_number_area.update()
        self.breakpoint_toggled.emit(line_number, enabled)
        return enabled

    def toggle_breakpoint_at_y(self, y: int) -> None:
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid():
            bottom = top + round(self.blockBoundingRect(block).height())
            if top <= y < bottom:
                self.toggle_breakpoint(block.blockNumber() + 1)
                return
            if top > self.viewport().height():
                break
            block = block.next()
            top = bottom

    def paint_line_number_area(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#0B1018"))
        painter.setPen(QColor("#313B4D"))
        painter.drawLine(
            self.line_number_area.width() - 1,
            event.rect().top(),
            self.line_number_area.width() - 1,
            event.rect().bottom(),
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        marker_x = 8
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_number = block_number + 1
                center_y = top + self.fontMetrics().height() // 2
                if line_number in self.breakpoints:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#D75A74"))
                    painter.drawEllipse(marker_x - 4, center_y - 4, 8, 8)
                entries = self.diagnostics.get(line_number, [])
                if entries:
                    severity = str(entries[0].get("severity", "error")).lower()
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#F0646A" if severity == "error" else "#E5B84E"))
                    painter.drawRect(16, center_y - 4, 3, 8)
                is_current = block_number == self.textCursor().blockNumber()
                painter.setPen(QColor("#DCE7F7") if is_current else QColor("#647086"))
                painter.drawText(
                    20,
                    top,
                    self.line_number_area.width() - 27,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(line_number),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def go_to_line(self, line_number: int | None = None, column: int = 1) -> None:
        if line_number is None:
            value, accepted = IntInputDialog.get_int(
                self,
                "Đi tới dòng",
                "Số dòng:",
                self.textCursor().blockNumber() + 1,
                1,
                max(1, self.blockCount()),
            )
            if not accepted:
                return
            line_number = value
        block = self.document().findBlockByNumber(max(0, int(line_number) - 1))
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.setPosition(min(block.position() + max(0, int(column) - 1), block.position() + max(0, block.length() - 1)))
            self.setTextCursor(cursor)
            self.centerCursor()
            self.setFocus()

    def toggle_line_comment(self) -> None:
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        first_block = cursor.blockNumber()
        cursor.setPosition(end)
        last_block = cursor.blockNumber()
        blocks: list[QTextBlock] = []
        block = self.document().findBlockByNumber(first_block)
        while block.isValid() and block.blockNumber() <= last_block:
            blocks.append(block)
            block = block.next()
        non_empty = [block.text() for block in blocks if block.text().strip()]
        remove = bool(non_empty) and all(text.lstrip().startswith("//") for text in non_empty)
        edit = self.textCursor()
        edit.beginEditBlock()
        for block in reversed(blocks):
            text = block.text()
            if not text.strip():
                continue
            block_cursor = QTextCursor(block)
            indent = len(text) - len(text.lstrip())
            block_cursor.setPosition(block.position() + indent)
            if remove:
                if text[indent:].startswith("// "):
                    block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 3)
                else:
                    block_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 2)
                block_cursor.removeSelectedText()
            else:
                block_cursor.insertText("// ")
        edit.endEditBlock()

    def _indent_selection(self, unindent: bool = False) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            if unindent:
                block = cursor.block()
                text = block.text()
                count = 4 if text.startswith("    ") else 1 if text.startswith("\t") else 0
                if count:
                    cursor.setPosition(block.position())
                    cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, count)
                    cursor.removeSelectedText()
            else:
                cursor.insertText("    ")
            return
        start_block = self.document().findBlock(cursor.selectionStart())
        end_block = self.document().findBlock(cursor.selectionEnd())
        edit = self.textCursor()
        edit.beginEditBlock()
        block = end_block
        while block.isValid() and block.blockNumber() >= start_block.blockNumber():
            line_cursor = QTextCursor(block)
            if unindent:
                text = block.text()
                count = 4 if text.startswith("    ") else 1 if text.startswith("\t") else 0
                if count:
                    line_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, count)
                    line_cursor.removeSelectedText()
            else:
                line_cursor.insertText("    ")
            if block.blockNumber() == start_block.blockNumber():
                break
            block = block.previous()
        edit.endEditBlock()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        modifiers = event.modifiers()
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if control and event.key() == Qt.Key.Key_Slash:
            self.toggle_line_comment()
            event.accept()
            return
        if control and event.key() == Qt.Key.Key_G:
            self.go_to_line()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Tab:
            self._indent_selection(False)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Backtab or (shift and event.key() == Qt.Key.Key_Tab):
            self._indent_selection(True)
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            cursor = self.textCursor()
            before = cursor.block().text()[: cursor.positionInBlock()]
            indent = re.match(r"\s*", before).group(0)
            extra = "    " if before.rstrip().endswith("{") else ""
            cursor.insertText("\n" + indent + extra)
            self.setTextCursor(cursor)
            event.accept()
            return

        pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
        text = event.text()
        if text in pairs and not control:
            cursor = self.textCursor()
            if cursor.hasSelection():
                selected = cursor.selectedText()
                cursor.insertText(text + selected + pairs[text])
            else:
                cursor.insertText(text + pairs[text])
                cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.setTextCursor(cursor)
            event.accept()
            return
        if text in pairs.values() and not control:
            cursor = self.textCursor()
            document_text = self.document().characterAt(cursor.position())
            if document_text == text:
                cursor.movePosition(QTextCursor.MoveOperation.Right)
                self.setTextCursor(cursor)
                event.accept()
                return
        super().keyPressEvent(event)
