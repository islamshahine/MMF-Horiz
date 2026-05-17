"""SQLite persistence for AQUASIGHT™ MMF projects (stdlib sqlite3 only).

Default file: ``aquasight.db`` in the process working directory.

Stores the same *inputs* payload as JSON export (``engine.project_io``); optional
*computed* snapshot excludes non-serialisable tab callables (severity fns).

Tables: ``projects``, ``cases``, ``revisions``, ``snapshots`` (legacy), ``scenarios``.

B3 hierarchy: **Project** → **Case** → **Revision** (report hash per revision).
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

        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            case_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, case_name),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            revision_code TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            report_hash TEXT NOT NULL DEFAULT '',
            inputs_json TEXT,
            computed_json TEXT,
            parent_revision_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_revision_id) REFERENCES revisions(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cases_project ON cases(project_id, is_default DESC);
        CREATE INDEX IF NOT EXISTS idx_revisions_case ON revisions(case_id, created_at DESC);
        """
    )


_SCHEMA_VERSION = 3


def _migrate_schema_v3(conn: sqlite3.Connection) -> None:
    """Migrate legacy projects/snapshots into cases/revisions (idempotent)."""
    ver = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if ver >= _SCHEMA_VERSION:
        return

    from engine.project_revisions import revision_report_hash

    projects = conn.execute("SELECT id, inputs_json, computed_json FROM projects").fetchall()
    for prow in projects:
        pid = int(prow["id"])
        existing = conn.execute(
            "SELECT id FROM cases WHERE project_id = ? AND is_default = 1",
            (pid,),
        ).fetchone()
        if existing:
            case_id = int(existing["id"])
        else:
            now = _utc_now()
            conn.execute(
                """INSERT INTO cases (project_id, case_name, description, is_default, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (pid, "Main", "Default case (migrated)", 1, now, now),
            )
            case_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        n_rev = conn.execute(
            "SELECT COUNT(*) AS n FROM revisions WHERE case_id = ?", (case_id,),
        ).fetchone()["n"]
        if int(n_rev) == 0:
            snaps = conn.execute(
                """SELECT label, notes, inputs_json, computed_json, created_at
                   FROM snapshots WHERE project_id = ? ORDER BY created_at ASC, id ASC""",
                (pid,),
            ).fetchall()
            if snaps:
                for s in snaps:
                    inp_j = s["inputs_json"]
                    comp_j = s["computed_json"]
                    inputs = None
                    computed = None
                    if inp_j:
                        inputs = _pio.engine_inputs_dict(_pio.json_to_inputs(inp_j))
                    if comp_j:
                        computed = json.loads(comp_j)
                    rh = revision_report_hash(inputs, computed) if inputs else ""
                    conn.execute(
                        """INSERT INTO revisions (
                               case_id, revision_code, label, notes, report_hash,
                               inputs_json, computed_json, parent_revision_id, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            case_id,
                            "",
                            s["label"] or "",
                            s["notes"] or "",
                            rh,
                            inp_j,
                            comp_j,
                            None,
                            s["created_at"],
                        ),
                    )
            elif prow["inputs_json"]:
                inputs = _pio.engine_inputs_dict(_pio.json_to_inputs(prow["inputs_json"]))
                computed = json.loads(prow["computed_json"]) if prow["computed_json"] else None
                doc_rev = str(inputs.get("revision") or "A1")
                rh = revision_report_hash(inputs, computed)
                now = _utc_now()
                conn.execute(
                    """INSERT INTO revisions (
                           case_id, revision_code, label, notes, report_hash,
                           inputs_json, computed_json, parent_revision_id, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        case_id,
                        doc_rev,
                        "Head",
                        "",
                        rh,
                        prow["inputs_json"],
                        prow["computed_json"],
                        None,
                        now,
                    ),
                )

    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")


def init_db(db_path: str = "aquasight.db") -> None:
    """Create database file and tables if they do not exist."""
    conn = _connect(db_path)
    try:
        _create_tables(conn)
        _migrate_schema_v3(conn)
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
    ui_session_overrides: Optional[dict[str, Any]] = None,
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
    inputs_json = _pio.inputs_to_json(inputs, ui_session_overrides=ui_session_overrides)
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
        try:
            from engine import logger as _log

            _log.log_db_project_save(key, created)
        except Exception:
            pass
        return {"id": pid, "project_key": key, "created": created, "updated_at": now}
    finally:
        conn.close()


def update_project_by_id(
    db_path: str,
    project_id: int,
    inputs: dict,
    computed: Optional[dict] = None,
    *,
    notes: Optional[str] = None,
    ui_session_overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Overwrite an existing library row by primary key (not project_key slug alone)."""
    init_db(db_path)
    key = _project_key(inputs)
    display = str(inputs.get("project_name") or "project")
    doc_number = str(inputs.get("doc_number") or "")
    schema_version = _pio.SCHEMA_VERSION
    inputs_json = _pio.inputs_to_json(inputs, ui_session_overrides=ui_session_overrides)
    computed_json = _serialize_computed(computed)
    now = _utc_now()

    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError("project not found")
        clash = conn.execute(
            "SELECT id FROM projects WHERE project_key = ? AND id != ?",
            (key, project_id),
        ).fetchone()
        if clash is not None:
            raise ValueError(f"Another project already uses key {key!r}")

        if notes is None:
            conn.execute(
                """UPDATE projects SET project_key=?, display_name=?, doc_number=?,
                   schema_version=?, inputs_json=?, computed_json=?, updated_at=?
                   WHERE id=?""",
                (key, display, doc_number, schema_version, inputs_json, computed_json, now, project_id),
            )
        else:
            conn.execute(
                """UPDATE projects SET project_key=?, display_name=?, doc_number=?, notes=?,
                   schema_version=?, inputs_json=?, computed_json=?, updated_at=?
                   WHERE id=?""",
                (key, display, doc_number, notes, schema_version, inputs_json, computed_json, now, project_id),
            )
        conn.commit()
        return {"id": project_id, "project_key": key, "created": False, "updated_at": now}
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
        try:
            from engine import logger as _log

            _log.log_db_project_load(str(row["project_key"]))
        except Exception:
            pass
        document = _pio.json_to_inputs(row["inputs_json"])
        inputs = _pio.engine_inputs_dict(document)
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
            "document": document,
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


def delete_project(db_path: str, project_id: int) -> None:
    """Delete a project and its snapshots/scenarios (FK cascade)."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise KeyError("project not found")
    finally:
        conn.close()


def update_project_notes(db_path: str, project_id: int, notes: str) -> None:
    init_db(db_path)
    now = _utc_now()
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE projects SET notes = ?, updated_at = ? WHERE id = ?",
            (notes, now, project_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise KeyError("project not found")
    finally:
        conn.close()


def ensure_default_case(db_path: str, project_id: int) -> int:
    """Return default case id for a project, creating ``Main`` if needed."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM cases WHERE project_id = ? AND is_default = 1",
            (project_id,),
        ).fetchone()
        if row is not None:
            return int(row["id"])
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if proj is None:
            raise KeyError("project not found")
        now = _utc_now()
        conn.execute(
            """INSERT INTO cases (project_id, case_name, description, is_default, created_at, updated_at)
               VALUES (?,?,?,1,?,?)""",
            (project_id, "Main", "", now, now),
        )
        conn.commit()
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        conn.close()


