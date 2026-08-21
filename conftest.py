"""Put the backend package on the path so `import app...` works from the repo root."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
