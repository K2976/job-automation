"""Put this evaluation dir on the path so `eval_lib` / `labels` import as top-level
modules (mirrors how the standalone run_eval.py imports them)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
