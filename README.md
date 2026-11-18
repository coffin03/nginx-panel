# nginx-panel

本地运行的 nginx 可视化管理面板：直接接管你的 nginx 目录，在线编辑配置、一键启停重载、自动备份与回滚。数据全部保存在本地 SQLite，不需要联网，也不需要额外的云端服务。

> A local-first web UI for nginx: edit configs visually, start/stop/reload nginx, and keep a full local history with one-click rollback. No cloud, no telemetry.

## 功能

- **配置可视化编辑**：自动展开 `include`，左侧文件树列出全部可编辑配置；内置 nginx 语法高亮的代码编辑器。
- **结构化表单**：常用 `server` / `location` / `upstream` 指令可视化管理，与文本编辑双向同步（只改写发生变化的片段，保留原文件格式与注释）。
- **安全的生效流程**：保存 → 快照入库 → 写盘 → `nginx -t` 校验 → 失败自动还原 → reload → 健康检查 → 异常自动回滚。
- **进程管理**：启动、停止、重载、重启、配置测试；支持本地进程（Windows / 容器）与 systemd 两种模式。
- **历史与回滚**：每次应用自动生成快照，可查看逐行差异并一键恢复；外部手动修改也会自动留档。
- **日志查看**：直接读取 nginx 的 `logs` 目录，支持自动刷新与关键字过滤。
- **完全本地**：SQLite（WAL）保存数据，bcrypt 保存密码，首次启动向导创建管理员账号。

## 下载（稳定版）

Windows 用户不需要安装 Python / Node，直接下载打包好的便携版：

1. 打开 [Releases](../../releases/latest)，下载 `nginx-panel-<版本>-win64.zip`。
2. 解压后双击 `nginx-panel.exe` 运行，无需安装（压缩包内含 `LICENSE.txt`）。
3. 可选校验：把 `SHA256SUMS.txt` 与压缩包放在同一目录，执行
   `certutil -hashfile nginx-panel-0.1.0-win64.zip SHA256`，与文件中的值比对。

当前版本：**0.1.0**，变更记录见 [CHANGELOG.md](CHANGELOG.md)。Linux / Docker 部署见下方对应章节。

## 快速开始（Windows）

1. 从上方 Releases 下载并解压，或自行构建（见下文）。
2. 双击运行，会打开一个独立的桌面窗口（内嵌 WebView2，不经过系统浏览器）；关闭窗口即退出程序。
3. 首次打开设置管理员账号。
4. 点击「添加实例」，填写：
   - **nginx 目录**：例如 `C:\nginx`
   - **可执行文件**：例如 `C:\nginx\nginx.exe`
   - **主配置**：`conf\nginx.conf`
   - **运行模式**：`local`
5. 之后即可在实例页编辑配置、启动/重载 nginx。

数据文件位置：exe 同级的 `data\` 目录；如果该目录不可写，会自动落到 `%APPDATA%\nginx-panel`。

命令行参数通过环境变量控制：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `NGINX_PANEL_HOST` | 监听地址 | `127.0.0.1` |
| `NGINX_PANEL_PORT` | 监听端口 | `8090` |
| `NGINX_PANEL_DATA_DIR` | 数据目录 | exe 同级 `data` |
| `NGINX_PANEL_SECRET` | 会话签名密钥 | 自动生成并保存到 `data/secret.key` |
| `NGINX_PANEL_BROWSER` | 设为 `1` 时改用系统浏览器打开，不弹桌面窗口 | 未设置 |
| `NGINX_PANEL_NO_BROWSER` | 设为 `1` 时只启动后台服务，不打开窗口 | 未设置 |

桌面窗口依赖系统的 Microsoft Edge WebView2 运行时（Windows 10/11 一般已自带；若缺失，程序会提示并改用浏览器打开）。启动日志写在数据目录的 `logs\app.log`。

## 快速开始（Linux）

推荐使用一键脚本，把面板安装成 systemd 服务并通过 systemctl 管理本机 nginx：

```bash
sudo bash deploy/install.sh
```

脚本会：构建前端（需要 Node.js 18+，也可预先准备好 `web/dist`）→ 安装到 `/opt/nginx-panel` → 创建虚拟环境 → 注册并启动 `nginx-panel.service`。安装完成后访问 `http://服务器IP:8090`。

