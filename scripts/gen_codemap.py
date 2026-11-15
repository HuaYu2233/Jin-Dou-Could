#!/usr/bin/env python3
"""生成 backend/app 的符号索引 doc/codemap.md。"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "backend" / "app"
OUTPUT = ROOT / "doc" / "codemap.md"

MAX_SIGNATURE = 100


def first_doc_line(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    return doc.strip().splitlines()[0].strip() if doc.strip() else ""


def format_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    names = [a.arg for a in args.posonlyargs + args.args]
    if names and names[0] in {"self", "cls"}:
        names = names[1:]
    if args.vararg:
        names.append("*" + args.vararg.arg)
    if args.kwarg:
        names.append("**" + args.kwarg.arg)
    signature = ", ".join(names)
    if len(signature) > MAX_SIGNATURE:
        signature = signature[:MAX_SIGNATURE] + "..."
    return f"({signature})"


def function_line(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    doc = first_doc_line(node)
    suffix = f" — {doc}" if doc else ""
    return f"  - `{prefix} {node.name}{format_args(node)}` L{node.lineno}{suffix}"


def render_file(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(ROOT).as_posix()
    module_doc = first_doc_line(tree)
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(function_line(node).removeprefix("  "))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            head = f"`class {node.name}`" + (f"({bases})" if bases else "")
            doc = first_doc_line(node)
            suffix = f" — {doc}" if doc else ""
            symbols.append(f"- {head} L{node.lineno}{suffix}")
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(function_line(child))
    if not symbols and not module_doc:
        return []
    lines = [f"### `{rel}`"]
    if module_doc:
        lines.append(f"> {module_doc}")
    lines.append("")
    lines.extend(symbols)
    lines.append("")
    return lines


def main() -> int:
    if not APP_DIR.is_dir():
        print(f"missing directory: {APP_DIR}", file=sys.stderr)
        return 1
    files = sorted(p for p in APP_DIR.rglob("*.py") if "__pycache__" not in p.parts)
    body: list[str] = []
    for path in files:
        body.extend(render_file(path))
    header = [
        "# 后端符号索引（自动生成）",
        "",
        "由 `make map` 生成，请勿手工编辑。修改 `backend/app` 后重新生成。",
        "",
        f"覆盖 `backend/app` 下 {len(files)} 个 Python 文件。`L<数字>` 为定义起始行号，可据此定向读取行区间。",
        "",
        "## 目录",
        "",
    ]
    groups: dict[str, list[str]] = {}
    for path in files:
        group = path.relative_to(APP_DIR).parts[0] if len(path.relative_to(APP_DIR).parts) > 1 else "(root)"
        groups.setdefault(group, []).append(path.stem)
    for group in sorted(groups):
        stems = sorted(groups[group])
        header.append(f"- {group}: " + "、".join(f"`{s}`" for s in stems))
    header.append("")
    header.append("## 符号")
    header.append("")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(header + body).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())