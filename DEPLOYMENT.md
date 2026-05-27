# AutoStockCollector 部署说明文档

## 一、项目概述

AutoStockCollector 是一套轻量化 A 股 AI 量化分析系统，集成全自动数据采集、智能数据治理、多模型 AI 决策、量化回测、全维度风控能力。

## 二、系统要求

### 2.1 运行环境
- **操作系统**：macOS / Linux / Windows
- **Python 版本**：Python 3.8+
- **数据库**：MongoDB 5.0+（本地或 Atlas 云服务）

### 2.2 硬件建议
- **CPU**：双核以上
- **内存**：4GB+
- **磁盘**：10GB+ 可用空间

## 三、部署步骤

### 3.1 环境准备

#### 3.1.1 安装 Python
确保已安装 Python 3.8 或更高版本：

```bash
python --version
```

#### 3.1.2 安装 MongoDB

**选项 A：使用 MongoDB Atlas（云服务）**
1. 注册 MongoDB Atlas 账号：https://www.mongodb.com/cloud/atlas
2. 创建免费集群（Shared Cluster）
3. 获取连接字符串，格式如：
   ```
   mongodb+srv://username:password@cluster.mongodb.net
   ```
4. 在 Atlas 安全设置中配置数据库用户名和密码
5. 在 IP Access List 中添加 `0.0.0.0/0` 或当前 IP

**选项 B：本地 MongoDB**
```bash
# macOS (使用 Homebrew)
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community

# Ubuntu/Debian
sudo apt install mongodb-org
sudo systemctl start mongod
```

### 3.2 项目部署

#### 3.2.1 克隆项目
```bash
git clone <repository-url>
cd AutoStockCollector
```

#### 3.2.2 创建虚拟环境（推荐）
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows
```

#### 3.2.3 安装依赖
```bash
pip install -r requirements.txt
```

#### 3.2.4 配置环境变量

复制配置文件并编辑：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入 MongoDB 连接信息：
```bash
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net
MONGODB_DATABASE=stock_collector
```

#### 3.2.5 验证安装
```bash
python -c "import akshare; print('AKShare version:', akshare.__version__)"
python -c "import pymongo; print('PyMongo installed')"
```

## 四、启动系统

### 4.1 开发环境启动
```bash
python main.py
```

服务启动后，访问 http://localhost:5000

### 4.2 生产环境部署

#### 4.2.1 使用 Gunicorn（推荐）
```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

#### 4.2.2 使用 Supervisor 管理进程
创建 `/etc/supervisor/conf.d/autostock.conf`：
```ini
[program:autostock]
command=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 main:app
directory=/path/to/AutoStockCollector
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/autostock.err.log
stdout_logfile=/var/log/autostock.out.log
```

启动 Supervisor：
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start autostock
```

#### 4.2.3 使用 Docker 部署

创建 `Dockerfile`：
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MONGODB_URI=mongodb://host:27017
ENV MONGODB_DATABASE=stock_collector

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "main:app"]
```

构建和运行：
```bash
docker build -t autostockcollector .
docker run -d -p 5000:5000 --name autostock autostockcollector
```

## 五、API 接口使用

### 5.1 健康检查
```bash
curl http://localhost:5000/health
```

### 5.2 任务管理
```bash
# 创建采集任务
curl -X POST http://localhost:5000/api/v1/task/create \
  -H "Content-Type: application/json" \
  -d '{"task_type": "kline", "params": {"codes": ["SH600000"]}}'

# 查询任务状态
curl http://localhost:5000/api/v1/task/<task_id>

# 列出所有任务
curl http://localhost:5000/api/v1/tasks
```

### 5.3 数据查询
```bash
# 查询K线数据
curl "http://localhost:5000/api/v1/kline/SH600000?start_date=2024-01-01&end_date=2024-01-31"

# 查询股票信息
curl http://localhost:5000/api/v1/stock/SH600000/info

# 查询新闻
curl "http://localhost:5000/api/v1/news?limit=50"
```

### 5.4 自选股管理
```bash
# 添加自选股
curl -X POST http://localhost:5000/api/v1/watchlist \
  -H "Content-Type: application/json" \
  -d '{"user_id": "default", "code": "SH600000", "group_id": "default"}'

# 查询自选股
curl http://localhost:5000/api/v1/watchlist?user_id=default
```

### 5.5 策略回测
```bash
# 运行回测
curl -X POST http://localhost:5000/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "ma_cross",
    "codes": ["SH600000"],
    "start_date": "2024-01-01",
    "end_date": "2024-06-30",
    "initial_cash": 1000000
  }'
```

## 六、定时任务配置

### 6.1 增量采集（每日收盘后）
建议设置每日 15:30-16:00 执行增量采集任务

### 6.2 数据校验（每日）
建议设置每日 18:00 执行数据校验

### 6.3 自选股监控（盘中）
建议设置每 15 分钟执行一次异动监控

## 七、日志管理

日志目录：`./logs/`
- 普通日志：保留 30 天
- 错误日志：保留 60 天

手动清理过期日志：
```bash
python -c "from utils.logger import clean_old_logs; clean_old_logs()"
```

## 八、故障排查

### 8.1 MongoDB 连接失败
```
检查 MONGODB_URI 配置是否正确
检查网络是否可访问 Atlas
检查 IP Access List 是否允许当前 IP
```

### 8.2 数据采集失败
```
检查网络连接
查看日志中的具体错误信息
确认 AKShare 接口是否正常
```

### 8.3 服务启动失败
```
检查端口是否被占用：lsof -i :5000
检查 Python 环境是否正确激活
查看启动日志错误信息
```

## 九、安全建议

1. **数据库安全**
   - 使用强密码
   - 限制 IP Access List
   - 考虑使用私有端点

2. **API 安全**
   - 生产环境建议配置 Nginx 反向代理
   - 考虑添加 API Key 认证
   - 配置 HTTPS

3. **密钥安全**
   - 不要将 `.env` 文件提交到代码仓库
   - 使用环境变量或密钥管理服务存储敏感信息

## 十、性能优化建议

1. **并发配置**：根据 API 限制调整并发数
2. **索引优化**：定期分析查询性能，创建必要索引
3. **数据清理**：定期清理过期日志和临时数据
4. **缓存策略**：启用 AI 结果缓存减少 API 调用

## 十一、技术支持

如遇问题，请检查：
1. `logs/` 目录下的错误日志
2. MongoDB Atlas 的监控面板
3. 系统资源使用情况