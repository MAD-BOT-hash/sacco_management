__version__ = "1.0.0"

# Import fix functions for bench execute access
from .fix_sacco_management import run_all_fixes, fix_controllers, ensure_utility_functions, insert_dashboard_charts

__all__ = [
    "run_all_fixes",
    "fix_controllers",
    "ensure_utility_functions",
    "insert_dashboard_charts"
]
