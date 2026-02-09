import logging
import time
from contextlib import contextmanager
from typing import Optional

_STORE: Optional[list[str]] = None
_PREFIX_STACK: list[str] = []
_T0: Optional[float] = None
_CONFIGURED = False
_RUN_ID = -1


def _prefix() -> str:
    return "".join(_PREFIX_STACK)


class ListHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _STORE
        if _STORE is None:
            return  # logging enabled but no store bound

        _STORE.append(self.format(record))


class RuntimeFormatter(logging.Formatter):
    def __init__(self, start_time: float = None, prefix: str = ""):
        super().__init__("%(runtime)s%(prefix)s%(levelname)s %(filename)s %(message)s")
        self.start_time = start_time if start_time is not None else time.perf_counter()

    def format(self, record: logging.LogRecord) -> str:
        # runtime
        if _T0 is None:
            record.runtime = ""
        else:
            record.runtime = f"{time.perf_counter() - _T0:8.3f}s "
        record.prefix = _prefix()
        if record.prefix:
            record.prefix = f"{record.prefix} "
        return super().format(record)


_HANDLER = ListHandler()
_HANDLER.setFormatter(RuntimeFormatter())


def configure_once(level=logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logger = logging.getLogger("openbes")
    logger.setLevel(level)
    logger.addHandler(_HANDLER)
    _CONFIGURED = True


def bind(log_store: list[str], base_prefix: str = "") -> None:
    """
    Overwrites the global store/prefix/runtime anchor.
    Intended to be called by the root simulation during __init__.
    """
    global _STORE, _T0, _RUN_ID
    configure_once()

    _RUN_ID += 1
    run_id = _RUN_ID

    _STORE = log_store
    _T0 = time.perf_counter()

    _PREFIX_STACK.clear()
    if run_id > 0:
        _PREFIX_STACK.append(f"[run={run_id:03d}] ")
    if base_prefix:
        _PREFIX_STACK.append(base_prefix)


@contextmanager
def LogPrefix(prefix: str):
    _PREFIX_STACK.append(prefix or "")
    try:
        yield
    finally:
        _PREFIX_STACK.pop()


def getLogger(name: str) -> logging.Logger:
    configure_once()
    return logging.getLogger(name)
