import os

import pytest

from nginx_panel.nginx import writer
from nginx_panel.nginx.includes import load_tree
from nginx_panel.nginx.parser import parse_source, tokenize

SAMPLE = """\
# 顶部注释
worker_processes auto;
events {
    worker_connections 1024;
}

http {
    include       mime.types;   # 类型表
    default_type  application/octet-stream;
    server {
        listen       80;
        server_name  example.com;
        location / {
            root   html;
            index  index.html index.htm;
        }
        # 尾部注释
        location /api/ {
            proxy_pass http://127.0.0.1:8080;
        }
    }
}
"""


def test_tokenize_quotes_and_comments():
    tokens = tokenize('a "b c" \'d e\'; # x\n')
    values = [(t.type, t.value) for t in tokens]
    assert ("word", "a") in values
    assert ("quoted", "b c") in values
    assert ("quoted", "d e") in values
    assert any(t.type == "comment" for t in tokens)


def test_parse_nested_blocks():
    src = parse_source(SAMPLE, "nginx.conf")
    assert src.error is None
    names = [n.name for n in src.nodes]
    assert names == ["worker_processes", "events", "http"]
    http = src.nodes[2]
    assert http.block and http.block[0].name == "include"
    server = [n for n in http.block if n.name == "server"][0]
    locs = [n for n in server.block if n.name == "location"]
    assert locs[0].args == ["/"]
    assert locs[0].block[0].args == ["html"]


def _server(src):
    http = [n for n in src.nodes if n.name == "http"][0]
    return [n for n in http.block if n.name == "server"][0]


def test_set_args_keeps_formatting():
    src = parse_source(SAMPLE, "nginx.conf")
    server = _server(src)
    listen = server.block[0]
    edit = writer.set_args(src, listen, ["8080", "default_server"])
    out = writer.apply_file_edits(src, [edit])
    assert "listen       8080 default_server;" in out
    assert "server_name  example.com;" in out


def test_delete_node_keeps_trailing_comment():
    src = parse_source(SAMPLE, "nginx.conf")
    include = src.nodes[2].block[0]
    out = writer.apply_file_edits(src, [writer.delete_node(src, include)])
    assert "include" not in out
    assert "# 类型表" in out
    assert out.count("\n") == SAMPLE.count("\n")


def test_insert_child_and_reparse():
    src = parse_source(SAMPLE, "nginx.conf")
    server = _server(src)
    edit = writer.append_child(src, server, ["*:443", "ssl"], "listen")
    out = writer.apply_file_edits(src, [edit])
    reparsed = parse_source(out, "nginx.conf")
    server2 = _server(reparsed)
    listens = [n.args for n in server2.block if n.name == "listen"]
    assert ["*:443", "ssl"] in listens


def test_crlf_preserved(tmp_path):
    raw = "http {\r\n    server {\r\n        listen 80;\r\n    }\r\n}\r\n"
    path = tmp_path / "nginx.conf"
    path.write_bytes(raw.encode())
    tree = load_tree(str(path), str(tmp_path))
    assert tree.root is not None
    assert tree.root.eol == "\r\n"
    server = tree.root.nodes[0].block[0]
    edit = writer.append_child(tree.root, server, ["81"], "listen")
    out = writer.apply_file_edits(tree.root, [edit])
    assert "listen 81;\r\n" in out
    assert "\n" not in out.replace("\r\n", "")


def test_include_expansion(tmp_path):
    (tmp_path / "conf.d").mkdir()
    (tmp_path / "mime.types").write_text("types { text/html html; }\n", encoding="utf-8")
    (tmp_path / "conf.d" / "a.conf").write_text(
        "server { listen 80; server_name a.test; }\n", encoding="utf-8"
    )
    (tmp_path / "conf.d" / "b.conf").write_text(
        "server { listen 81; server_name b.test; }\n", encoding="utf-8"
    )
    main = tmp_path / "nginx.conf"
    main.write_text(
        "http {\n  include mime.types;\n  include conf.d/*.conf;\n}\n", encoding="utf-8"
    )
    tree = load_tree(str(main), str(tmp_path))
    assert tree.errors == []
    http = tree.root.nodes[0]
    assert len(http.block[0].included) == 1
    assert len(http.block[1].included) == 2
    expanded = list(tree.flatten_nodes())
    assert sum(1 for n in expanded if n.name == "server") == 2


def test_unclosed_block_reports_error():
    src = parse_source("http { server { listen 80; }\n", "bad.conf")
    assert src.error is not None