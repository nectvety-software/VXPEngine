"""Static feature audit helpers for VXPEngine.

The audit intentionally avoids importing PySide6 so it can run in CI and in
minimal repair environments. It checks the most common causes of UI controls
that appear but do not work: duplicate method definitions, empty handlers,
missing ``self.method`` signal targets, and duplicate shortcut declarations.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


INHERITED_QT_CALLBACKS = {
    "accept", "reject", "close", "hide", "show", "showMinimized",
    "showMaximized", "showNormal", "deleteLater", "toggle",
}


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    code: str
    file: str
    line: int
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _effective_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    return [statement for statement in node.body if not _is_docstring(statement)]


def _shortcut_literals(class_node: ast.ClassDef) -> list[tuple[str, int]]:
    values: list[tuple[str, int]] = []
    for call in ast.walk(class_node):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "setShortcut":
            continue
        if not call.args:
            continue
        argument = call.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            values.append((argument.value.strip().lower(), call.lineno))
        elif (
            isinstance(argument, ast.Call)
            and isinstance(argument.func, ast.Name)
            and argument.func.id == "QKeySequence"
            and argument.args
            and isinstance(argument.args[0], ast.Constant)
            and isinstance(argument.args[0].value, str)
        ):
            values.append((argument.args[0].value.strip().lower(), call.lineno))
    return values


def _signal_targets(class_node: ast.ClassDef) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    for call in ast.walk(class_node):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "connect":
            continue
        if not call.args:
            continue
        callback = call.args[0]
        if (
            isinstance(callback, ast.Attribute)
            and isinstance(callback.value, ast.Name)
            and callback.value.id == "self"
        ):
            targets.append((callback.attr, callback.lineno))
    return targets


def audit_engine_source(app_root: str | Path) -> list[AuditFinding]:
    root = Path(app_root).resolve()
    findings: list[AuditFinding] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as error:
            line = getattr(error, "lineno", 1) or 1
            findings.append(AuditFinding("error", "parse-error", relative, line, str(error)))
            continue

        module_names: dict[str, list[int]] = defaultdict(list)
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                module_names[node.name].append(node.lineno)
        for name, lines in module_names.items():
            if len(lines) > 1:
                findings.append(AuditFinding(
                    "error", "duplicate-module-symbol", relative, lines[-1],
                    f"'{name}' được định nghĩa lặp tại các dòng {lines}.",
                ))

        for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            methods: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = defaultdict(list)
            for child in class_node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods[child.name].append(child)
            for name, definitions in methods.items():
                if len(definitions) > 1:
                    lines = [definition.lineno for definition in definitions]
                    findings.append(AuditFinding(
                        "error", "duplicate-method", relative, lines[-1],
                        f"{class_node.name}.{name} được định nghĩa lặp tại {lines}.",
                    ))
                for definition in definitions:
                    body = _effective_body(definition)
                    if not body or all(isinstance(item, ast.Pass) for item in body):
                        findings.append(AuditFinding(
                            "warning", "empty-handler", relative, definition.lineno,
                            f"{class_node.name}.{name} chưa có logic thực thi.",
                        ))

            available_methods = set(methods)
            for target, line in _signal_targets(class_node):
                if target not in available_methods and target not in INHERITED_QT_CALLBACKS:
                    findings.append(AuditFinding(
                        "error", "missing-callback", relative, line,
                        f"Signal nối tới self.{target}, nhưng class {class_node.name} không định nghĩa handler này.",
                    ))

            shortcuts: dict[str, list[int]] = defaultdict(list)
            for shortcut, line in _shortcut_literals(class_node):
                if shortcut:
                    shortcuts[shortcut].append(line)
            for shortcut, lines in shortcuts.items():
                if len(lines) > 1:
                    findings.append(AuditFinding(
                        "warning", "duplicate-shortcut", relative, lines[-1],
                        f"Phím tắt '{shortcut}' được khai báo lặp trong {class_node.name} tại {lines}.",
                    ))

    return findings


def summarize_findings(findings: Iterable[AuditFinding]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    counts["total"] = sum(counts.values())
    return counts


def format_audit_summary(findings: Iterable[AuditFinding], limit: int = 30) -> str:
    items = list(findings)
    counts = summarize_findings(items)
    lines = [
        "VXPEngine Feature Audit",
        f"Lỗi: {counts.get('error', 0)} · Cảnh báo: {counts.get('warning', 0)} · Tổng: {counts.get('total', 0)}",
    ]
    for finding in items[: max(0, limit)]:
        prefix = "ERROR" if finding.severity == "error" else "WARN"
        lines.append(f"[{prefix}] {finding.file}:{finding.line} · {finding.message}")
    if len(items) > limit:
        lines.append(f"… còn {len(items) - limit} mục khác.")
    if not items:
        lines.append("Không phát hiện handler rỗng, callback thiếu, method trùng hoặc shortcut trùng.")
    return "\n".join(lines)
