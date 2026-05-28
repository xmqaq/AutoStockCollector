#!/usr/local/bin/python3.10
"""
实时监控 AutoStockCollector 数据采集进度
用法：python monitor.py [--interval 3]
"""
import sys
import time
import json
import signal
import argparse
import urllib.request
from datetime import datetime, timedelta

# ── ANSI 颜色 ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
WHITE  = "\033[97m"
GRAY   = "\033[90m"

# ── 工具 ───────────────────────────────────────────────────────────────────
def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def move_to_top():
    sys.stdout.write("\033[H")
    sys.stdout.flush()

def fetch_progress(host: str) -> dict | None:
    try:
        url = f"{host}/api/v1/collect/progress_all"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None

def fetch_db_counts(host: str) -> dict:
    """通过 /api/v1/scheduler/stats 等接口获取 DB 记录数（用 task 统计代替）"""
    counts = {}
    try:
        url = f"{host}/api/v1/tasks?limit=1"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass  # 仅用于验证服务在线
    except Exception:
        pass
    return counts

def bar(percent: float, width: int = 24) -> str:
    filled = int(percent / 100 * width)
    empty  = width - filled
    return f"{'█' * filled}{'░' * empty}"

def status_color(status: str) -> str:
    return {
        "completed": GREEN,
        "running":   YELLOW,
        "pending":   BLUE,
        "failed":    RED,
        "cancelled": GRAY,
        "not_started": GRAY,
    }.get(status, WHITE)

def status_icon(status: str) -> str:
    return {
        "completed":   "✅",
        "running":     "🔄",
        "pending":     "⏳",
        "failed":      "❌",
        "cancelled":   "⛔",
        "not_started": "  ",
    }.get(status, "  ")

def fmt_count(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}w"
    return f"{n:,}"

def eta(elapsed: float, percent: float) -> str:
    if percent <= 0 or percent >= 100:
        return "  --:--"
    remaining = elapsed / percent * (100 - percent)
    m, s = divmod(int(remaining), 60)
    h, m = divmod(m, 60)
    if h:
        return f"  ~{h}h{m:02d}m"
    return f"  ~{m:02d}m{s:02d}s"

# ── 渲染 ───────────────────────────────────────────────────────────────────
TYPE_LABELS = {
    "kline":        "K线数据",
    "stock_info":   "股票基础信息",
    "financial":    "财务数据",
    "news":         "新闻舆情",
    "fund_flow":    "资金流向",
    "dragon_tiger": "龙虎榜",
    "sector":       "板块数据",
    "margin":       "融资融券",
}

ORDER = ["kline", "stock_info", "financial", "fund_flow",
         "dragon_tiger", "margin", "sector", "news"]

