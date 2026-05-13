"""SQLite persistence for AQUASIGHT™ MMF projects (stdlib sqlite3 only).

Default file: ``aquasight.db`` in the process working directory.

Stores the same *inputs* payload as JSON export (``engine.project_io``); optional
*computed* snapshot excludes non-serialisable tab callables (severity fns).

Tables: ``projects``, ``snapshots``, ``scenarios``.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from engine import project_io as _pio

_COMPUTED_DB_EXCLUDE = frozenset({"lv_severity_fn", "ebct_severity_fn"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_key(inputs: dict) -> str:
    pn = inputs.get("project_name") or "project"
    dn = inputs.get("doc_number") or ""
    slug = re.sub(r"[^\w]+", "_", f"{pn}_{dn}").strip("_")
    return slug or "project"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_key TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            doc_number TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            schema_version TEXT,
            inputs_json TEXT NOT NULL,
            computed_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            inputs_json TEXT,
            computed_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scenario_name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(project_id, scenario_name),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshots_project ON snapshots(project_id, created_at DESC);
        """
    )


def init_db(db_path: str = "aquasight.db") -> None:
    """Create database file and tables if they do not exist."""
    conn = _connect(db_path)
    try:
        _create_tables(conn)
        conn.commit()
    finally:
        conn.close()


def _serialize_computed(computed: Optional[dict]) -> Optional[str]:
    if computed is None:
        return None
    slim = {k: v for k, v in computed.items() if k not in _COMPUTED_DB_EXCLUDE}
    return json.dumps(slim, default=str)


