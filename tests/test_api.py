import base64
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from nginx_panel.main import app
from nginx_panel.nginx.process.base import OpResult, Status

NGINX_CONF = """\
worker_processes 1;
events { worker_connections 256; }
http {
    server {
        listen 8088;
        server_name demo.local;
        location / {
            root html;
            index index.html;
        }
    }
    upstream app_pool {
        server 127.0.0.1:8001;
        server 127.0.0.1:8002;
        keepalive 16;
    }
}
"""


class FakeAdapter:
    def __init__(self, ok=True):
        self.ok = ok
        self.reloaded = 0

    def status(self):
        return Status(False, None, "未运行")

    def test(self):
        return OpResult(self.ok, "nginx: configuration file test is successful")

    def reload(self):
        self.reloaded += 1
        return OpResult(self.ok, "reload")

    def start(self):
        return OpResult(True, "started", running=True)

    def stop(self):
        return OpResult(True, "stopped", running=False)

    def restart(self):
        return OpResult(True, "restarted", running=True)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    status = client.get("/api/auth/status").json()
    if not status["initialized"]:
        r = client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
        assert r.status_code == 200, r.text
    else:
        r = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
        assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def nginx_dir(tmp_path):
    prefix = tmp_path / "nginx"
    (prefix / "conf").mkdir(parents=True)
    (prefix / "logs").mkdir()
    (prefix / "html").mkdir()
    (prefix / "conf" / "nginx.conf").write_text(NGINX_CONF, encoding="utf-8")
    (prefix / "conf" / "mime.types").write_text("types { text/html html; }\n", encoding="utf-8")
    return prefix


