"""nginx 配置的轻量 CST（保留原始文本位置）。

设计原则：
- 只记录位置与原始文本，任何编辑都基于 span 做局部替换，绝不整体重新序列化。
- 一个 Node 一定来自某个具体文件的某段原文，file 字段标记来源文件。
"""

from dataclasses import dataclass, field
from typing import List, Optional


class TokType:
    WORD = "word"
    QUOTED = "quoted"
    LBRACE = "lbrace"
    RBRACE = "rbrace"
    SEMI = "semi"
    COMMENT = "comment"


@dataclass
class Token:
    type: str
    raw: str  # 原始文本（引号保留）
    value: str  # 去掉引号后的值
    start: int
    end: int
    line: int


@dataclass
class Node:
    name: str
    file: str
    line: int
    # 名字 token 的位置
    name_start: int
    name_end: int
    # 参数区间（不含前导空白）；无参数时 args_start == args_end == name_end
    args_start: int
    args_end: int
    # 语句终止符（';' 或 '{'）的位置
    term_start: int
    # 整条语句结束位置（';' 之后 或 '}' 之后）
    end: int
    args: List[str] = field(default_factory=list)
    block: Optional[List["Node"]] = None
    # include 指令展开出的文件
    included: List["SourceFile"] = field(default_factory=list)
    include_error: Optional[str] = None
    incomplete: bool = False

    @property
    def is_block(self) -> bool:
        return self.block is not None

    @property
    def is_include(self) -> bool:
        return self.name == "include"

    def walk(self):
        yield self
        for child in self.block or []:
            yield from child.walk()

    def to_dict(self, with_children: bool = True) -> dict:
        data = {
            "name": self.name,
            "args": self.args,
            "file": self.file,
            "line": self.line,
            "name_start": self.name_start,
            "args_start": self.args_start,
            "args_end": self.args_end,
            "term_start": self.term_start,
            "end": self.end,
            "is_block": self.is_block,
            "is_include": self.is_include,
        }
        if self.is_include and self.included:
            data["included"] = [f.to_dict(with_children=with_children) for f in self.included]
        if with_children and self.block is not None:
            data["block"] = [n.to_dict(with_children=with_children) for n in self.block]
        return data


@dataclass
class SourceFile:
    path: str  # 绝对路径
    text: str
    nodes: List[Node] = field(default_factory=list)
    error: Optional[str] = None
    bom: bool = False

    @property
    def eol(self) -> str:
        return "\r\n" if "\r\n" in self.text else "\n"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "error": self.error,
            "nodes": [n.to_dict() for n in self.nodes],
        }


@dataclass
class TextEdit:
    """对单个文件的一次文本替换。"""

    file: str
    start: int
    end: int
    replacement: str