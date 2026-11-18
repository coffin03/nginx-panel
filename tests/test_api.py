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