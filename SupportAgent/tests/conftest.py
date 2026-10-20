import sys
from pathlib import Path

# The agent code runs with app/support_agent as its root, so tests import it the same way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "support_agent"))
