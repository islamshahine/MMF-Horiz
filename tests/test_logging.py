"""Tests for engine/logger.py — file logging and helpers."""
import pytest

from engine import logger


@pytest.fixture(autouse=True)
def _log_file(tmp_path):
    logf = tmp_path / "aquasight.log"
    logger.configure(str(logf))
    yield logf
    logger.configure(None)


def test_get_logger_creates_file(_log_file):
    lg = logger.get_logger()
    lg.info("hello")
    assert _log_file.is_file()
    txt = _log_file.read_text(encoding="utf-8")
    assert "hello" in txt
    assert "|" in txt


def test_log_warning(_log_file):
    logger.log_warning("headroom low")
    assert "headroom low" in _log_file.read_text(encoding="utf-8")


def test_log_validation_errors(_log_file):
    logger.log_validation_errors(["a", "b"])
    t = _log_file.read_text(encoding="utf-8")
    assert "validation_errors" in t
    assert "a | b" in t


def test_log_validation_errors_empty(_log_file):
    logger.log_validation_errors([])
    t = _log_file.read_text(encoding="utf-8")
    assert "validation_errors" not in t


def test_project_io_logs_on_serialise(_log_file):
    from engine.project_io import inputs_to_json, json_to_inputs

    s = inputs_to_json({"project_name": "PN", "doc_number": "D1", "streams": 1})
    assert "streams" in s
    assert "project_save JSON" in _log_file.read_text(encoding="utf-8")
    json_to_inputs(s)
    t = _log_file.read_text(encoding="utf-8")
    assert "project_load JSON" in t


def test_compute_all_logs_end(tmp_path):
    from engine.compute import compute_all
    from engine.validators import REFERENCE_FALLBACK_INPUTS

    import copy

    logf = tmp_path / "c.log"
    logger.configure(str(logf))
    try:
        out = compute_all(copy.deepcopy(REFERENCE_FALLBACK_INPUTS))
        assert "input_validation" in out
        txt = logf.read_text(encoding="utf-8")
        assert "compute_start" in txt
        assert "compute_end ok" in txt
    finally:
        logger.configure(None)
