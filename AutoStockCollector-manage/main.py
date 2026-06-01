"""
AutoStockCollector 主入口
Flask应用启动文件
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

dotenv_path = project_root / ".env"
if dotenv_path.exists():
    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from api import create_app
from config.settings import Settings
from utils.logger import get_logger


logger = get_logger(__name__)


def main():
    app = create_app()  # bootstrap (DB, cron, AI keys) is called inside create_app()

    host = Settings.API_CONFIG["host"]
    port = Settings.API_CONFIG["port"]
    debug = Settings.API_CONFIG["debug"]

    logger.info(f"Starting AutoStockCollector on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()