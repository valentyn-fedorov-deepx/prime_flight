"""Makes the repository root importable for the tests, whatever invokes them.

`python -m pytest` puts the working directory on `sys.path` and `pytest` does not, so the suite passed locally and failed
on the first CI run with `ModuleNotFoundError: No module named 'pf'`. A conftest at the root fixes it for both, and for an
IDE that runs a single test file.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
