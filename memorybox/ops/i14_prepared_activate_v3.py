"""Guarded activation of the existing unpublished v3 generation.

Reads the v3 generation id from the private JSON. Calls
comms_prepared_assert_generation_ready then
comms_prepared_activate_generation exactly once. Does not use the 038
first-generation activator. Does not load, delete, or rewrite rows.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import assert_counts_only, failure_json

CONFIRM = "activate-unpublished-v3-retain-v1-v2"
PRIVATE_PATH = Path(r"E:\MemoryBox-backups\i14-040-v3-private.json")
V1 = "i14-prepared-email-v1"
V2 = "i14-prepared-email-v2"
V3 = "i14-prepared-email-v3"
CHILD = {"threads": 40996, "messages": 91247, "participants": 294061, "attachments": 28467}
ARCHIVE = {"evidence": 188656, "sources": 27, "communication_rfc_ids": 287010}
DISP = {
    "authored_displayable": 90001,
    "non_substantive": 169,
    "correctly_empty": 323,
    "attachment_only": 695,
    "prepared_text_unavailable": 59,
    "uncertain": 0,
}
VOICE = {"Tom": 11578, "Peggy": 1345, "Sue": 210}


class ActivateV3Error(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def require_flags() -> None:
    if not _env_on("MEMORYBOX_I14_ACTIVATE_ALLOW_FLIGHTSIM"):
        raise ActivateV3Error("activate_flightsim_not_allowed")
    if not _env_on("MEMORYBOX_I14_ACTIVATE_ALLOW_MEMORYBOX_DB"):
        raise ActivateV3Error("activate_memorybox_db_not_allowed")
    if os.environ.get("MEMORYBOX_I14_ACTIVATE_CONFIRM", "").strip() != CONFIRM:
        raise ActivateV3Error("activate_confirm_mismatch")


def _n(conn: Any, sql: str, params: tuple | None = None) -> int:
    row = conn.execute(sql, params).fetchone() if params else conn.execute(sql).fetchone()
    return int(row["n"])


def _child(conn: Any, gid: Any) -> dict[str, int]:
    return {
        "threads": _n(
            conn,
            "SELECT COUNT(*) AS n FROM comms_prepared_threads WHERE generation_id = %s",
            (gid,),
        ),
        "messages": _n(
            conn,
            "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
            (gid,),
        ),
        "participants": _n(
            conn,
            """
            SELECT COUNT(*) AS n FROM comms_prepared_participants p
              JOIN comms_prepared_messages m ON m.id = p.message_id
             WHERE m.generation_id = %s
            """,
            (gid,),
        ),
        "attachments": _n(
            conn,
            """
            SELECT COUNT(*) AS n FROM comms_prepared_attachments a
              JOIN comms_prepared_messages m ON m.id = a.message_id
             WHERE m.generation_id = %s
            """,
            (gid,),
        ),
    }


def _agree(actual: dict[str, int], expected: dict[str, int], code: str) -> None:
    diffs = [f"{k}:{actual.get(k)}!={v}" for k, v in expected.items() if int(actual.get(k) or 0) != v]
    if diffs:
        raise ActivateV3Error(code + ":" + ",".join(diffs))


def load_v3_id() -> UUID:
    raw = json.loads(PRIVATE_PATH.read_text(encoding="utf-8"))
    return UUID(str(raw["generation_id"]))


def precheck(conn: Any, v3: UUID) -> dict[str, Any]:
    ledger = list(conn.execute("SELECT version, filename FROM schema_migrations ORDER BY version").fetchall())
    if len(ledger) != 40 or str(ledger[-1]["filename"]) != "040_p2_i14_voice_requires_displayable_authored.sql":
        raise ActivateV3Error("ledger_not_001_040")
    gens = list(
        conn.execute(
            """
            SELECT id, algo_version, status, published, is_active
              FROM comms_prepared_generations ORDER BY created_at
            """
        ).fetchall()
    )
    if len(gens) != 3:
        raise ActivateV3Error("generation_count_unexpected")
    by_algo = {str(g["algo_version"]): g for g in gens}
    if set(by_algo) != {V1, V2, V3}:
        raise ActivateV3Error("algo_set_unexpected")
    v1, v2, target = by_algo[V1], by_algo[V2], by_algo[V3]
    if target["id"] != v3:
        raise ActivateV3Error("v3_id_mismatch_private_file")
    if not (v1["published"] and v1["is_active"] and str(v1["status"]) == "published"):
        raise ActivateV3Error("v1_not_sole_active")
    if v2["published"] or v2["is_active"] or str(v2["status"]) != "validated":
        raise ActivateV3Error("v2_state_unexpected")
    if target["published"] or target["is_active"] or str(target["status"]) != "validated":
        raise ActivateV3Error("v3_state_unexpected")
    failed = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE status IN ('failed','building')")
    if failed:
        raise ActivateV3Error("failed_or_building_present")
    published_n = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE published")
    active_n = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_active_generations")
    if published_n != 1 or active_n != 1:
        raise ActivateV3Error("published_or_active_count_unexpected")
    _agree(_child(conn, v3), CHILD, "v3_child_mismatch")
    null_disp = _n(
        conn,
        """
        SELECT COUNT(*) AS n FROM comms_prepared_messages
         WHERE generation_id = %s
           AND (prepared_text_disposition IS NULL OR prepared_text_disposition = 'legacy')
        """,
        (v3,),
    )
    if null_disp:
        raise ActivateV3Error("v3_disposition_incomplete")
    blank_voice = _n(
        conn,
        """
        SELECT COUNT(*) AS n FROM comms_prepared_messages
         WHERE generation_id = %s AND voice_corpus
           AND length(btrim(COALESCE(cleaned_authored_text,''))) = 0
        """,
        (v3,),
    )
    if blank_voice:
        raise ActivateV3Error("blank_voice_present")
    forbidden = _n(
        conn,
        """
        SELECT COUNT(*) AS n FROM comms_prepared_messages
         WHERE generation_id = %s AND voice_corpus
           AND prepared_text_disposition IS DISTINCT FROM 'authored_displayable'
        """,
        (v3,),
    )
    if forbidden:
        raise ActivateV3Error("forbidden_disposition_and_voice")
    disp = {
        str(r["d"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT COALESCE(prepared_text_disposition,'<NULL>') AS d, COUNT(*)::int AS n
              FROM comms_prepared_messages WHERE generation_id = %s GROUP BY 1
            """,
            (v3,),
        ).fetchall()
    }
    _agree({k: int(disp.get(k, 0)) for k in DISP}, DISP, "v3_disposition_mismatch")
    archive = {
        "evidence": _n(conn, "SELECT COUNT(*) AS n FROM evidence"),
        "sources": _n(conn, "SELECT COUNT(*) AS n FROM sources"),
        "communication_rfc_ids": _n(conn, "SELECT COUNT(*) AS n FROM communication_rfc_ids"),
    }
    _agree(archive, ARCHIVE, "archive_baseline_mismatch")
    return {"v1": str(v1["id"]), "v2": str(v2["id"]), "v3": str(v3)}


