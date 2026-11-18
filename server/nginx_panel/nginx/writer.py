"""基于 span 的局部文本改写。

约定：
- 所有编辑都落在某个文件的原始文本上，编辑之间不得重叠。
- 删除指令时保留同一行尾部的注释。
- 新增指令按同级缩进插入，保持文件原有换行风格（LF/CRLF）。
"""

import re
from dataclasses import dataclass
from typing import Iterable, List

from .ast import Node, SourceFile, TextEdit

_NEED_QUOTE = re.compile(r"[\s\"'{};#]")


def quote_arg(value: str) -> str:
    if value == "" or _NEED_QUOTE.search(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def join_args(args: Iterable[str]) -> str:
    return " ".join(quote_arg(a) for a in args)


def line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def line_end(text: str, pos: int) -> int:
    idx = text.find("\n", pos)
    return len(text) if idx < 0 else idx + 1


def indent_at(text: str, pos: int) -> str:
    ls = line_start(text, pos)
    m = re.match(r"[ \t]*", text[ls:pos])
    return m.group(0) if m else ""


def child_indent(text: str, node: Node) -> str:
    """块内子指令的缩进：优先参考第一个子节点，否则父缩进 + 4 空格。"""
    if node.block:
        return indent_at(text, node.block[0].name_start) or (indent_at(text, node.name_start) + "    ")
    return indent_at(text, node.name_start) + "    "


def set_args(src: SourceFile, node: Node, args: List[str]) -> TextEdit:
    body = join_args(args)
    has_args = node.args_start > node.name_end
    if has_args:
        if body:
            # 只替换参数区间，保留指令名与第一个参数之间的对齐空白
            return TextEdit(src.path, node.args_start, node.args_end, body)
        return TextEdit(src.path, node.name_end, node.args_end, "")
    if body:
        return TextEdit(src.path, node.name_end, node.name_end, " " + body)
    return TextEdit(src.path, node.name_end, node.name_end, "")


def rename(src: SourceFile, node: Node, name: str) -> TextEdit:
    return TextEdit(src.path, node.name_start, node.name_end, name)


def delete_node(src: SourceFile, node: Node) -> TextEdit:
    text = src.text
    ls = line_start(text, node.name_start)
    le = line_end(text, node.end)
    line_after = text[node.end:le]
    comment_idx = line_after.find("#")
    if comment_idx >= 0:
        comment = line_after[comment_idx:].rstrip("\r\n")
        replacement = indent_at(text, node.name_start) + comment + src.eol
        return TextEdit(src.path, ls, le, replacement)
    # 删除整行；若删除的是最后一行且没有换行符，保留前一行换行
    start = ls
    end = le
    if end == len(text) and start > 0:
        start = start - 1 if text[start - 1] == "\n" else start
        if start > 0 and text[start - 1] == "\r":
            start -= 1
    return TextEdit(src.path, start, end, "")


def insert_after(src: SourceFile, node: Node, args: List[str], name: str | None = None) -> TextEdit:
    """在 node 所在行的下一行插入一条同级指令。"""
    text = src.text
    eol = src.eol
    indent = indent_at(text, node.name_start)
    stmt = f"{indent}{name or node.name} {join_args(args)};{eol}"
    pos = line_end(text, node.end)
    if pos == len(text) and not text.endswith("\n"):
        stmt = eol + stmt
    return TextEdit(src.path, pos, pos, stmt)


def append_child(src: SourceFile, block_node: Node, args: List[str], name: str) -> TextEdit:
    """在块结束的 '}' 之前插入子指令。"""
    text = src.text
    eol = src.eol
    indent = child_indent(text, block_node)
    stmt = f"{indent}{name} {join_args(args)};{eol}"
    # term_start 指向 '{'，end 指向 '}' 之后；在 '}' 所在行的起始处插入
    close_pos = text.rfind("}", 0, block_node.end)
    if close_pos < 0:
        close_pos = block_node.end
    close_line_start = line_start(text, close_pos)
    if text[close_line_start:close_pos].strip() == "":
        insert_at = close_line_start
        return TextEdit(src.path, insert_at, insert_at, stmt)
    return TextEdit(src.path, close_pos, close_pos, eol + stmt)


def insert_block_child_raw(src: SourceFile, block_node: Node, raw_lines: str) -> TextEdit:
    text = src.text
    close_pos = text.rfind("}", 0, block_node.end)
    if close_pos < 0:
        close_pos = block_node.end
    close_line_start = line_start(text, close_pos)
    if text[close_line_start:close_pos].strip() == "":
        return TextEdit(src.path, close_line_start, close_line_start, raw_lines)
    return TextEdit(src.path, close_pos, close_pos, src.eol + raw_lines)


def apply_edits(text: str, edits: List[TextEdit]) -> str:
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.start < prev.end:
            raise ValueError("编辑区间重叠，已取消本次修改")
    out = text
    for edit in reversed(ordered):
        out = out[: edit.start] + edit.replacement + out[edit.end :]
    return out


def apply_file_edits(src: SourceFile, edits: List[TextEdit]) -> str:
    return apply_edits(src.text, [e for e in edits if e.file == src.path])