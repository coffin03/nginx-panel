import os
import sys
import tempfile
from pathlib import Path

os.environ["NGINX_PANEL_DATA_DIR"] = tempfile.mkdtemp(prefix="ngp-test-")
os.environ["NGINX_PANEL_NO_BROWSER"] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))