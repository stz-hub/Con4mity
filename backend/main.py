"""
Con4mity — backend FastAPI (CT 103).

- API sous le préfixe /api (pour ne pas entrer en conflit avec le front statique sur /).
- Front : dossier ../frontend ou variable FRONTEND_DIR.

En local : uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import bcrypt
import psycopg2
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from opensearchpy import OpenSearch
from psycopg2 import errors as pg_errors
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from log_normalization import (
    aggregate_top_ips,
    pick_host,
    pick_timestamp_raw,
    ui_envelope,
)

# --- Config ---
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-dev-only")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

PG_HOST = os.getenv("PG_HOST", "192.168.0.104")
PG_NAME = os.getenv("PG_NAME", "con4mity")
PG_USER = os.getenv("PG_USER", "con4mity")
PG_PASSWORD = os.getenv("PG_PASSWORD", "Con4mity2024")

OS_HOST = os.getenv("OS_HOST", "192.168.0.101")
OS_PORT = int(os.getenv("OS_PORT", "9200"))

# Fichier touché périodiquement par l’hôte (optionnel) — sinon statut filebeat: unknown
FILEBEAT_HEARTBEAT_FILE = os.getenv("FILEBEAT_HEARTBEAT_FILE", "")

OS_LOGS_INDEX = os.getenv("OS_LOGS_INDEX", "con4mity-logs-*")

_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_FRONT = _BACKEND_DIR.parent / "frontend"
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(_DEFAULT_FRONT)))

security = HTTPBearer(auto_error=False)

app = FastAPI(title="Con4mity API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os_client = OpenSearch(
    hosts=[{"host": OS_HOST, "port": OS_PORT}],
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

api = APIRouter(prefix="/api")


def pg_connect():
    return psycopg2.connect(
        host=PG_HOST,
        database=PG_NAME,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def _parse_iso_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = raw.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s.replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _aggregate_logs_overview(docs: list[dict[str, Any]], hours: int = 24) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Histogramme + top hôtes à partir des documents déjà récupérés (léger pour Pi)."""
    now = datetime.now(timezone.utc)
    bucket = [0] * hours
    hosts: Counter[str] = Counter()
    for d in docs:
        hosts[pick_host(d)] += 1
        dt = _parse_iso_ts(pick_timestamp_raw(d))
        if not dt:
            continue
        delta_h = int((now - dt).total_seconds() // 3600)
        if 0 <= delta_h < hours:
            idx = hours - 1 - delta_h
            bucket[idx] += 1
    timeline: list[dict[str, Any]] = []
    for i in range(hours):
        t = now - timedelta(hours=hours - 1 - i)
        timeline.append({"label": t.strftime("%d/%m %Hh"), "count": bucket[i]})
    top_hosts = [{"host": h, "count": c} for h, c in hosts.most_common(5) if h != "—"]
    return timeline, top_hosts


def _log_operator_activity(username: str, action_key: str, detail: str | None) -> None:
    try:
        conn = pg_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO operator_activity (username, action_key, detail)
                    VALUES (%s, %s, %s)
                    """,
                    (username, action_key, detail),
                )
            conn.commit()
        finally:
            conn.close()
    except psycopg2.Error:
        pass


def _build_logs_query_body(
    q: str | None,
    host: str | None,
    event_type: str | None,
    from_ts: str | None,
    to_ts: str | None,
    user_name: str | None,
) -> tuple[list[Any], list[Any]]:
    must: list[Any] = []
    filter_q: list[Any] = []
    if q and q.strip():
        must.append(
            {
                "simple_query_string": {
                    "query": q.strip(),
                    "fields": [
                        "message^2",
                        "raw_message",
                        "log^1.5",
                        "host.name",
                        "event.original",
                        "user.name",
                        "user.id",
                    ],
                    "default_operator": "and",
                }
            }
        )
    if host and host.strip():
        h = host.strip()
        host_should: list[dict[str, Any]] = [
            {"wildcard": {"host.name": f"*{h}*"}},
            {"match_phrase": {"host.name": h}},
        ]
        if len(h) >= 2:
            host_should.append({"wildcard": {"log": f"*{h}*"}})
            host_should.append({"wildcard": {"message": f"*{h}*"}})
            host_should.append({"wildcard": {"raw_message": f"*{h}*"}})
        filter_q.append({"bool": {"should": host_should, "minimum_should_match": 1}})
    if event_type and event_type.strip():
        et = event_type.strip()
        filter_q.append(
            {
                "bool": {
                    "should": [
                        {"term": {"event.type.keyword": et}},
                        {"match": {"event.type": {"query": et, "operator": "and"}}},
                        {"term": {"event.category.keyword": et}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    if user_name and user_name.strip():
        un = user_name.strip()
        filter_q.append(
            {
                "bool": {
                    "should": [
                        {"wildcard": {"user.name": f"*{un}*"}},
                        {"wildcard": {"user.id": f"*{un}*"}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    if from_ts or to_ts:
        rng: dict[str, Any] = {}
        if from_ts:
            rng["gte"] = from_ts
        if to_ts:
            rng["lte"] = to_ts
        filter_q.append({"range": {"@timestamp": rng}})
    if not must:
        must.append({"match_all": {}})
    return must, filter_q


def _parse_log_ids_field(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x is not None and str(x).strip() != ""]
    if isinstance(raw, str) and raw.strip():
        try:
            j = json.loads(raw)
            if isinstance(j, list):
                return [str(x) for x in j if x is not None and str(x).strip() != ""]
        except (json.JSONDecodeError, TypeError, ValueError):
            return [raw.strip()]
    if isinstance(raw, (dict,)):
        v = raw.get("ids") or raw.get("log_ids")
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
    return []


def _os_cluster_services() -> dict[str, Any]:
    return {
        "opensearch": _check_opensearch(),
        "postgresql": _check_postgres(),
        "filebeat": _check_filebeat(),
    }


def _check_opensearch() -> dict[str, Any]:
    try:
        h = os_client.cluster.health(request_timeout=5)
        return {
            "ok": True,
            "status": h.get("status", "unknown"),
            "cluster_name": h.get("cluster_name"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_postgres() -> dict[str, Any]:
    try:
        conn = pg_connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _check_filebeat() -> dict[str, Any]:
    if not FILEBEAT_HEARTBEAT_FILE:
        return {"ok": None, "detail": "not_configured"}
    p = Path(FILEBEAT_HEARTBEAT_FILE)
    try:
        if not p.is_file():
            return {"ok": False, "detail": "file_missing"}
        age = time.time() - p.stat().st_mtime
        return {"ok": age < 600, "age_seconds": int(age)}
    except OSError as e:
        return {"ok": False, "error": str(e)[:120]}


def _stats_from_db() -> dict[str, Any]:
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'new') AS new_alerts,
                    COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_alerts,
                    COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_alerts,
                    COUNT(*) AS total_alerts,
                    COUNT(*) FILTER (
                        WHERE status IN ('new', 'in_progress')
                    ) AS incidents_open,
                    COUNT(*) FILTER (
                        WHERE LOWER(COALESCE(severity, '')) = 'critical'
                        AND status IN ('new', 'in_progress')
                    ) AS critical_open
                FROM alerts
                """
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {
            "new_alerts": 0,
            "in_progress_alerts": 0,
            "resolved_alerts": 0,
            "total_alerts": 0,
            "incidents_open": 0,
            "critical_open": 0,
        }
    return {
        "new_alerts": int(row[0] or 0),
        "in_progress_alerts": int(row[1] or 0),
        "resolved_alerts": int(row[2] or 0),
        "total_alerts": int(row[3] or 0),
        "incidents_open": int(row[4] or 0),
        "critical_open": int(row[5] or 0),
    }


def _top_alert_rules_from_db(limit: int = 5) -> list[dict[str, Any]]:
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(rule_name, '—') AS rule_name, COUNT(*)::int AS c
                FROM alerts
                WHERE created_at >= NOW() - INTERVAL '30 days'
                GROUP BY 1
                ORDER BY c DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [{"rule": (r[0] or "—")[:200], "count": r[1]} for r in rows or []]


def _opensearch_volume_24h() -> list[dict[str, Any]]:
    try:
        body: dict[str, Any] = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": "now-24h",
                                    "lte": "now",
                                }
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "by_hour": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "1h",
                        "min_doc_count": 0,
                    }
                }
            },
        }
        r = os_client.search(index=OS_LOGS_INDEX, body=body)
    except Exception:
        try:
            body = {
                "size": 0,
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "range": {
                                    "received_at": {
                                        "gte": "now-24h",
                                        "lte": "now",
                                    }
                                }
                            }
                        ]
                    }
                },
                "aggs": {
                    "by_hour": {
                        "date_histogram": {
                            "field": "received_at",
                            "fixed_interval": "1h",
                            "min_doc_count": 0,
                        }
                    }
                },
            }
            r = os_client.search(index=OS_LOGS_INDEX, body=body)
        except Exception:
            return []
    buckets = (r.get("aggregations") or {}).get("by_hour", {}).get("buckets") or []
    out: list[dict[str, Any]] = []
    for b in buckets:
        out.append(
            {
                "key": b.get("key"),
                "key_as_string": b.get("key_as_string") or "",
                "count": int(b.get("doc_count", 0) or 0),
            }
        )
    return out