首次添加实例时填写：

- nginx 目录：`/etc/nginx`
- 可执行文件：`/usr/sbin/nginx`
- 主配置：`nginx.conf`
- 运行模式：`systemd`
- 服务名：`nginx`

服务管理：

```bash
systemctl status nginx-panel
systemctl restart nginx-panel
journalctl -u nginx-panel -f
```

## Docker

镜像内含 nginx，面板直接管理容器内的 nginx，适合开箱即用或作为配置预览环境：

```bash
docker compose up -d --build
```

- 面板：<http://127.0.0.1:8090>
- 容器内 nginx：<http://127.0.0.1:8080>
- 数据卷：`nginx-panel-data` → `/data`

添加实例时填写：目录 `/etc/nginx`、可执行文件 `/usr/sbin/nginx`、主配置 `nginx.conf`、运行模式 `local`。

如果要管理自己的配置，可将 `docker-compose.yml` 中 `./nginx-conf:/etc/nginx` 的挂载取消注释，并先把配置放到 `./nginx-conf`。

## 源码运行（开发）

```bash
# 后端
python -m pip install -r server/requirements.txt
python server/run.py

# 前端（另一个终端，开发服务器会代理 /api 到 8090）
cd web
npm install
npm run dev
```

构建 Windows 单文件 exe：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
# 产物：dist\nginx-panel.exe
```

运行测试：

```bash
python -m pytest
```

## 发布新版本

1. 更新 `server/nginx_panel/__init__.py` 的 `__version__`、`web/package.json` 的 `version`，并在 `CHANGELOG.md` 补一条记录。
2. 提交后打标签并推送：

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. GitHub Actions（[.github/workflows/release.yml](.github/workflows/release.yml)）会自动运行测试、构建前端与 exe、生成 `nginx-panel-<版本>-win64.zip` 与 `SHA256SUMS.txt`，并创建对应的 Release。

本地复现同一套产物：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\make-release.ps1
# 产物：dist\nginx-panel-<版本>-win64.zip 与 dist\SHA256SUMS.txt
```

## 工作方式

- **解析而不是正则替换**：自研 nginx 配置解析器为每条指令记录文件、偏移、行号；编辑时只替换最小文本区间，不重新序列化整个文件，因此缩进、对齐和注释都能保留。
- **include 展开**：从主配置递归展开 `include`（支持相对路径与通配符），所有被包含的文件都可以直接编辑。
- **冲突保护**：保存时携带文件内容哈希，磁盘内容被其他程序改过会返回 409，避免覆盖他人修改。
- **失败即回滚**：写盘前先备份，`nginx -t` 失败立即还原；reload 后进程消失或 error.log 出现新的 `[emerg]` 会再次回滚。
- **外部修改留档**：后台监听配置目录，检测到非本面板的修改会自动生成 `auto` 快照。

## 目录结构

```
server/            FastAPI 后端
  nginx_panel/      nginx 解析器、include 展开、文本补丁、进程适配器
    services/       实例、快照、生效流水线、表单映射、文件服务
    api/            REST 接口
    core/           SQLite、认证、路径与配置、文件监听
web/               Vue 3 + Element Plus + CodeMirror 6 前端
packaging/         PyInstaller 打包配置与发布脚本
deploy/            Linux 安装脚本与 systemd unit
.github/           CI 与 Release 工作流
tests/             解析器与接口测试
```

## 安全说明

- 面板默认只监听 `127.0.0.1`。如需对外开放，请放在带 HTTPS 的反向代理之后，并设置强密码。
- Linux 安装脚本使用 root 运行面板（需要写 nginx 配置并调用 systemctl）；请把服务器访问权限控制在可信范围内。
- 所有数据（账号、快照、密钥）都在本地，不会上传到任何地方。

## 参与贡献

欢迎提 Issue 与 PR：先在 [Issues](../../issues) 说明场景或复现步骤，PR 请保持改动聚焦，并确保 `python -m pytest` 与 `npm run build` 通过。版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## License

[MIT](LICENSE)