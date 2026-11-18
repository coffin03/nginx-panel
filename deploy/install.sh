#!/usr/bin/env bash
# nginx-panel Linux 一键安装：把面板安装为 systemd 服务，通过 systemctl 管理本机 nginx
# 用法（在仓库根目录）：sudo bash deploy/install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "请使用 sudo 运行：sudo bash deploy/install.sh"
    exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX=/opt/nginx-panel
DATA=/var/lib/nginx-panel

command -v python3 >/dev/null 2>&1 || { echo "缺少 python3，请先安装：apt install python3 python3-venv"; exit 1; }
python3 -c 'import venv' >/dev/null 2>&1 || { echo "缺少 python3-venv，请先安装：apt install python3-venv"; exit 1; }

if ! command -v nginx >/dev/null 2>&1; then
    echo "警告：未找到 nginx 命令。面板可以安装，但需要先安装 nginx 才能启动/重载服务。"
fi

if [[ ! -f "$ROOT/web/dist/index.html" ]]; then
    if command -v npm >/dev/null 2>&1; then
        echo "==> 构建前端"
        (cd "$ROOT/web" && npm install && npm run build)
    else
        echo "未找到前端产物 web/dist，且系统没有 npm。"
        echo "请先安装 Node.js 18+，或从 release 包中解压已构建的 dist 后再运行本脚本。"
        exit 1
    fi
fi

echo "==> 安装文件到 $PREFIX"
mkdir -p "$PREFIX"
rm -rf "$PREFIX/server" "$PREFIX/web"
cp -a "$ROOT/server" "$PREFIX/server"
mkdir -p "$PREFIX/web"
cp -a "$ROOT/web/dist" "$PREFIX/web/dist"

echo "==> 创建 Python 虚拟环境"
python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --quiet --upgrade pip
"$PREFIX/venv/bin/pip" install --quiet -r "$PREFIX/server/requirements.txt"

mkdir -p "$DATA"

echo "==> 注册 systemd 服务"
sed -e "s#__PREFIX__#$PREFIX#g" -e "s#__DATA__#$DATA#g" \
    "$ROOT/deploy/nginx-panel.service" > /etc/systemd/system/nginx-panel.service
systemctl daemon-reload
systemctl enable --now nginx-panel

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "安装完成：http://${IP:-127.0.0.1}:8090"
echo "数据目录：$DATA"
echo "服务管理：systemctl status nginx-panel | systemctl restart nginx-panel | systemctl stop nginx-panel"
echo ""
echo "首次打开请设置管理员账号，然后添加实例："
echo "  nginx 目录   /etc/nginx"
echo "  可执行文件   /usr/sbin/nginx"
echo "  主配置       nginx.conf"
echo "  运行模式     systemd"
echo "  服务名       nginx"