# ---------- Schémas ----------
class LoginBody(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AlertPatch(BaseModel):
    status: str = Field(..., pattern="^(new|in_progress|resolved)$")
    comment: str | None = Field(None, max_length=2000)


class ActivityIn(BaseModel):
    action_key: str = Field(..., max_length=120)
    detail: str | None = Field(None, max_length=2000)


# ---------- Auth ----------
def create_token(sub: str, role: str | None) -> str:
    """python-jose attend surtout des timestamps numériques pour iat/exp."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRE_HOURS)
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role or "",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


async def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        return decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ---------- Routes API ----------
@api.get("/health")
def api_health():
    return {"status": "Con4mity backend OK", "frontend": str(FRONTEND_DIR)}


@api.post("/login", response_model=TokenOut)
def login(body: LoginBody):
    conn = pg_connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = %s",
                (body.username,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    stored_hash = (row.get("password_hash") or "").strip()
    if not stored_hash:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has empty password_hash",
        )
    try:
        ok = bcrypt.checkpw(
            body.password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password hash invalid: {e}",
        ) from e

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_token(sub=row["username"], role=row.get("role"))
    return TokenOut(access_token=token)


@api.get("/logs")
def get_logs(
    user: dict = Depends(require_user),
    q: str | None = None,
    host: str | None = None,
    event_type: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    user_name: str | None = None,
    source: str | None = None,
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(50, ge=1, le=200),
    size: int | None = Query(None),
):
    """
    Paginated logs. Paramètre legacy `size` (sans pagination) : si fourni, ignore page/page_size
    et renvoie une liste (comportement ancien) pour rétrocompat.
    """
    must, filter_q = _build_logs_query_body(q, host, event_type, from_ts, to_ts, user_name)
    sc = (source or "").strip().lower() or None
    if sc in ("all", "any", ""):
        sc = None
    if sc and sc not in ("linux", "windows", "switch", "network", "other"):
        raise HTTPException(
            status_code=400,
            detail="source must be one of: linux, windows, switch, network, other",
        )

    legacy = size is not None
    if legacy:
        ps = min(max(1, int(size)), 400)
        pg = 1
    else:
        ps = page_size
        pg = page

    pool_cap = 2500
    if sc:
        body: dict[str, Any] = {
            "query": {"bool": {"must": must, "filter": filter_q}},
            "size": min(pool_cap, 2500),
            "from": 0,
            "sort": [
                {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
                {"received_at": {"order": "desc", "unmapped_type": "date"}},
            ],
        }
    else:
        from_idx = (pg - 1) * ps
        body = {
            "query": {"bool": {"must": must, "filter": filter_q}},
            "size": ps,
            "from": from_idx,
            "track_total_hits": True,
            "sort": [
                {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
                {"received_at": {"order": "desc", "unmapped_type": "date"}},
            ],
        }
    try:
        response = os_client.search(index=OS_LOGS_INDEX, body=body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenSearch error: {e}") from e

    hits = response.get("hits", {}).get("hits", [])
    sources = [h.get("_source") or {} for h in hits]
    mapped = [ui_envelope(s) for s in sources]

    if sc:
        filtered = [m for m in mapped if m.get("con4mity_ui_source") == sc]
        start = (pg - 1) * ps
        end = start + ps
        page_rows = filtered[start:end]
        total = len(filtered)
        if legacy:
            return page_rows
        return {
            "items": page_rows,
            "total": total,
            "page": pg,
            "page_size": ps,
        }

    total_h = response.get("hits", {}).get("total", 0)
    if isinstance(total_h, dict):
        tcount = int(total_h.get("value", 0) or 0)
    else:
        tcount = int(total_h or 0)
    if legacy:
        return mapped
    return {"items": mapped, "total": tcount, "page": pg, "page_size": ps}


@api.get("/logs/volume-24h")
def get_logs_volume_24h(user: dict = Depends(require_user)) -> list[dict[str, Any]]:
    return _opensearch_volume_24h()


@api.get("/logs/export.csv")
def export_logs_csv(
    user: dict = Depends(require_user),
    q: str | None = None,
    host: str | None = None,
    event_type: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    user_name: str | None = None,
    source: str | None = None,
    limit: int = Query(5000, ge=1, le=10_000),
):
    must, filter_q = _build_logs_query_body(q, host, event_type, from_ts, to_ts, user_name)
    sc = (source or "").strip().lower() or None
    if sc in ("all", "any", ""):
        sc = None
    body = {
        "query": {"bool": {"must": must, "filter": filter_q}},
        "size": min(limit, 10_000),
        "from": 0,
        "sort": [
            {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
            {"received_at": {"order": "desc", "unmapped_type": "date"}},
        ],
    }
    try:
        response = os_client.search(index=OS_LOGS_INDEX, body=body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenSearch error: {e}") from e
    hits = response.get("hits", {}).get("hits", [])
    sources = [h.get("_source") or {} for h in hits]
    rows = [ui_envelope(s) for s in sources]
    if sc and sc in ("linux", "windows", "switch", "network", "other"):
        rows = [r for r in rows if r.get("con4mity_ui_source") == sc]

    def gen() -> Any:
        output = io.StringIO()
        w = csv.writer(output)
        w.writerow(["timestamp", "host", "severity", "source", "message"])
        for r in rows:
            w.writerow(
                [
                    r.get("con4mity_ui_timestamp") or r.get("@timestamp") or "",
                    r.get("con4mity_ui_host") or "",
                    r.get("con4mity_ui_severity") or "",
                    r.get("con4mity_ui_source") or "",
                    (r.get("con4mity_ui_message") or "")[:8000],
                ]
            )
        yield output.getvalue()

    return StreamingResponse(
        gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="con4mity-logs.csv"'},
    )


def _alerts_list_query() -> str:
    return """
        SELECT
            id, created_at, rule_name, severity, host, description, status, log_ids,
            COALESCE(status_note, '') AS status_note,
            COALESCE(last_actor, '') AS last_actor,
            updated_at
        FROM alerts
        ORDER BY created_at DESC NULLS LAST
        LIMIT 200
    """


@api.get("/alerts")
def get_alerts(user: dict = Depends(require_user)):
    conn = pg_connect()
    try:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(_alerts_list_query())
                rows = cur.fetchall()
        except pg_errors.UndefinedColumn:
            conn.rollback()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, created_at, rule_name, severity, host, description, status, log_ids, updated_at
                    FROM alerts
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT 200
                    """
                )
                rows = cur.fetchall()
    finally:
        conn.close()
    return jsonable_encoder(rows)