def save_project(
    db_path: str,
    inputs: dict,
    computed: Optional[dict] = None,
    *,
    notes: str = "",
    version_tag: Optional[str] = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """
    Insert or update a project row keyed by ``project_name`` + ``doc_number`` slug.

    Returns ``{"id", "project_key", "created", "updated_at"}`` where ``created`` is
    True if a new row was inserted.
    """
    init_db(db_path)
    key = _project_key(inputs)
    display = str(inputs.get("project_name") or "project")
    doc_number = str(inputs.get("doc_number") or "")
    schema_version = version_tag if version_tag is not None else _pio.SCHEMA_VERSION
    inputs_json = _pio.inputs_to_json(inputs)
    computed_json = _serialize_computed(computed)
    now = _utc_now()

    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM projects WHERE project_key = ?", (key,)
        ).fetchone()
        if row is not None and not overwrite:
            raise FileExistsError(f"Project already exists: {key!r} (set overwrite=True)")
        if row is None:
            conn.execute(
                """INSERT INTO projects (project_key, display_name, doc_number, notes,
                   schema_version, inputs_json, computed_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (key, display, doc_number, notes, schema_version, inputs_json, computed_json, now, now),
            )
            pid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            created = True
        else:
            pid = int(row["id"])
            conn.execute(
                """UPDATE projects SET display_name=?, doc_number=?, notes=?,
                   schema_version=?, inputs_json=?, computed_json=?, updated_at=?
                   WHERE id=?""",
                (display, doc_number, notes, schema_version, inputs_json, computed_json, now, pid),
            )
            created = False
        conn.commit()
        return {"id": pid, "project_key": key, "created": created, "updated_at": now}
    finally:
        conn.close()


def load_project(
    db_path: str,
    *,
    project_id: Optional[int] = None,
    project_key: Optional[str] = None,
) -> dict[str, Any]:
    """Load one project. Pass ``project_id`` or ``project_key``."""
    if (project_id is None) == (project_key is None):
        raise ValueError("Provide exactly one of project_id or project_key")
    init_db(db_path)
    conn = _connect(db_path)
    try:
        if project_id is not None:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM projects WHERE project_key = ?", (project_key,)).fetchone()
        if row is None:
            raise KeyError("project not found")
        inputs = _pio.json_to_inputs(row["inputs_json"])
        computed = None
        if row["computed_json"]:
            computed = json.loads(row["computed_json"])
        return {
            "id": int(row["id"]),
            "project_key": row["project_key"],
            "display_name": row["display_name"],
            "doc_number": row["doc_number"],
            "notes": row["notes"],
            "schema_version": row["schema_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "inputs": inputs,
            "computed": computed,
        }
    finally:
        conn.close()


def list_projects(db_path: str, *, limit: int = 200) -> list[dict[str, Any]]:
    """Return recent projects (metadata only, no large JSON blobs)."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """SELECT id, project_key, display_name, doc_number, notes,
                      schema_version, created_at, updated_at
               FROM projects ORDER BY updated_at DESC LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_snapshot(
    db_path: str,
    project_id: int,
    inputs: Optional[dict] = None,
    computed: Optional[dict] = None,
    *,
    label: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Append a history snapshot for a project (inputs/computed JSON optional each)."""
    init_db(db_path)
    now = _utc_now()
    inputs_json = _pio.inputs_to_json(inputs) if inputs is not None else None
    computed_json = _serialize_computed(computed)
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO snapshots (project_id, label, notes, inputs_json, computed_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (project_id, label, notes, inputs_json, computed_json, now),
        )
        conn.commit()
        sid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {"id": sid, "project_id": project_id, "created_at": now}
    finally:
        conn.close()


def project_history(db_path: str, project_id: int) -> list[dict[str, Any]]:
    """List snapshots for a project, newest first."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """SELECT id, project_id, label, notes, inputs_json, computed_json, created_at
               FROM snapshots WHERE project_id = ?
               ORDER BY created_at DESC, id DESC""",
            (project_id,),
        )
        rows = []
        for r in cur.fetchall():
            rows.append(
                {
                    "id": int(r["id"]),
                    "project_id": int(r["project_id"]),
                    "label": r["label"],
                    "notes": r["notes"],
                    "created_at": r["created_at"],
                    "has_inputs": r["inputs_json"] is not None,
                    "has_computed": r["computed_json"] is not None,
                }
            )
        return rows
    finally:
        conn.close()


def load_snapshot(db_path: str, snapshot_id: int) -> dict[str, Any]:
    """Load full snapshot row including JSON blobs."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        r = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if r is None:
            raise KeyError("snapshot not found")
        out: dict[str, Any] = {
            "id": int(r["id"]),
            "project_id": int(r["project_id"]),
            "label": r["label"],
            "notes": r["notes"],
            "created_at": r["created_at"],
            "inputs": None,
            "computed": None,
        }
        if r["inputs_json"]:
            out["inputs"] = _pio.json_to_inputs(r["inputs_json"])
        if r["computed_json"]:
            out["computed"] = json.loads(r["computed_json"])
        return out
    finally:
        conn.close()


def save_scenario(
    db_path: str,
    project_id: int,
    scenario_name: str,
    payload: dict,
) -> dict[str, Any]:
    """Upsert a named scenario JSON blob for a project."""
    init_db(db_path)
    now = _utc_now()
    blob = json.dumps(payload, default=str)
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO scenarios (project_id, scenario_name, payload_json, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(project_id, scenario_name) DO UPDATE SET
                 payload_json = excluded.payload_json,
                 created_at = excluded.created_at""",
            (project_id, scenario_name, blob, now),
        )
        conn.commit()
        return {"project_id": project_id, "scenario_name": scenario_name, "updated_at": now}
    finally:
        conn.close()


def list_scenarios(db_path: str, project_id: int) -> list[dict[str, Any]]:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT scenario_name, created_at FROM scenarios WHERE project_id = ? ORDER BY scenario_name",
            (project_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


__all__ = [
    "init_db",
    "save_project",
    "load_project",
    "list_projects",
    "save_snapshot",
    "project_history",
    "load_snapshot",
    "save_scenario",
    "list_scenarios",
]