def render(data: dict, last_data: dict | None, refresh: int, host: str,
           start_times: dict, iteration: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tasks       = data.get("tasks", {})
    overall_pct = data.get("overall_percent", 0.0)
    completed   = data.get("completed_types", 0)
    total_types = data.get("total_types", 8)
    all_done    = data.get("all_done", False)

    lines = []

    # ── 标题栏 ────────────────────────────────────────────────────────────
    lines.append(f"{BOLD}{CYAN}{'═'*72}{RESET}")
    lines.append(
        f"{BOLD}{CYAN}  AutoStockCollector  数据采集监控{RESET}"
        f"   {GRAY}刷新间隔 {refresh}s  |  {now}{RESET}"
    )
    lines.append(f"{BOLD}{CYAN}{'═'*72}{RESET}")

    # ── 总进度 ────────────────────────────────────────────────────────────
    overall_color = GREEN if all_done else YELLOW
    overall_bar   = bar(overall_pct, 36)
    done_str      = f"{GREEN}全部完成！{RESET}" if all_done else f"{completed}/{total_types} 类完成"
    lines.append(
        f"\n  {BOLD}总进度{RESET}  "
        f"{overall_color}{overall_bar}{RESET} "
        f"{BOLD}{overall_pct:5.1f}%{RESET}   {done_str}\n"
    )

    # ── 列头 ──────────────────────────────────────────────────────────────
    lines.append(
        f"  {BOLD}{GRAY}{'数据类型':<10}  {'状态':<9}  "
        f"{'进度条':^26}  {'完成度':>6}  "
        f"{'成功':>6}  {'失败':>5}  {'已用时':>7}  {'预计剩余':>8}{RESET}"
    )
    lines.append(f"  {GRAY}{'─'*68}{RESET}")

    # ── 每类任务 ─────────────────────────────────────────────────────────
    for ttype in ORDER:
        task    = tasks.get(ttype, {})
        status  = task.get("status", "not_started")
        pct     = task.get("percent", 0.0)
        success = task.get("success", 0)
        failed  = task.get("failed", 0)
        elapsed = task.get("elapsed_time", 0.0)
        tid     = task.get("task_id") or ""
        label   = TYPE_LABELS.get(ttype, ttype)
        icon    = status_icon(status)
        color   = status_color(status)

        # 追踪开始时间以计算真实已用时
        if status == "running" and ttype not in start_times:
            start_times[ttype] = time.time()
        if status == "completed" and ttype in start_times:
            elapsed = time.time() - start_times[ttype]

        elapsed_str = ""
        if elapsed > 0:
            m, s = divmod(int(elapsed), 60)
            h, m = divmod(m, 60)
            elapsed_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"00:{m:02d}:{s:02d}"

        eta_str = eta(elapsed, pct) if status == "running" else ""
        prog_bar = f"{color}{bar(pct, 22)}{RESET}"

        lines.append(
            f"  {icon} {BOLD}{label:<10}{RESET}"
            f"  {color}{status:<9}{RESET}"
            f"  {prog_bar}  "
            f"{BOLD}{pct:5.1f}%{RESET}  "
            f"{GREEN}{fmt_count(success):>6}{RESET}  "
            f"{RED if failed else GRAY}{failed:>5}{RESET}  "
            f"{GRAY}{elapsed_str:>7}{RESET}  "
            f"{CYAN}{eta_str:<10}{RESET}"
        )

    lines.append(f"\n  {GRAY}{'─'*68}{RESET}")

    # ── 统计小结 ──────────────────────────────────────────────────────────
    total_success = sum(t.get("success", 0) for t in tasks.values())
    total_failed  = sum(t.get("failed", 0)  for t in tasks.values())
    lines.append(
        f"\n  {BOLD}累计写入{RESET}  "
        f"{GREEN}{fmt_count(total_success)} 条成功{RESET}  "
        f"{RED if total_failed else GRAY}{fmt_count(total_failed)} 条失败{RESET}"
        f"   {GRAY}第 {iteration} 次刷新{RESET}"
    )

    # ── 底部提示 ──────────────────────────────────────────────────────────
    lines.append(f"\n  {GRAY}按 Ctrl+C 退出监控{RESET}")
    lines.append(f"{BOLD}{CYAN}{'═'*72}{RESET}\n")

    return "\n".join(lines)

# ── 主循环 ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AutoStockCollector 采集进度监控")
    parser.add_argument("--host",     default="http://localhost:5555", help="服务地址")
    parser.add_argument("--interval", default=3, type=int,            help="刷新间隔（秒）")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda *_: (
        sys.stdout.write(f"\n{RESET}{CYAN}监控已退出。{RESET}\n"),
        sys.exit(0)
    ))

    clear_screen()
    start_times: dict = {}
    last_data   = None
    iteration   = 0
    first_draw  = True

    print(f"{CYAN}正在连接 {args.host} ...{RESET}")

    while True:
        data = fetch_progress(args.host)

        if data is None:
            if first_draw:
                clear_screen()
            move_to_top()
            print(f"\n  {RED}⚠  无法连接服务 {args.host}{RESET}")
            print(f"  {GRAY}请确认 Flask 服务已启动（python main.py）{RESET}\n")
        else:
            iteration += 1
            output = render(data, last_data, args.interval, args.host,
                            start_times, iteration)
            if first_draw:
                clear_screen()
                first_draw = False
            move_to_top()
            sys.stdout.write(output)
            sys.stdout.flush()
            last_data = data

            if data.get("all_done"):
                sys.stdout.write(
                    f"\n  {GREEN}{BOLD}🎉  所有 8 类数据采集完成！{RESET}\n\n"
                )
                sys.stdout.flush()
                break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