@api.get("/alerts/daily")
def get_alerts_daily(
    user: dict = Depends(require_user),
    days: int = Query(30, ge=1, le=90),
):
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (date_trunc('day', created_at))::date AS d,
                    COUNT(*)::int
                FROM alerts
                WHERE created_at >= (NOW() - ((%s)::int * INTERVAL '1 day'))
                GROUP BY 1
                ORDER BY 1 ASC
                """,
                (days,),
            )
            rrows = cur.fetchall()
    finally:
        conn.close()
    return [{"date": str(r[0]), "count": r[1]} for r in (rrows or [])]


@api.get("/alerts/{alert_id}")
def get_alert_detail(alert_id: int, user: dict = Depends(require_user)):
    conn = pg_connect()
    try:
        row = None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        id, created_at, rule_name, severity, host, description, status, log_ids, updated_at,
                        COALESCE(status_note, '') AS status_note, COALESCE(last_actor, '') AS last_actor
                    FROM alerts
                    WHERE id = %s
                    """,
                    (alert_id,),
                )
                row = cur.fetchone()
        except pg_errors.UndefinedColumn:
            conn.rollback()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, created_at, rule_name, severity, host, description, status, log_ids, updated_at
                    FROM alerts
                    WHERE id = %s
                    """,
                    (alert_id,),
                )
                row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    raw_ids = _parse_log_ids_field(row.get("log_ids"))
    linked: list[dict[str, Any]] = []
    if raw_ids:
        try:
            qbody = {
                "query": {"ids": {"values": raw_ids[:500]}},
                "size": min(len(raw_ids), 500),
            }
            r = os_client.search(index=OS_LOGS_INDEX, body=qbody)
            hits = r.get("hits", {}).get("hits", [])
            srcs = [h.get("_source") or {} for h in hits]
            linked = [ui_envelope(s) for s in srcs]
        except Exception:
            linked = []
    return {"alert": jsonable_encoder(row), "linked_logs": linked}


@api.get("/stats")
def get_stats(user: dict = Depends(require_user)):
    return _stats_from_db()


@api.get("/overview")
def get_overview(user: dict = Depends(require_user)):
    """Vue synthétique : stats PG + agrégations légères sur un échantillon de logs (Pi-friendly)."""
    stats = _stats_from_db()
    docs: list[dict[str, Any]] = []
    try:
        body = {
            "query": {"match_all": {}},
            "size": 500,
            "sort": [
                {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
                {"received_at": {"order": "desc", "unmapped_type": "date"}},
            ],
        }
        response = os_client.search(index=OS_LOGS_INDEX, body=body)
        hits = response.get("hits", {}).get("hits", [])
        docs = [h.get("_source") or {} for h in hits]
    except Exception:
        docs = []

    timeline, top_hosts = _aggregate_logs_overview(docs, hours=24)
    events_24h = len(docs)
    recent_rate = sum(b["count"] for b in timeline[-3:]) if timeline else 0
    top_source_ips = aggregate_top_ips(docs, limit=5)
    vol24 = _opensearch_volume_24h()
    top_rules = _top_alert_rules_from_db(5)
    return {
        "stats": stats,
        "timeline": timeline,
        "top_hosts": top_hosts,
        "top_source_ips": top_source_ips,
        "top_alert_rules": top_rules,
        "log_volume_24h": vol24,
        "services": _os_cluster_services(),
        "events_sampled": events_24h,
        "activity_recent_count": recent_rate,
        "map_hint": "top_hosts",
    }


@api.get("/sources")
def get_sources_status(user: dict = Depends(require_user)):
    """
    Hôtes vus dans OpenSearch (terms) + dernière activité — badges active / silent / down.
    """
    body: dict[str, Any] = {
        "size": 0,
        "aggs": {
            "hosts": {
                "terms": {"field": "host.name.keyword", "size": 300, "order": {"_key": "asc"}},
                "aggs": {
                    "last_seen": {"max": {"field": "@timestamp"}},
                },
            }
        },
    }
    r: dict[str, Any] = {}
    try:
        r = os_client.search(index=OS_LOGS_INDEX, body=body)
    except Exception:
        body["aggs"]["hosts"]["terms"]["field"] = "host.name"
        try:
            r = os_client.search(index=OS_LOGS_INDEX, body=body)
        except Exception:
            return {"items": []}
    buckets = (r.get("aggregations") or {}).get("hosts", {}).get("buckets") or []
    now_ms = time.time() * 1000.0
    items: list[dict[str, Any]] = []
    for b in buckets:
        name = b.get("key", "—")
        last_v = b.get("last_seen", {}).get("value")
        if last_v is None:
            badge = "down"
            last_iso: str | None = None
            age = None
        else:
            try:
                last_iso = datetime.fromtimestamp(
                    float(last_v) / 1000.0, tz=timezone.utc
                ).isoformat()
            except (OSError, ValueError, TypeError):
                last_iso = None
            try:
                age = max(0.0, (now_ms - float(last_v)) / 1000.0)
            except (TypeError, ValueError):
                age = None
            if age is not None and age < 300:
                badge = "active"
            elif age is not None and age < 3600:
                badge = "silent"
            else:
                badge = "down"
        items.append(
            {
                "host": str(name) if name is not None else "—",
                "last_seen": last_iso,
                "badge": badge,
                "age_seconds": int(age) if age is not None else None,
            }
        )
    return {"items": items}


@api.get("/activity")
def list_activity(user: dict = Depends(require_user)):
    conn = pg_connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, action_key, detail, created_at
                FROM operator_activity
                ORDER BY created_at DESC NULLS LAST
                LIMIT 50
                """
            )
            rows = list(cur.fetchall())
    except pg_errors.UndefinedTable:
        rows = []
    finally:
        conn.close()

    return jsonable_encoder(rows)


