"""Structured file logging for AQUASIGHT™ MMF (stdlib logging).

Default log file: ``logs/aquasight.log``. Tests may call ``configure()`` to redirect.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

_LOGGER_NAME = "aquasight.engine"
_DEFAULT_LOG = Path("logs") / "aquasight.log"

_logger: Optional[logging.Logger] = None
_path_override: Optional[Path] = None


def configure(log_file: str | Path | None = None) -> None:
    """Reset handlers; next ``get_logger()`` uses ``log_file`` or the default path."""
    global _logger, _path_override
    _path_override = Path(log_file) if log_file else None
    if _logger is not None:
        for h in list(_logger.handlers):
            _logger.removeHandler(h)
            h.close()
        _logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    target = _path_override or _DEFAULT_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(_LOGGER_NAME)
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    fh = logging.FileHandler(target, encoding="utf-8")
    fh.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    lg.addHandler(fh)
    _logger = lg
    return lg


def log_compute_start(project_name: str = "", doc_number: str = "") -> None:
    get_logger().info("compute_start project=%r doc=%r", project_name, doc_number)


def log_compute_end(
    elapsed_s: float,
    *,
    valid: bool,
    fallback_used: bool,
    n_validation_warnings: int,
    n_output_warnings: Optional[int],
    exc: Optional[BaseException],
) -> None:
    lg = get_logger()
    if exc is not None:
        lg.error(
            "compute_end aborted after %.4fs: %s",
            elapsed_s,
            exc,
            exc_info=exc,
        )
        return
    lg.info(
        "compute_end ok elapsed_s=%.4f valid=%s fallback=%s val_warns=%s out_warns=%s",
        elapsed_s,
        valid,
        fallback_used,
        n_validation_warnings,
        n_output_warnings,
    )


def log_warning(message: str) -> None:
    get_logger().warning("%s", message)


def log_validation_errors(errors: Iterable[str]) -> None:
    lg = get_logger()
    errs = list(errors)
    if not errs:
        return
    lg.warning("validation_errors count=%d: %s", len(errs), " | ".join(errs))


def log_exception(context: str, exc: BaseException) -> None:
    get_logger().error("%s: %s", context, exc, exc_info=sys.exc_info())


def log_project_save(project_name: str, doc_number: str = "") -> None:
    get_logger().info("project_save JSON name=%r doc=%r", project_name, doc_number)


def log_project_load(project_name: str, doc_number: str = "") -> None:
    get_logger().info("project_load JSON name=%r doc=%r", project_name, doc_number)


def log_db_project_save(project_key: str, created: bool) -> None:
    get_logger().info("project_db save key=%r created=%s", project_key, created)


def log_db_project_load(project_key: str) -> None:
    get_logger().info("project_db load key=%r", project_key)


__all__ = [
    "configure",
    "get_logger",
    "log_compute_start",
    "log_compute_end",
    "log_warning",
    "log_validation_errors",
    "log_exception",
    "log_project_save",
    "log_project_load",
    "log_db_project_save",
    "log_db_project_load",
]
