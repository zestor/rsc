from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parent
_INNER_PACKAGE = Path(__file__).with_name("rsc")
__path__ = [str(_ROOT), str(_INNER_PACKAGE)]

from .rsc import *  # noqa: F401,F403,E402

__path__ = [str(_INNER_PACKAGE)]