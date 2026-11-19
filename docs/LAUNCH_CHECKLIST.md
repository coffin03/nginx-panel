# 开源发布清单

目标：让项目在 GitHub 上可被搜索、能在 10 秒内被看懂，并具备可信的分发与更新路径。

## 一、发布前必须完成（阻断项）

- [x] 添加远程仓库并推送：https://github.com/coffin03/nginx-panel
- [x] 仓库 Description（英文，尽量含关键词）：
      `Local-first web UI for nginx: edit the real config tree, validate with nginx -t, reload and auto-rollback.`
- [x] GitHub Topics：`nginx`、`nginx-ui`、`nginx-config`、`self-hosted`、`webui`、`devops`、`docker`、`fastapi`、`vue3`
- [x] 上传 Social Preview（`docs/screenshots/social-preview.png`，1280×640）
- [x] 添加真实截图到 `docs/screenshots/`，并已在中英文 README 中引用：
      - `editor.png` / `editor.zh-CN.png` 配置编辑（含 include 展开、语法高亮）
      - `form.png` / `form.zh-CN.png` 结构化表单
      - `checks.png` / `checks.zh-CN.png` 配置体检
- [ ] 待补充截图（需要先造演示数据）：
      - `diff.png` 快照差异与回滚
      - `certs.png` 证书与续期
      - `sites.png` 站点管理
- [ ] 录制 30 秒演示 GIF（首屏最关键素材）：
      1. 打开实例 → 编辑配置（改错一个指令）
      2. 保存 → `nginx -t` 失败提示
      3. 展示自动回滚、文件恢复原状
      4. 改成正确配置 → 保存成功 → reload 生效
      建议 1280×720、10–12 fps、体积控制在 8 MB 内；同时上传到 README 顶部和 Release 说明。
- [ ] README 首屏自检（手机宽度下也能看懂）：
      - 名称 + 一句话定位在首屏
      - 至少一张图或 GIF 在首屏
      - 明确 Windows exe 下载入口
      - Star 引导不超过一句
- [x] 仓库公开后，把 CI 徽章补到 README 徽章行
- [x] 检查 `README.md` / `README.zh-CN.md` 中所有相对链接可用（Releases、LICENSE、CHANGELOG、deploy、docker-compose、截图）

## 二、首个 Release

- [x] 确认版本号一致：`server/nginx_panel/__init__.py`、`web/package.json`、`CHANGELOG.md` 均为 0.1.0
- [x] 打 tag 并推送：`v0.1.0`
- [x] 确认 Actions 产物：`nginx-panel-0.1.0-win64.zip`、`SHA256SUMS.txt`
- [ ] Release 说明使用英文为主，附：
      - 一句话定位
      - 3–4 条核心差异
      - 下载与校验方式
      - GIF 或截图
      - 已知限制（WebView2、默认监听 127.0.0.1 等）

## 三、分发渠道（按优先级）

- [x] 发布 Docker 镜像到 GHCR（`.github/workflows/docker.yml`，`ghcr.io/coffin03/nginx-panel:0.1.0`），README 已补 `docker run` 示例
- [ ] 提交 [HelloGitHub](https://hellogithub.com/)（中文项目最有效的早期曝光渠道之一）
- [ ] 向 awesome 列表提 PR：
      - `awesome-selfhosted`（需满足其收录标准，先读 CONTRIBUTING）
      - `awesome-nginx`
      - `awesome-homelab`
      - `awesome-devops`
- [ ] Show HN：标题直接说明差异，例如
      `Show HN: Local-first nginx panel with automatic rollback on failed reload`
- [ ] Reddit：`r/nginx`、`r/selfhosted`、`r/homelab`、`r/devops`（每个社区单独写切入角度，不要复制同一段）
- [ ] 中文社区：V2EX、Linux.do、掘金、少数派、阮一峰周刊投稿、HostLoc
- [ ] X / 即刻：GIF + 一句话 + 仓库链接；避免连续刷屏
- [ ] Product Hunt（可选，适合桌面工具定位）

## 四、内容长尾

- [ ] 《如何安全地在线修改 nginx 配置：校验、快照与自动回滚》
- [ ] 《为什么我们选择解析 nginx，而不是正则替换》
- [ ] 《Windows 上不装环境，直接管理 nginx 的桌面面板》
- [ ] 每篇文章结尾给出仓库链接、exe 下载与 Docker 方式；中文发掘金/知乎，英文发 Dev.to/Hashnode

## 五、社区与留存

- [ ] 创建标签：`good first issue`、`help wanted`、`roadmap`、`bug`、`enhancement`
- [ ] 准备 3–5 个 `good first issue`（文档、翻译、检查规则、UI 细节）
- [ ] Issue 模板补充英文（现有模板若是中文，海外用户会直接离开）
- [ ] 在 README 或 Discussions 中说明支持范围与响应方式
- [ ] 每个版本发布后回到旧 Issue 回复进展，形成可见的维护节奏
- [ ] 收集真实使用场景（匿名也可），补充到 README 的 “Who uses it” 或 Discussions

## 六、观察指标

- GitHub Traffic：Views / Unique visitors / Referrers，找出转化最高的渠道
- Star 来源：发布后 48 小时内的增长主要来自哪个渠道，下一轮加大投入
- 转化率：README 访问 → Release 下载 → Issue/Star
- 质量指标：Issue 中有多少来自真实使用场景（比星数更能说明问题）