def make_instance(client, prefix):
    r = client.post(
        "/api/instances",
        json={
            "name": "本地测试",
            "binary": "nginx",
            "prefix": str(prefix),
            "conf_path": "conf/nginx.conf",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_setup_and_login_required(client):
    assert client.get("/api/instances").status_code == 401
    client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    assert client.get("/api/instances").status_code == 200


def test_locale_switch_for_api_messages(client):
    client.post("/api/auth/setup", json={"username": "admin", "password": "secret123"})
    bad = {"username": "admin", "password": "wrong"}

    zh = client.post("/api/auth/login", json=bad)
    assert zh.json()["message"] == "用户名或密码错误"

    en = client.post("/api/auth/login", json=bad, headers={"X-Locale": "en"})
    assert en.json()["message"] == "Incorrect username or password"

    # 未带 X-Locale 时按 Accept-Language 推断
    en2 = client.post("/api/auth/login", json=bad, headers={"Accept-Language": "en-US,en;q=0.9"})
    assert en2.json()["message"] == "Incorrect username or password"


def test_system_pick_path(admin, monkeypatch):
    from nginx_panel.api import system

    monkeypatch.setattr(
        system,
        "_open_dialog",
        lambda mode, title, initial: r"D:\nginx\conf\nginx.conf" if mode == "file" else "",
    )
    r = admin.post("/api/system/pick", json={"mode": "file", "title": "选择文件"})
    assert r.status_code == 200, r.text
    assert r.json()["path"].endswith("nginx.conf")

    # 取消选择时返回空路径，前端保持原值
    r = admin.post("/api/system/pick", json={"mode": "folder"})
    assert r.status_code == 200, r.text
    assert r.json()["path"] == ""

    r = admin.post("/api/system/pick", json={"mode": "bad"})
    assert r.status_code == 400


def test_instance_and_file_flow(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    tree = admin.get(f"/api/instances/{iid}/tree").json()
    rels = [f["rel"] for f in tree["files"]]
    assert "conf/nginx.conf" in rels

    info = admin.get(f"/api/instances/{iid}/file", params={"path": "conf/nginx.conf"}).json()
    assert "listen 8088;" in info["content"]

    new_content = info["content"].replace("listen 8088;", "listen 9099;")
    r = admin.put(
        f"/api/instances/{iid}/file",
        json={"path": info["path"], "content": new_content, "base_hash": info["hash"], "message": "改端口"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["snapshot_id"] > 0
    assert "listen 9099;" in (nginx_dir / "conf" / "nginx.conf").read_text(encoding="utf-8")

    # 旧 hash 再次提交应冲突
    r2 = admin.put(
        f"/api/instances/{iid}/file",
        json={"path": info["path"], "content": new_content, "base_hash": info["hash"]},
    )
    assert r2.status_code == 409

    snaps = admin.get(f"/api/instances/{iid}/snapshots").json()
    assert len(snaps) >= 1

    form = admin.get(f"/api/instances/{iid}/form").json()
    assert form["servers"][0]["fields"]["listen"][0]["args"] == ["9099"]
    # 回归：upstream 不能被生成器耗尽导致为空
    assert len(form["upstreams"]) == 1
    assert form["upstreams"][0]["name"] == "app_pool"
    assert len(form["upstreams"][0]["fields"]["server"]) == 2


def test_failed_test_rolls_back(admin, nginx_dir, monkeypatch):
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(False))
    info = admin.get(f"/api/instances/{iid}/file", params={"path": "conf/nginx.conf"}).json()
    bad = info["content"].replace("listen 8088;", "listen 7777;")
    r = admin.put(
        f"/api/instances/{iid}/file",
        json={"path": info["path"], "content": bad, "base_hash": info["hash"]},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "test"
    assert "listen 8088;" in (nginx_dir / "conf" / "nginx.conf").read_text(encoding="utf-8")


def test_form_edit_applies_minimal_patch(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]
    form = admin.get(f"/api/instances/{iid}/form").json()
    listen = form["servers"][0]["fields"]["listen"][0]
    r = admin.post(
        f"/api/instances/{iid}/form",
        json={"edits": [{"file": listen["file"], "start": listen["start"], "args": ["8088", "reuseport"]}]},
    )
    assert r.status_code == 200, r.text
    text = (nginx_dir / "conf" / "nginx.conf").read_text(encoding="utf-8")
    assert "listen 8088 reuseport;" in text
    assert "server_name demo.local;" in text


TEST_CERT_DER_B64 = (
    "MIG8MIGmoAUwAwIBAgIBATANBgkqhkiG9w0BAQsFADASMRAwDgYDVQQDDAdUZXN0IENBMB4XDTI1"
    "MDEwMTAwMDAwMFoXDTM1MDEwMTAwMDAwMFowFjEUMBIGA1UEAwwLZXhhbXBsZS5jb20wEjANBgkq"
    "hkiG9w0BAQEFAAMBAKMrMCkwJwYDVR0RBCAwHoILZXhhbXBsZS5jb22CD3d3dy5leGFtcGxlLmNv"
    "bTANBgkqhkiG9w0BAQsFAAMCAAE="
)


def write_cert_pem(path):
    body = "\n".join(TEST_CERT_DER_B64[i : i + 76] for i in range(0, len(TEST_CERT_DER_B64), 76))
    path.write_text(f"-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----\n", encoding="utf-8")


def test_certificates_endpoint(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    write_cert_pem(nginx_dir / "conf" / "demo.crt")
    conf = nginx_dir / "conf" / "nginx.conf"
    conf.write_text(
        conf.read_text(encoding="utf-8").replace(
            "server_name demo.local;", "server_name demo.local;\n        ssl_certificate conf/demo.crt;"
        ),
        encoding="utf-8",
    )

    r = admin.get(f"/api/instances/{iid}/certificates")
    assert r.status_code == 200, r.text
    certs = r.json()["certificates"]
    assert len(certs) == 1
    item = certs[0]
    assert item["status"] == "ok"
    assert item["domains"] == ["example.com", "www.example.com"]
    assert item["issuer"] == "Test CA"
    assert item["days_left"] > 0


def test_renew_certificate(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    write_cert_pem(nginx_dir / "conf" / "demo.crt")
    conf = nginx_dir / "conf" / "nginx.conf"
    conf.write_text(
        conf.read_text(encoding="utf-8").replace(
            "server_name demo.local;", "server_name demo.local;\n        ssl_certificate conf/demo.crt;"
        ),
        encoding="utf-8",
    )

    opts = admin.get(f"/api/instances/{iid}/certificates/renew-options", params={"path": "conf/demo.crt"})
    assert opts.status_code == 200, opts.text
    assert any(opt["id"] == "custom" for opt in opts.json()["options"])

    empty = admin.post(f"/api/instances/{iid}/certificates/renew", json={"path": "conf/demo.crt", "command": "  "})
    assert empty.status_code == 400

    r = admin.post(
        f"/api/instances/{iid}/certificates/renew",
        json={"path": "conf/demo.crt", "command": "exit 0", "reload": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["changed"] is False
    assert data["before"]["not_after"] == data["after"]["not_after"]


def test_create_site_injects_include(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    payload = {
        "server_name": "demo2.local",
        "kind": "static",
        "root": str(nginx_dir / "html"),
        "listen": 8080,
    }
    preview = admin.post(f"/api/instances/{iid}/sites/preview", json=payload)
    assert preview.status_code == 200, preview.text
    assert "server_name demo2.local;" in preview.json()["content"]
    assert preview.json()["needs_include"] is True

    r = admin.post(f"/api/instances/{iid}/sites", json=payload)
    assert r.status_code == 200, r.text

    site = nginx_dir / "conf.d" / "demo2.local.conf"
    assert site.is_file()
    assert "include conf.d/*.conf;" in (nginx_dir / "conf" / "nginx.conf").read_text(encoding="utf-8")

    tree = admin.get(f"/api/instances/{iid}/tree").json()
    rels = [f["rel"] for f in tree["files"]]
    assert any(rel.endswith("demo2.local.conf") for rel in rels)

    # 重复创建应报错
    again = admin.post(f"/api/instances/{iid}/sites", json=payload)
    assert again.status_code == 400


def test_sites_list_toggle_delete(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    payload = {
        "server_name": "demo3.local",
        "kind": "static",
        "root": str(nginx_dir / "html"),
        "listen": 8080,
    }
    assert admin.post(f"/api/instances/{iid}/sites", json=payload).status_code == 200

    sites = admin.get(f"/api/instances/{iid}/sites").json()
    assert sites["include_configured"] is True
    assert len(sites["sites"]) == 1
    item = sites["sites"][0]
    assert item["enabled"] is True
    assert item["loaded"] is True
    assert item["server_names"] == ["demo3.local"]

    # 停用：重命名为 .conf.disabled
    r = admin.post(f"/api/instances/{iid}/sites/demo3.local.conf/disable")
    assert r.status_code == 200, r.text
    assert not (nginx_dir / "conf.d" / "demo3.local.conf").exists()
    assert (nginx_dir / "conf.d" / "demo3.local.conf.disabled").is_file()
    after = admin.get(f"/api/instances/{iid}/sites").json()["sites"][0]
    assert after["enabled"] is False
    assert after["loaded"] is False

    # 启用：还原文件名
    r = admin.post(f"/api/instances/{iid}/sites/demo3.local.conf.disabled/enable")
    assert r.status_code == 200, r.text
    assert (nginx_dir / "conf.d" / "demo3.local.conf").is_file()

    # 删除
    r = admin.delete(f"/api/instances/{iid}/sites/demo3.local.conf")
    assert r.status_code == 200, r.text
    assert not (nginx_dir / "conf.d" / "demo3.local.conf").exists()
    assert admin.get(f"/api/instances/{iid}/sites").json()["sites"] == []


def test_checks_endpoint(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    conf = nginx_dir / "conf" / "nginx.conf"
    conf.write_text(
        conf.read_text(encoding="utf-8").replace("root html;", "root html;\n        root missing-dir;"),
        encoding="utf-8",
    )

    r = admin.get(f"/api/instances/{iid}/checks")
    assert r.status_code == 200, r.text
    data = r.json()
    codes = {item["code"] for item in data["items"]}
    assert "root_missing" in codes
    assert "gzip_off" in codes
    assert data["summary"]["warning"] >= 1
    assert data["summary"]["info"] >= 1


def _zip_payload(files: dict, manifest: dict = None) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
        zf.writestr("manifest.json", json.dumps(manifest or {"version": 1, "files": []}))
    return base64.b64encode(buf.getvalue()).decode()


def test_backup_export_and_import(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    r = admin.get(f"/api/instances/{iid}/backup/export")
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "files/conf/nginx.conf" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert any(item["rel"] == "conf/nginx.conf" for item in manifest["files"])
        content = zf.read("files/conf/nginx.conf").decode("utf-8")

    data = _zip_payload(
        {"files/conf/nginx.conf": content.replace("listen 8088;", "listen 9100;")},
        {"version": 1, "instance": {"name": "备份"}, "files": []},
    )

    preview = admin.post(f"/api/instances/{iid}/backup/inspect", json={"data": data})
    assert preview.status_code == 200, preview.text
    item = next(f for f in preview.json()["files"] if f["rel"] == "conf/nginx.conf")
    assert item["status"] == "changed"
    assert preview.json()["summary"]["changed"] == 1

    r = admin.post(f"/api/instances/{iid}/backup/import", json={"data": data, "reload": False})
    assert r.status_code == 200, r.text
    assert "listen 9100;" in (nginx_dir / "conf" / "nginx.conf").read_text(encoding="utf-8")


def test_backup_rejects_invalid_archive(admin, nginx_dir, monkeypatch):
    monkeypatch.setattr("nginx_panel.services.apply.build_adapter", lambda *a, **k: FakeAdapter(True))
    inst = make_instance(admin, nginx_dir)
    iid = inst["id"]

    bad = base64.b64encode(b"not a zip").decode()
    r = admin.post(f"/api/instances/{iid}/backup/inspect", json={"data": bad})
    assert r.status_code == 400

    traversal = _zip_payload({"files/../evil.conf": "x"})
    r = admin.post(f"/api/instances/{iid}/backup/import", json={"data": traversal})
    assert r.status_code == 400
    assert not (nginx_dir.parent / "evil.conf").exists()

    # 缺少 manifest.json 也应拒绝
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("files/conf/nginx.conf", "x")
    missing = base64.b64encode(buf.getvalue()).decode()
    r = admin.post(f"/api/instances/{iid}/backup/inspect", json={"data": missing})
    assert r.status_code == 400