@api.post("/activity")
def post_activity(body: ActivityIn, user: dict = Depends(require_user)):
    uname = str(user.get("sub") or "operator")
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO operator_activity (username, action_key, detail)
                VALUES (%s, %s, %s)
                RETURNING id, created_at
                """,
                (uname, body.action_key[:120], body.detail),
            )
            row = cur.fetchone()
        conn.commit()
    except pg_errors.UndefinedTable:
        conn.rollback()
        raise HTTPException(
            status_code=503,
            detail="Table operator_activity absente — exécuter backend/sql/003_operator_activity.sql",
        ) from None
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()

    return {"id": row[0], "created_at": row[1]}


PLAYBOOKS_META: dict[str, dict[str, str]] = {
    "export_hint": {
        "fr": "Ouvre la page Rapports pour exporter les données visibles.",
        "en": "Open the Reports page to export visible data.",
    },
    "refresh_index_hint": {
        "fr": "Vérifie la connectivité OpenSearch et les index con4mity-logs-*.",
        "en": "Check OpenSearch connectivity and con4mity-logs-* indices.",
    },
    "notify_placeholder": {
        "fr": "Simulation : aucun email envoyé (SIEM léger).",
        "en": "Simulation: no email sent (lightweight SIEM).",
    },
    "triage_credential": {
        "fr": "Rappel de rotation des comptes à privilèges (simulation).",
        "en": "Privileged account rotation reminder (simulation).",
    },
    "isolate_host_hint": {
        "fr": "Checklist : isoler l’hôte (VLAN, pare-feu) — exécution manuelle côté réseau.",
        "en": "Checklist: isolate the host (VLAN, firewall) — run manually on the network side.",
    },
    "escalation_ticket": {
        "fr": "Créer un ticket d’escalade (Jira/GLPI) — intégration future.",
        "en": "Create an escalation ticket (Jira/GLPI) — future integration.",
    },
}


@api.get("/playbooks")
def list_playbooks(user: dict = Depends(require_user)):
    return {"items": [{"slug": k} for k in PLAYBOOKS_META]}


@api.post("/playbooks/{slug}")
def run_playbook(slug: str, user: dict = Depends(require_user)):
    if slug not in PLAYBOOKS_META:
        raise HTTPException(status_code=404, detail="Unknown playbook")
    uname = str(user.get("sub") or "operator")
    _log_operator_activity(uname, f"playbook:{slug}", PLAYBOOKS_META[slug].get("fr"))
    return {"ok": True, "slug": slug}


@api.patch("/alerts/{alert_id}")
def patch_alert(alert_id: int, body: AlertPatch, user: dict = Depends(require_user)):
    uname = str(user.get("sub") or "operator")
    cmt = (body.comment or "").strip()
    conn = pg_connect()
    updated = None
    try:
        with conn.cursor() as cur:
            try:
                if cmt:
                    cur.execute(
                        """
                        UPDATE alerts
                        SET
                            status = %s,
                            updated_at = NOW(),
                            last_actor = %s,
                            status_note = %s
                        WHERE id = %s
                        RETURNING id
                        """,
                        (body.status, uname, cmt, alert_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE alerts
                        SET
                            status = %s,
                            updated_at = NOW(),
                            last_actor = %s
                        WHERE id = %s
                        RETURNING id
                        """,
                        (body.status, uname, alert_id),
                    )
                updated = cur.fetchone()
            except pg_errors.UndefinedColumn:
                conn.rollback()
                cur.execute(
                    """
                    UPDATE alerts
                    SET status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (body.status, alert_id),
                )
                updated = cur.fetchone()
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        if getattr(e, "pgcode", None) == "42703":
            raise HTTPException(
                status_code=500,
                detail="Colonne manquante — exécuter les migrations SQL sur la table alerts.",
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()

    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")

    _log_operator_activity(
        uname,
        "alert_status",
        f"alert #{alert_id} → {body.status}" + (f" — {cmt[:200]}" if cmt else ""),
    )
    return {"id": alert_id, "status": body.status, "status_note": cmt or None, "last_actor": uname}


@api.websocket("/stream")
async def ws_event_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return
    try:
        decode_token(token)
    except JWTError:
        await websocket.close(code=4401, reason="invalid token")
        return
    loop = asyncio.get_running_loop()
    try:
        while True:
            stats, vol = await asyncio.gather(
                loop.run_in_executor(None, _stats_from_db),
                loop.run_in_executor(None, _opensearch_volume_24h),
            )
            await websocket.send_json(
                {
                    "type": "tick",
                    "t": int(time.time()),
                    "stats": stats,
                    "log_volume_24h": vol,
                }
            )
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        return


app.include_router(api)

# Front : servi en dernier pour ne pas masquer /docs, /openapi.json, /api/*
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {
            "error": "frontend directory missing",
            "expected": str(FRONTEND_DIR),
            "hint": "Set FRONTEND_DIR or place HTML/CSS/JS in ../frontend",
        }
