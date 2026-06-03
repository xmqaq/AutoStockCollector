#!/bin/bash
# 一键部署到 VPS
# 用法:
#   ./deploy.sh                 全量部署（前端+后端）
#   ./deploy.sh backend         只部署后端（跳过前端构建，快）
#   ./deploy.sh frontend        只部署前端
#   ./deploy.sh --verbose       全量部署，显示完整构建日志
#   ./deploy.sh backend -v      只部署后端，显示完整构建日志
#   ./deploy.sh --host 1.2.3.4  部署到指定服务器

set -euo pipefail

VPS="123.57.220.197"
DIR="/opt/stock"
LOG_FILE="/tmp/stock-deploy.log"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

VERBOSE=false
TARGET="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose) VERBOSE=true ;;
        --host) VPS="$2"; shift ;;
        backend|frontend|all) TARGET="$1" ;;
    esac
    shift
done

TOTAL_STEPS=4
CURRENT_STEP=0

SPINNER_PID=""

cleanup() {
    stop_spinner
    rm -f /tmp/stock.tar.gz
}
trap cleanup EXIT

start_spinner() {
    local msg="$1"
    if $VERBOSE; then return; fi
    (
        local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
        local i=0
        while true; do
            printf "\r  ${frames[$i]} ${DIM}%s${RESET}" "$msg"
            i=$(( (i + 1) % ${#frames[@]} ))
            sleep 0.1
        done
    ) &
    SPINNER_PID=$!
}

stop_spinner() {
    if [[ -n "$SPINNER_PID" ]] && kill -0 "$SPINNER_PID" 2>/dev/null; then
        kill "$SPINNER_PID" 2>/dev/null
        wait "$SPINNER_PID" 2>/dev/null || true
        printf "\r\033[K"
        SPINNER_PID=""
    fi
}

step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}[${CURRENT_STEP}/${TOTAL_STEPS}]${RESET} ${BOLD}$1${RESET}"
}

done_msg() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

fail_msg() {
    echo -e "  ${RED}✗ $1${RESET}"
}

run_cmd() {
    local desc="$1"
    shift
    if $VERBOSE; then
        "$@"
    else
        start_spinner "$desc"
        if "$@" > "$LOG_FILE" 2>&1; then
            stop_spinner
        else
            local exit_code=$?
            stop_spinner
            fail_msg "$desc 失败 (exit code: $exit_code)"
            echo -e "  ${YELLOW}╭─ 错误日志 ──────────────────────────────${RESET}"
            tail -20 "$LOG_FILE" | sed 's/^/  │ /'
            echo -e "  ${YELLOW}╰─ 完整日志: ${LOG_FILE}${RESET}"
            exit $exit_code
        fi
    fi
}

run_ssh() {
    local desc="$1"
    local cmd="$2"
    if $VERBOSE; then
        ssh -t root@${VPS} "$cmd"
    else
        start_spinner "$desc"
        if ssh root@${VPS} "$cmd" > "$LOG_FILE" 2>&1; then
            stop_spinner
        else
            local exit_code=$?
            stop_spinner
            fail_msg "$desc 失败 (exit code: $exit_code)"
            echo -e "  ${YELLOW}╭─ 错误日志 ──────────────────────────────${RESET}"
            tail -20 "$LOG_FILE" | sed 's/^/  │ /'
            echo -e "  ${YELLOW}╰─ 完整日志: ${LOG_FILE}${RESET}"
            exit $exit_code
        fi
    fi
}

# ─────────────────────────────────────────

echo -e "${BOLD}🚀 AutoStockCollector 部署${RESET} ${DIM}(${TARGET})${RESET}"
if $VERBOSE; then
    echo -e "${DIM}   模式: verbose${RESET}"
fi

# 预检: SSH 连通性
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 root@${VPS} "exit" 2>/dev/null; then
    echo ""
    echo -e "${YELLOW}⚠  无法免密连接到 ${VPS}${RESET}"
    echo -e "${DIM}   请先运行以下命令，输入一次服务器密码即可:${RESET}"
    echo ""
    echo -e "   ${BOLD}ssh-copy-id root@${VPS}${RESET}"
    echo ""
    echo -e "${DIM}   完成后重新运行 ./deploy.sh${RESET}"
    exit 1
fi

START=$(date +%s)

# [1] 打包
step "📦 打包项目"
run_cmd "正在打包..." \
    tar --no-mac-metadata --exclude='node_modules' --exclude='venv' --exclude='.git' \
        --exclude='__pycache__' --exclude='dist' --exclude='*.tar.gz' \
        -czf /tmp/stock.tar.gz -C "$(cd "$(dirname "$0")" && pwd)" .
SIZE=$(du -h /tmp/stock.tar.gz | cut -f1)
done_msg "打包完成 (${SIZE})"

# [2] 上传
step "📤 上传到 VPS"
run_cmd "正在上传..." scp -q /tmp/stock.tar.gz root@${VPS}:/tmp/
done_msg "上传完成"

# [3] 构建部署
case "$TARGET" in
    backend)
        step "🔧 构建后端"
        run_ssh "正在构建后端..." "cd ${DIR} && tar xzf /tmp/stock.tar.gz 2>/dev/null && docker compose up -d --build backend"
        done_msg "后端构建完成"
        ;;
    frontend)
        step "🎨 构建前端"
        run_ssh "正在构建前端..." "cd ${DIR} && tar xzf /tmp/stock.tar.gz 2>/dev/null && docker compose up -d --build frontend"
        done_msg "前端构建完成"
        ;;
    *)
        step "🚀 全量构建部署"
        run_ssh "正在构建中 (可能需要几分钟)..." "cd ${DIR} && tar xzf /tmp/stock.tar.gz 2>/dev/null && docker compose up -d --build"
        done_msg "全量构建完成"
        ;;
esac

# [4] 清理
step "🧹 清理临时文件"
ssh root@${VPS} "rm -f /tmp/stock.tar.gz" 2>/dev/null || true
rm -f /tmp/stock.tar.gz
done_msg "清理完成"

# ─────────────────────────────────────────

END=$(date +%s)
ELAPSED=$((END - START))

if [ $ELAPSED -ge 60 ]; then
    TIME_STR="$((ELAPSED / 60))m $((ELAPSED % 60))s"
else
    TIME_STR="${ELAPSED}s"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  ✅ 部署完成!  耗时 ${TIME_STR}${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "  ${DIM}前端:${RESET} https://stock.xmqaq.top | http://${VPS}:8888"
echo -e "  ${DIM}后端:${RESET} http://${VPS}:5555"
echo ""
