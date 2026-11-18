"""开发/打包入口：python server/run.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nginx_panel.main import run  # noqa: E402

if __name__ == "__main__":
    run()