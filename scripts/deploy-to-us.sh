#!/usr/bin/env bash
# 北大附中海口学校 3D 校园模型生产环境一键部署脚本
# 规范参考: /Users/perrylei/repos/Shiye/DEPLOYMENT.md 与 scripts/deploy-to-us.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REMOTE_HOST="${REMOTE_HOST:-wh-us}"
REMOTE_DIR="${REMOTE_DIR:-/var/www/bdfz.leiping.dev}"
DOMAIN="${DOMAIN:-bdfz.leiping.dev}"

log() {
  printf '
[%s] %s
' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

cd "$REPO_ROOT"

log "1. 执行本地 Web 生产打包 (Vite Build)..."
npm --prefix web run build

log "2. 同步静态编译产物到远程服务器 ($REMOTE_HOST:$REMOTE_DIR)..."
rsync -avz --delete   --exclude '.DS_Store'   --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r   web/dist/ "$REMOTE_HOST:$REMOTE_DIR/"

log "3. 线上站点健康探测与资源可达性检查..."
sleep 1
curl -fsS -I "https://$DOMAIN/" >/dev/null
curl -fsS -I "https://$DOMAIN/bdfz.glb" >/dev/null
curl -fsS -I "https://$DOMAIN/scene.json" >/dev/null

log "部署成功！已上线: https://$DOMAIN"
