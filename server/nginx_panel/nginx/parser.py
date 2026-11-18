"""nginx 配置词法/语法分析。

只做语法结构识别，不做语义校验。解析失败时尽量返回已完成部分并给出错误信息。
"""

from typing import List, Optional, Tuple

from .ast import Node, SourceFile, TokType, Token


class ParseError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.message = message
        self.line = line


_SPECIAL = "{};"


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(text)
    line = 1
    while i < n:
        c = text[i]
        if c in " \t\r":
            i += 1
            continue
        if c == "\n":
            line += 1
            i += 1
            continue
        if c == "#":
            j = text.find("\n", i)
            if j < 0:
                j = n
            tokens.append(Token(TokType.COMMENT, text[i:j], text[i:j], i, j, line))
            i = j
            continue
        if c in _SPECIAL:
            ttype = {"{": TokType.LBRACE, "}": TokType.RBRACE, ";": TokType.SEMI}[c]
            tokens.append(Token(ttype, c, c, i, i + 1, line))
            i += 1
            continue
        if c in "\"'":
            quote = c
            j = i + 1
            while j < n:
                ch = text[j]
                if ch == "\\" and j + 1 < n:
                    j += 2
                    continue
                if ch == quote:
                    j += 1
                    break
                if ch == "\n":
                    line += 1
                j += 1
            raw = text[i:j]
            value = raw[1:-1] if len(raw) >= 2 and raw.endswith(quote) else raw[1:]
            tokens.append(Token(TokType.QUOTED, raw, value, i, j, line))
            i = j
            continue
        # 普通词
        j = i
        while j < n and text[j] not in " \t\r\n{};#":
            j += 1
        if j == i:
            j = i + 1
        tokens.append(Token(TokType.WORD, text[i:j], text[i:j], i, j, line))
        i = j
    return tokens


class _Parser:
    def __init__(self, text: str, filename: str, tokens: List[Token]):
        self.text = text
        self.filename = filename
        self.tokens = tokens
        self.i = 0
        self.errors: List[str] = []

    def _make_node(self, stmt: List[Token], block: Optional[List[Node]], term: Token, end: int) -> Node:
        name_tok = stmt[0]
        if len(stmt) > 1:
            args_start = stmt[1].start
            args_end = stmt[-1].end
        else:
            args_start = args_end = name_tok.end
        return Node(
            name=name_tok.value,
            file=self.filename,
            line=name_tok.line,
            name_start=name_tok.start,
            name_end=name_tok.end,
            args_start=args_start,
            args_end=args_end,
            term_start=term.start,
            end=end,
            args=[t.value for t in stmt[1:]],
            block=block,
        )

    def parse_nodes(self, top_level: bool = True) -> Tuple[List[Node], Optional[Token]]:
        nodes: List[Node] = []
        stmt: List[Token] = []
        while self.i < len(self.tokens):
            tok = self.tokens[self.i]
            t = tok.type
            if t == TokType.COMMENT:
                self.i += 1
                continue
            if t == TokType.RBRACE:
                if top_level:
                    self.errors.append(f"第 {tok.line} 行: 多余的 '}}'")
                    self.i += 1
                    continue
                close = tok
                self.i += 1
                return nodes, close
            if t == TokType.LBRACE:
                if not stmt:
                    self.errors.append(f"第 {tok.line} 行: '{{' 前缺少指令名")
                    self.i += 1
                    continue
                self.i += 1
                children, close = self.parse_nodes(top_level=False)
                end = close.end if close is not None else tok.end
                nodes.append(self._make_node(stmt, children, tok, end))
                stmt = []
                continue
            if t == TokType.SEMI:
                if stmt:
                    nodes.append(self._make_node(stmt, None, tok, tok.end))
                stmt = []
                self.i += 1
                continue
            stmt.append(tok)
            self.i += 1
        if stmt:
            node = self._make_node(stmt, None, stmt[-1], stmt[-1].end)
            node.incomplete = True
            nodes.append(node)
        if not top_level:
            self.errors.append(f"第 {stmt[0].line if stmt else 1} 行: 块缺少 '}}'")
        return nodes, None


def parse_text(text: str, filename: str = "") -> tuple[List[Node], List[str]]:
    tokens = tokenize(text)
    parser = _Parser(text, filename, tokens)
    nodes, _ = parser.parse_nodes()
    return nodes, parser.errors


def parse_source(text: str, filename: str) -> SourceFile:
    src = SourceFile(path=filename, text=text)
    try:
        src.nodes, errors = parse_text(text, filename)
        if errors:
            src.error = "; ".join(errors)
    except ParseError as exc:  # 兜底：不应发生
        src.error = f"第 {exc.line} 行: {exc.message}"
        src.nodes = []
    return src