"""smokeTIPs — observability + governance for AI orchestration.

Watch, score, and govern the layers an orchestrator delegates to. Where there's
smoke, there's a tip. The ledger is plain files (JSONL + markdown), so everything
is editable and traceable.
"""

from .client import emit, guard, layer
from .guard import Config, Decision, check
from .ledger import Event

__version__ = "0.1.0"
__all__ = ["emit", "guard", "layer", "check", "Config", "Decision", "Event",
           "__version__"]
