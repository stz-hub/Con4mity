"""
Con4mity — backend FastAPI (CT 103).

- API sous le préfixe /api (pour ne pas entrer en conflit avec le front statique sur /).
- Front : dossier ../frontend ou variable FRONTEND_DIR.

En local : uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import psycopg2
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
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
    top_hosts = [{"host": h, "count": c} for h, c in hosts.most_common(8) if h != "—"]
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


# ---------- Schémas ----------
class LoginBody(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AlertPatch(BaseModel):
    status: str = Field(..., pattern="^(new|in_progress|resolved)$")


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
    size: int = Query(100, ge=1, le=400),
):
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
    body: dict[str, Any] = {
        "query": {"bool": {"must": must, "filter": filter_q}},
        "size": size,
        "sort": [
            {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
            {"received_at": {"order": "desc", "unmapped_type": "date"}},
        ],
    }
    try:
        response = os_client.search(index="con4mity-logs-*", body=body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenSearch error: {e}") from e

    hits = response.get("hits", {}).get("hits", [])
    sources = [h.get("_source") or {} for h in hits]
    return [ui_envelope(s) for s in sources]


@api.get("/alerts")
def get_alerts(user: dict = Depends(require_user)):
    conn = pg_connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, created_at, rule_name, severity, host, description, status, log_ids
                FROM alerts
                ORDER BY created_at DESC NULLS LAST
                LIMIT 100
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return jsonable_encoder(rows)


@api.get("/stats")
def get_stats(user: dict = Depends(require_user)):
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

    return {
        "new_alerts": int(row[0] or 0),
        "in_progress_alerts": int(row[1] or 0),
        "resolved_alerts": int(row[2] or 0),
        "total_alerts": int(row[3] or 0),
        "incidents_open": int(row[4] or 0),
        "critical_open": int(row[5] or 0),
    }


@api.get("/overview")
def get_overview(user: dict = Depends(require_user)):
    """Vue synthétique : stats PG + agrégations légères sur un échantillon de logs (Pi-friendly)."""
    stats = get_stats(user)  # type: ignore[arg-type]
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
        response = os_client.search(index="con4mity-logs-*", body=body)
        hits = response.get("hits", {}).get("hits", [])
        docs = [h.get("_source") or {} for h in hits]
    except Exception:
        docs = []

    timeline, top_hosts = _aggregate_logs_overview(docs, hours=24)
    events_24h = len(docs)
    recent_rate = sum(b["count"] for b in timeline[-3:]) if timeline else 0
    top_source_ips = aggregate_top_ips(docs, limit=8)

    return {
        "stats": stats,
        "timeline": timeline,
        "top_hosts": top_hosts,
        "top_source_ips": top_source_ips,
        "events_sampled": events_24h,
        "activity_recent_count": recent_rate,
        "map_hint": "top_hosts",
    }


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
    conn = pg_connect()
    try:
        with conn.cursor() as cur:
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
                detail="Column updated_at missing — run SQL migration on alerts table.",
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        conn.close()

    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")

    uname = str(user.get("sub") or "operator")
    _log_operator_activity(
        uname,
        "alert_status",
        f"alert #{alert_id} → {body.status}",
    )

    return {"id": alert_id, "status": body.status}


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
