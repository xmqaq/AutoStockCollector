#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
#  AutoStockCollector 本地一键启动脚本
#  后端: Flask :5555  |  前端: Vite :5173
#  用法: ./run.sh          启动前后端
#        ./run.sh backend  只启动后端
#        ./run.sh frontend 只启动前端
#        ./run.sh stop     停止所有
# ──────────────────────────────────────────────────────────
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/AutoStockCollector-manage"
FRONTEND_DIR="$ROOT_DIR/AutoStockCollector-web"
PID_DIR="$ROOT_DIR/.pids"
BACKEND_LOG="$ROOT_DIR/.backend.log"
FRONTEND_LOG="$ROOT_DIR/.frontend.log"

# ── 颜色 ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}${BOLD}  ╔══════════════════════════════════════════════╗${RESET}"
  echo -e "${CYAN}${BOLD}  ║       🚀 AutoStockCollector  Launcher       ║${RESET}"
  echo -e "${CYAN}${BOLD}  ╚══════════════════════════════════════════════╝${RESET}"
  echo ""
}

info()    { echo -e "  ${BLUE}[INFO]${RESET}  $*"; }
success() { echo -e "  ${GREEN}[  OK]${RESET}  $*"; }
warn()    { echo -e "  ${YELLOW}[WARN]${RESET}  $*"; }
fail()    { echo -e "  ${RED}[FAIL]${RESET}  $*"; }

separator() {
  echo -e "  ${DIM}──────────────────────────────────────────────${RESET}"
}

# ── PID 管理 ──────────────────────────────────────────────
mkdir -p "$PID_DIR"

save_pid()  { echo "$2" > "$PID_DIR/$1.pid"; }
read_pid()  { cat "$PID_DIR/$1.pid" 2>/dev/null; }
clear_pid() { rm -f "$PID_DIR/$1.pid"; }

is_running() {
  local pid
  pid=$(read_pid "$1")
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# ── 停止 ──────────────────────────────────────────────────
stop_service() {
  local name="$1"
  if is_running "$name"; then
    local pid
    pid=$(read_pid "$name")
    kill "$pid" 2>/dev/null
    # 等待退出（最多 5 秒）
    for _ in {1..10}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    # 仍在运行则强杀
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
    clear_pid "$name"
    success "$name 已停止 (PID $pid)"
  else
    info "$name 未在运行"
    clear_pid "$name"
  fi
}

do_stop() {
  banner
  info "正在停止服务..."
  separator
  stop_service "backend"
  stop_service "frontend"
  separator
  echo ""
  success "全部已停止"
  echo ""
}

# ── 端口检测 ──────────────────────────────────────────────
check_port() {
  local port=$1 name=$2
  if lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    local occ_pid
    occ_pid=$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -1)
    warn "端口 $port 已被占用 (PID $occ_pid)"

    # 如果是我们自己的进程，先停掉
    local saved_pid
    saved_pid=$(read_pid "$name")
    if [[ "$occ_pid" == "$saved_pid" ]]; then
      info "检测到上次未关闭的 $name，正在重启..."
      stop_service "$name"
      return 0
    fi

    fail "请先释放端口 $port 或运行: kill $occ_pid"
    return 1
  fi
  return 0
}

# ── 启动后端 ──────────────────────────────────────────────
start_backend() {
  info "启动后端 Flask 服务..."

  if ! [[ -d "$BACKEND_DIR/venv" ]]; then
    fail "未找到 Python 虚拟环境: $BACKEND_DIR/venv"
    fail "请先执行: cd $BACKEND_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    return 1
  fi

  check_port 5555 "backend" || return 1

  cd "$BACKEND_DIR"
  "$BACKEND_DIR/venv/bin/python" main.py > "$BACKEND_LOG" 2>&1 &
  local pid=$!
  save_pid "backend" "$pid"

  # 等待后端就绪（最多 15 秒）
  local ready=false
  for i in {1..30}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      fail "后端进程异常退出，查看日志: $BACKEND_LOG"
      tail -5 "$BACKEND_LOG" 2>/dev/null | while read -r line; do
        echo -e "         ${DIM}$line${RESET}"
      done
      clear_pid "backend"
      return 1
    fi
    if curl -s http://localhost:5555/health >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 0.5
  done

  if $ready; then
    success "后端已启动  ${DIM}PID=$pid${RESET}"
    info "  地址:  ${BOLD}http://localhost:5555${RESET}"
    info "  日志:  ${DIM}$BACKEND_LOG${RESET}"
  else
    warn "后端进程已启动 (PID $pid)，但健康检查未通过，可能仍在初始化"
    info "  日志:  ${DIM}$BACKEND_LOG${RESET}"
  fi
}

# ── 启动前端 ──────────────────────────────────────────────
start_frontend() {
  info "启动前端 Vite 开发服务..."

  if ! [[ -d "$FRONTEND_DIR/node_modules" ]]; then
    warn "未找到 node_modules，正在安装依赖..."
    cd "$FRONTEND_DIR"
    pnpm install --frozen-lockfile 2>&1 | tail -3
  fi

  check_port 5173 "frontend" || return 1

  cd "$FRONTEND_DIR"
  npx vite --host > "$FRONTEND_LOG" 2>&1 &
  local pid=$!
  save_pid "frontend" "$pid"

  # 等待前端就绪（最多 10 秒）
  local ready=false
  for i in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      fail "前端进程异常退出，查看日志: $FRONTEND_LOG"
      tail -5 "$FRONTEND_LOG" 2>/dev/null | while read -r line; do
        echo -e "         ${DIM}$line${RESET}"
      done
      clear_pid "frontend"
      return 1
    fi
    if curl -s http://localhost:5173 >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 0.5
  done

  if $ready; then
    success "前端已启动  ${DIM}PID=$pid${RESET}"
    info "  地址:  ${BOLD}http://localhost:5173${RESET}"
    info "  日志:  ${DIM}$FRONTEND_LOG${RESET}"
  else
    warn "前端进程已启动 (PID $pid)，可能仍在编译中"
    info "  日志:  ${DIM}$FRONTEND_LOG${RESET}"
  fi
}

# ── 状态摘要 ──────────────────────────────────────────────
print_summary() {
  echo ""
  separator
  echo ""
  echo -e "  ${BOLD}服务状态${RESET}"
  echo ""

  if is_running "backend"; then
    echo -e "    ${GREEN}●${RESET}  后端 API     ${BOLD}http://localhost:5555${RESET}   ${DIM}PID $(read_pid backend)${RESET}"
  else
    echo -e "    ${RED}●${RESET}  后端 API     未运行"
  fi

  if is_running "frontend"; then
    echo -e "    ${GREEN}●${RESET}  前端 Dev     ${BOLD}http://localhost:5173${RESET}   ${DIM}PID $(read_pid frontend)${RESET}"
  else
    echo -e "    ${RED}●${RESET}  前端 Dev     未运行"
  fi

  echo ""
  separator
  echo -e "  ${DIM}停止服务:  ./run.sh stop${RESET}"
  echo -e "  ${DIM}查看日志:  tail -f .backend.log  |  tail -f .frontend.log${RESET}"
  echo ""
}

# ── 主入口 ────────────────────────────────────────────────
case "${1:-all}" in
  stop)
    do_stop
    ;;
  backend)
    banner
    start_backend
    print_summary
    ;;
  frontend)
    banner
    start_frontend
    print_summary
    ;;
  all)
    banner
    start_backend
    separator
    start_frontend
    print_summary
    ;;
  *)
    echo "用法: $0 {all|backend|frontend|stop}"
    exit 1
    ;;
esac