def list_cases(db_path: str, project_id: int) -> list[dict[str, Any]]:
    init_db(db_path)
    ensure_default_case(db_path, project_id)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            """SELECT id, project_id, case_name, description, is_default, created_at, updated_at
               FROM cases WHERE project_id = ?
               ORDER BY is_default DESC, case_name ASC""",
            (project_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_case(
    db_path: str,
    project_id: int,
    case_name: str,
    *,
    description: str = "",
) -> dict[str, Any]:
    init_db(db_path)
    name = (case_name or "").strip()
    if not name:
        raise ValueError("case_name required")
    now = _utc_now()
    conn = _connect(db_path)
    try:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if proj is None:
            raise KeyError("project not found")
        conn.execute(
            """INSERT INTO cases (project_id, case_name, description, is_default, created_at, updated_at)
               VALUES (?,?,?,0,?,?)""",
            (project_id, name, description, now, now),
        )
        conn.commit()
        cid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {"id": cid, "project_id": project_id, "case_name": name, "created_at": now}
    finally:
        conn.close()


def save_revision(
    db_path: str,
    case_id: int,
    inputs: Optional[dict] = None,
    computed: Optional[dict] = None,
    *,
    label: str = "",
    notes: str = "",
    revision_code: str = "",
    parent_revision_id: Optional[int] = None,
    ui_session_overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append a revision under a case (B3)."""
    from engine.project_revisions import revision_report_hash

    init_db(db_path)
    now = _utc_now()
    inputs_json = (
        _pio.inputs_to_json(inputs, ui_session_overrides=ui_session_overrides)
        if inputs is not None
        else None
    )
    computed_json = _serialize_computed(computed)
    rh = revision_report_hash(inputs, computed) if inputs is not None else ""
    code = (revision_code or "").strip()
    if not code and inputs is not None:
        code = str(inputs.get("revision") or "")

    conn = _connect(db_path)
    try:
        case = conn.execute("SELECT id, project_id FROM cases WHERE id = ?", (case_id,)).fetchone()
        if case is None:
            raise KeyError("case not found")
        conn.execute(
            """INSERT INTO revisions (
                   case_id, revision_code, label, notes, report_hash,
                   inputs_json, computed_json, parent_revision_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                case_id,
                code,
                label,
                notes,
                rh,
                inputs_json,
                computed_json,
                parent_revision_id,
                now,
            ),
        )
        conn.commit()
        rid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {
            "id": rid,
            "case_id": case_id,
            "project_id": int(case["project_id"]),
            "report_hash": rh,
            "revision_code": code,
            "created_at": now,
        }
    finally:
        conn.close()


def list_revisions(
    db_path: str,
    case_id: int,
    *,
    metadata_only: bool = True,
) -> list[dict[str, Any]]:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        if metadata_only:
            cur = conn.execute(
                """SELECT id, case_id, revision_code, label, notes, report_hash,
                          inputs_json, computed_json, parent_revision_id, created_at
                   FROM revisions WHERE case_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (case_id,),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM revisions WHERE case_id = ? ORDER BY created_at DESC, id DESC",
                (case_id,),
            )
        rows = []
        for r in cur.fetchall():
            row = {
                "id": int(r["id"]),
                "case_id": int(r["case_id"]),
                "revision_code": r["revision_code"],
                "label": r["label"],
                "notes": r["notes"],
                "report_hash": r["report_hash"],
                "created_at": r["created_at"],
                "parent_revision_id": r["parent_revision_id"],
                "has_inputs": r["inputs_json"] is not None,
                "has_computed": r["computed_json"] is not None,
            }
            if not metadata_only:
                row["inputs_json"] = r["inputs_json"]
                row["computed_json"] = r["computed_json"]
            rows.append(row)
        return rows
    finally:
        conn.close()


def load_revision(db_path: str, revision_id: int) -> dict[str, Any]:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        r = conn.execute(
            """SELECT r.*, c.project_id
               FROM revisions r
               JOIN cases c ON c.id = r.case_id
               WHERE r.id = ?""",
            (revision_id,),
        ).fetchone()
        if r is None:
            raise KeyError("revision not found")
        out: dict[str, Any] = {
            "id": int(r["id"]),
            "case_id": int(r["case_id"]),
            "project_id": int(r["project_id"]),
            "revision_code": r["revision_code"],
            "label": r["label"],
            "notes": r["notes"],
            "report_hash": r["report_hash"],
            "created_at": r["created_at"],
            "parent_revision_id": r["parent_revision_id"],
            "inputs": None,
            "computed": None,
        }
        if r["inputs_json"]:
            document = _pio.json_to_inputs(r["inputs_json"])
            out["document"] = document
            out["inputs"] = _pio.engine_inputs_dict(document)
        if r["computed_json"]:
            out["computed"] = json.loads(r["computed_json"])
        return out
    finally:
        conn.close()


def diff_revisions(db_path: str, revision_id_a: int, revision_id_b: int) -> dict[str, Any]:
    from engine.project_revisions import diff_revision_inputs, diff_revision_summary

    a = load_revision(db_path, revision_id_a)
    b = load_revision(db_path, revision_id_b)
    if a.get("inputs") is None or b.get("inputs") is None:
        raise ValueError("Both revisions must include inputs for diff")
    rows = diff_revision_inputs(a["inputs"], b["inputs"])
    return {
        "revision_a": revision_id_a,
        "revision_b": revision_id_b,
        "report_hash_a": a.get("report_hash"),
        "report_hash_b": b.get("report_hash"),
        "rows": rows,
        "summary": diff_revision_summary(rows),
    }


def save_snapshot(
    db_path: str,
    project_id: int,
    inputs: Optional[dict] = None,
    computed: Optional[dict] = None,
    *,
    label: str = "",
    notes: str = "",
    ui_session_overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append a history snapshot (legacy table) and matching case revision (B3)."""
    init_db(db_path)
    now = _utc_now()
    inputs_json = (
        _pio.inputs_to_json(inputs, ui_session_overrides=ui_session_overrides)
        if inputs is not None
        else None
    )
    computed_json = _serialize_computed(computed)
    case_id = ensure_default_case(db_path, project_id)
    rev = save_revision(
        db_path,
        case_id,
        inputs=inputs,
        computed=computed,
        label=label,
        notes=notes,
        ui_session_overrides=ui_session_overrides,
    )
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO snapshots (project_id, label, notes, inputs_json, computed_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (project_id, label, notes, inputs_json, computed_json, now),
        )
        conn.commit()
        sid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {
            "id": rev["id"],
            "snapshot_id": sid,
            "project_id": project_id,
            "case_id": case_id,
            "report_hash": rev.get("report_hash"),
            "created_at": now,
        }
    finally:
        conn.close()


def project_history(db_path: str, project_id: int) -> list[dict[str, Any]]:
    """List revisions for the project's default case (newest first)."""
    init_db(db_path)
    conn = _connect(db_path)
    try:
        if conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            return []
    finally:
        conn.close()
    case_id = ensure_default_case(db_path, project_id)
    revs = list_revisions(db_path, case_id, metadata_only=True)
    if revs:
        return [
            {
                "id": r["id"],
                "project_id": project_id,
                "case_id": case_id,
                "label": r["label"],
                "notes": r["notes"],
                "revision_code": r.get("revision_code", ""),
                "report_hash": r.get("report_hash", ""),
                "created_at": r["created_at"],
                "has_inputs": r["has_inputs"],
                "has_computed": r["has_computed"],
            }
            for r in revs
        ]
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
                    "revision_code": "",
                    "report_hash": "",
                    "created_at": r["created_at"],
                    "has_inputs": r["inputs_json"] is not None,
                    "has_computed": r["computed_json"] is not None,
                }
            )
        return rows
    finally:
        conn.close()


def load_snapshot(db_path: str, snapshot_id: int) -> dict[str, Any]:
    """Load revision by id (B3); falls back to legacy ``snapshots`` table."""
    init_db(db_path)
    try:
        return load_revision(db_path, snapshot_id)
    except KeyError:
        pass
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
            document = _pio.json_to_inputs(r["inputs_json"])
            out["document"] = document
            out["inputs"] = _pio.engine_inputs_dict(document)
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
    "update_project_by_id",
    "load_project",
    "list_projects",
    "delete_project",
    "update_project_notes",
    "ensure_default_case",
    "list_cases",
    "create_case",
    "save_revision",
    "list_revisions",
    "load_revision",
    "diff_revisions",
    "save_snapshot",
    "project_history",
    "load_snapshot",
    "save_scenario",
    "list_scenarios",
]
