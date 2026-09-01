import sys
from pathlib import Path

# Ensure the project root is importable when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
