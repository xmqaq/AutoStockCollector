# AutoStockCollector

<<<<<<< HEAD
一站式 A 股 AI 量化分析系统 —— 全自动数据采集 · 智能数据治理 · 多模型 AI 决策 · 量化回测 · 可视化工作流

[![CI](https://github.com/xmqaq/AutoStockCollector/actions/workflows/ci.yml/badge.svg)](https://github.com/xmqaq/AutoStockCollector/actions/workflows/ci.yml)

=======
[![CI](https://github.com/xmqaq/AutoStockCollector/actions/workflows/ci.yml/badge.svg)](https://github.com/xmqaq/AutoStockCollector/actions/workflows/ci.yml)

一站式 A 股 AI 量化分析系统 —— 全自动数据采集 · 智能数据治理 · 多模型 AI 决策 · 量化回测 · 可视化工作流

>>>>>>> d27c0f8200ca764be0cab3143211a08f31bf91ad
> **免责声明**：本项目所有数据、AI 分析结论、选股策略与回测结果仅用于量化技术研究与学习参考，不构成任何投资建议。股市风险极高，使用者所有实盘交易风险自行承担。

## 功能概览

### 数据中心
- **采集中心** — 全自动采集 A 股 K 线、财务、资金流向、龙虎榜、融资融券、新闻舆情等 13 类数据，智能断点续采、数据校验、缺失补采
- **实时行情** — 腾讯行情接口驱动的盘中实时数据，涵盖价格、涨跌、成交量、委买委卖
- **板块流向 / 资金排行** — 板块轮动热力图、个股资金流向排行、主力散户资金对比
- **龙虎榜 / 融资融券** — 每日龙虎榜席位明细、两融余额与趋势
- **新闻舆情** — 多源财经资讯采集，关联个股与板块，支撑事件驱动策略

### AI 智能
- **AI 智能中枢** — 多模型统一调度面板，支持 Claude / GPT / 通义千问等大模型，可插拔切换
- **量化选股** — 7 套 AI 选股策略（舆情驱动、资金跟踪、价值选股、板块轮动、趋势融合、反转套利、自选优选），结构化 JSON 输出，全流程可回测
- **个股深度分析** — 聚合技术面 + 基本面 + 资金面 + 舆情四维度，生成量化评分与 AI 研判报告
- **AI Agent 管理** — 多 Agent 协作对话、Multi-Agent 分析面板
- **AI Key 管理** — 多厂商 API Key 统一管理，优先级调度、频次限额、容错轮转

### 量化交易
- **仓位管理** — 持仓盈亏追踪、收益曲线图表、实时价格联动
- **模拟交易** — 内置交易引擎，按 A 股规则计算佣金/印花税，校验交易时段
- **工作流管理** — 可视化拖拽编排选股/监控/分析工作流，支持定时调度

### 其他
- **自选股** — 分组管理、批量导入、快照追踪、异动监控
- **策略回测** — Backtrader 引擎，支持 AI 策略 + 传统规则策略双模式回测

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.10+ · Flask · AKShare · Backtrader · Pydantic |
| **前端** | Vue 3 · TypeScript · Vite · Element Plus · ECharts · Pinia |
| **数据库** | MongoDB 5.0+ (pymongo) |
| **AI** | Claude · OpenAI · 通义千问 — 统一适配器，可插拔扩展 |
| **部署** | Docker Compose · Nginx 反代 |
| **CI** | GitHub Actions（后端单元/集成测试 + 前端构建） |

## 项目结构

```
AutoStockCollector/
├── AutoStockCollector-manage/          # 后端服务 (Flask, port 5555)
│   ├── api/routes/                     # REST API 路由
│   ├── core/
│   │   ├── collector/                  # 数据采集器（K线/财务/资金/新闻/...）
│   │   ├── scheduler/                  # 定时任务调度
│   │   ├── storage/                    # MongoDB 存储层
│   │   ├── validator/                  # 数据校验引擎
│   │   └── risk_control/              # 风控：限流/熔断/退避
│   ├── modules/
│   │   ├── ai/                         # AI 引擎（分析/选股/深度分析/LLM路由）
│   │   ├── ai_selector/               # 量化选股策略（因子/回测/优化器）
│   │   ├── paper_trading/             # 模拟交易引擎
│   │   ├── workflow/                   # 可视化工作流执行器
│   │   ├── watchlist/                  # 自选股管理
│   │   └── news/                       # 新闻管理
│   └── tests/                          # 单元测试 + 集成测试
├── AutoStockCollector-web/             # 前端 (Vue 3, port 8888)
│   └── src/
│       ├── views/                      # 20+ 页面
│       ├── components/                 # 可复用组件（K线图/热力图/情绪面板/...）
│       ├── api/                        # 后端 API 对接层
│       └── stores/                     # Pinia 状态管理
├── docker-compose.yml                  # 一键编排
└── .github/workflows/ci.yml           # CI 流水线
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 22+ & pnpm
- MongoDB 5.0+

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/xmqaq/AutoStockCollector.git
cd AutoStockCollector

# 2. 后端
cd AutoStockCollector-manage
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 填入 MongoDB 连接串和 AI API Key
python main.py          # 启动后端 http://localhost:5555

# 3. 前端（新终端）
cd AutoStockCollector-web
pnpm install
pnpm dev                # 启动前端 http://localhost:5173
```

### Docker 部署

```bash
# 配置环境变量
cp AutoStockCollector-manage/.env.example AutoStockCollector-manage/.env
# 编辑 .env 填入 MONGODB_URI、AI API Key 等

# 一键启动
docker compose up -d --build

# 访问
# 前端：http://localhost:8888
# 后端 API 通过 Nginx 自动代理到 /api/*
```

### 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `MONGODB_URI` | MongoDB 连接串 | `mongodb://user:pass@host:27017/stock_collector?authSource=admin` |
| `MONGODB_DATABASE` | 数据库名 | `stock_collector` |
| `FLASK_DEBUG` | 调试模式 | `false` |
| AI 相关 Key | 通过 Web 界面「AI Key 管理」页面配置即可 | — |

## 核心设计

### 数据采集策略

- **固定数据源优先级**：全局统一「非东财优先」规则（新浪 > 同花顺 > 百度 > 东方财富），无自动降级，保障数据来源一致可溯
- **智能续采**：基于数据校验结果精准定位缺失区间，仅补采缺失数据，不做全量重采
- **防限流风控**：场景化控频 + 指数退避 + 熔断休眠 + 冷热分流，纯代码实现，无需代理 IP

### AI 多模型架构

- **统一适配器**：屏蔽厂商接口差异，新增模型只需实现适配层
- **差异化调度**：核心分析调用高端模型，批量筛选调用高性价比模型
- **容错轮转**：单模型异常自动轮转备用模型，全模型不可用时降级为规则引擎
- **结果缓存**：同日同标的同策略结果去重复用，控制成本

### 数据校验体系
<<<<<<< HEAD

- 时序连续性校验（基于交易日历）
- 核心字段完整性校验
- 数据合法性校验（极值/负数/重复过滤）
- 完整度评分 + 闭环复核

## 截图预览

> 截图待补充，可运行项目后自行体验：系统总览、采集中心、AI 智能中枢、量化选股、个股深度分析、工作流画布等 20+ 页面。

## TODO

以下是后续计划的方向，欢迎贡献：

- [ ] **实盘券商对接** — 对接券商 API（如 QMT/XtQuant），打通从选股到自动下单的完整链路
- [ ] **多智能体辩论** — 多个 AI Agent 从不同立场（多头/空头/风控）辩论同一标的，综合输出共识结论
- [ ] **AI 因子挖掘** — 利用大模型自动发现新的量化因子，替代人工特征工程
- [ ] **向量行情对标** — 基于历史 K 线形态的向量相似度检索，找到当前走势的历史类比
- [ ] **WebSocket 实时推送** — 盘中行情、异动告警、任务进度改为 WebSocket 推送，替代轮询
- [ ] **用户认证与多租户** — 增加登录体系和权限隔离，支持多用户独立使用
- [ ] **移动端适配** — 响应式布局或独立小程序，方便盘中手机查看
- [ ] **策略回测可视化** — 回测结果的收益曲线、交易记录可视化展示，目前仅有数据输出
- [ ] **更多数据源接入** — 支持 Tushare、JQData 等付费数据源，提升数据质量和覆盖面
- [ ] **通知告警** — 集成企业微信/钉钉/Telegram 推送，异动和策略信号实时通知

## 贡献

欢迎提交 Issue 和 Pull Request。提交前请确保：

1. 后端测试通过：`python -m unittest discover -s AutoStockCollector-manage/tests -v`
2. 前端构建通过：`cd AutoStockCollector-web && pnpm build`

## License

=======

- 时序连续性校验（基于交易日历）
- 核心字段完整性校验
- 数据合法性校验（极值/负数/重复过滤）
- 完整度评分 + 闭环复核

## 截图预览

### 系统总览
![系统总览](screenshots/dashboard.png)

### 采集中心
![采集中心](screenshots/data-monitor.png)

### 实时行情
![实时行情](screenshots/market.png)

### 板块流向热力图
![板块流向](screenshots/sector-flow.png)

### AI 智能中枢
![AI智能中枢](screenshots/ai-dashboard.png)

### 工作流管理
![工作流管理](screenshots/workflow.png)

## TODO

以下是后续计划的方向，欢迎贡献：

- [ ] **实盘券商对接** — 对接券商 API（如 QMT/XtQuant），打通从选股到自动下单的完整链路
- [ ] **多智能体辩论** — 多个 AI Agent 从不同立场（多头/空头/风控）辩论同一标的，综合输出共识结论
- [ ] **AI 因子挖掘** — 利用大模型自动发现新的量化因子，替代人工特征工程
- [ ] **向量行情对标** — 基于历史 K 线形态的向量相似度检索，找到当前走势的历史类比
- [ ] **WebSocket 实时推送** — 盘中行情、异动告警、任务进度改为 WebSocket 推送，替代轮询
- [ ] **用户认证与多租户** — 增加登录体系和权限隔离，支持多用户独立使用
- [ ] **移动端适配** — 响应式布局或独立小程序，方便盘中手机查看
- [ ] **策略回测可视化** — 回测结果的收益曲线、交易记录可视化展示，目前仅有数据输出
- [ ] **更多数据源接入** — 支持 Tushare、JQData 等付费数据源，提升数据质量和覆盖面
- [ ] **通知告警** — 集成企业微信/钉钉/Telegram 推送，异动和策略信号实时通知

## 贡献

欢迎提交 Issue 和 Pull Request。提交前请确保：

1. 后端测试通过：`python -m unittest discover -s AutoStockCollector-manage/tests -v`
2. 前端构建通过：`cd AutoStockCollector-web && pnpm build`

## License

>>>>>>> d27c0f8200ca764be0cab3143211a08f31bf91ad
MIT