def postcheck(conn: Any, v3: UUID) -> dict[str, Any]:
    gens = list(
        conn.execute(
            """
            SELECT id, algo_version, status, published, is_active
              FROM comms_prepared_generations ORDER BY created_at
            """
        ).fetchall()
    )
    by = {str(g["algo_version"]): g for g in gens}
    v1, v2, t = by[V1], by[V2], by[V3]
    if not (t["published"] and t["is_active"] and str(t["status"]) == "published"):
        raise ActivateV3Error("v3_not_sole_active")
    if v1["is_active"] or v1["published"] or str(v1["status"]) != "superseded":
        raise ActivateV3Error("v1_not_superseded")
    if v2["published"] or v2["is_active"] or str(v2["status"]) != "validated":
        raise ActivateV3Error("v2_changed")
    if _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE published") != 1:
        raise ActivateV3Error("published_not_one")
    if _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_active_generations") != 1:
        raise ActivateV3Error("active_not_one")
    active_algo = conn.execute(
        """
        SELECT g.algo_version FROM comms_prepared_active_generations a
          JOIN comms_prepared_generations g ON g.id = a.id
        """
    ).fetchone()["algo_version"]
    if str(active_algo) != V3:
        raise ActivateV3Error("active_algo_not_v3")
    if _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE status IN ('failed','building')"):
        raise ActivateV3Error("failed_or_building_present")
    _agree(_child(conn, v3), CHILD, "v3_child_mismatch")
    _agree(_child(conn, by[V1]["id"]), CHILD, "v1_child_mismatch")
    _agree(_child(conn, by[V2]["id"]), CHILD, "v2_child_mismatch")
    disp = {
        str(r["d"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT COALESCE(prepared_text_disposition,'<NULL>') AS d, COUNT(*)::int AS n
              FROM comms_prepared_messages WHERE generation_id = %s GROUP BY 1
            """,
            (v3,),
        ).fetchall()
    }
    _agree({k: int(disp.get(k, 0)) for k in DISP}, DISP, "v3_disposition_mismatch")
    voice = {
        str(r["who"]): int(r["n"])
        for r in conn.execute(
            """
            SELECT split_part(pe.display_name, ' ', 1) AS who, COUNT(*)::int AS n
              FROM comms_prepared_messages m
              JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
              JOIN people pe ON pe.id = p.person_id
             WHERE m.generation_id = %s AND m.voice_corpus
             GROUP BY 1
            """,
            (v3,),
        ).fetchall()
    }
    _agree({k: int(voice.get(k, 0)) for k in VOICE}, VOICE, "voice_mismatch")
    archive = {
        "evidence": _n(conn, "SELECT COUNT(*) AS n FROM evidence"),
        "sources": _n(conn, "SELECT COUNT(*) AS n FROM sources"),
        "communication_rfc_ids": _n(conn, "SELECT COUNT(*) AS n FROM communication_rfc_ids"),
    }
    _agree(archive, ARCHIVE, "archive_baseline_mismatch")
    return {
        "generations": [
            {
                "algo_version": g["algo_version"],
                "status": g["status"],
                "published": bool(g["published"]),
                "is_active": bool(g["is_active"]),
            }
            for g in gens
        ],
        "child": CHILD,
        "dispositions": DISP,
        "voice": VOICE,
        "archive": archive,
        "commercial": {
            str(r["k"]): int(r["n"])
            for r in conn.execute(
                """
                SELECT commercial_class AS k, COUNT(*)::int AS n
                  FROM comms_prepared_messages WHERE generation_id = %s GROUP BY 1
                """,
                (v3,),
            ).fetchall()
        },
        "quote": {
            str(r["k"]): int(r["n"])
            for r in conn.execute(
                """
                SELECT quote_quality AS k, COUNT(*)::int AS n
                  FROM comms_prepared_messages WHERE generation_id = %s GROUP BY 1
                """,
                (v3,),
            ).fetchall()
        },
    }


def run(conn: Any) -> dict[str, Any]:
    v3 = load_v3_id()
    precheck(conn, v3)
    conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (v3,))
    conn.execute("SELECT comms_prepared_activate_generation(%s)", (v3,))
    proof = postcheck(conn, v3)
    public = {
        "ok": True,
        "kind": "household_email_v3_activation",
        "activation_called": True,
        "algo_version": V3,
        "v1_retained_superseded": True,
        "v2_still_unpublished": True,
        **proof,
    }
    assert_counts_only(public)
    return public


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        require_flags()
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise ActivateV3Error("MEMORYBOX_DATABASE_URL_missing")
        try:
            refuse_live_dsn(dsn, None, allow_flightsim=True)
        except ProductionDSNError as exc:
            raise ActivateV3Error(str(exc)) from None
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=10) as conn:
            public = run(conn)
            conn.commit()
        print(json.dumps(public, indent=2, sort_keys=True))
        return 0
    except ActivateV3Error as exc:
        print(json.dumps(failure_json(str(exc))))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
