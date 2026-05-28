# AutoStockCollector

A comprehensive stock data collection and analysis platform.

## Project Structure

```
AutoStockCollector/
├── AutoStockCollector-manage/    # Backend (Python)
└── AutoStockCollector-web/      # Frontend (React/TypeScript)
```

## Backend - AutoStockCollector-manage

Python-based backend for stock data collection, scheduling, and analysis.

### Features
- Data collection (K-line, financial reports, fund flow, etc.)
- Task scheduling with enhanced scheduler
- Data validation and risk control
- MongoDB storage
- AI-powered analysis

### Quick Start
```bash
cd AutoStockCollector-manage
pip install -r requirements.txt
python main.py
```

## Frontend - AutoStockCollector-web

React-based web interface for visualization and control.

### Quick Start
```bash
cd AutoStockCollector-web
pnpm install
pnpm run dev
```

## License

MIT License