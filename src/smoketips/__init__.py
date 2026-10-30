"""smokeTIPs — observability + governance for AI orchestration.

Watch, score, and govern the layers an orchestrator delegates to. Where there's
smoke, there's a tip. The ledger is plain files (JSONL + markdown), so everything
is editable and traceable.
"""

from .badge import render as badge
from .client import emit, guard, layer
from .guard import Config, Decision, check
from .ledger import Event
from .policy import PolicyError, load_policy

__version__ = "0.1.0"
__all__ = ["emit", "guard", "layer", "check", "badge", "load_policy",
           "Config", "Decision", "Event", "PolicyError", "__version__"]
