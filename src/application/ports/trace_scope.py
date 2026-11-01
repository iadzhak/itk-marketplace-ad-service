from collections.abc import Callable
from contextlib import AbstractContextManager

TraceScope = Callable[[str | None], AbstractContextManager[str]]
