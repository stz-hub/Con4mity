"""
Con4mity — backend FastAPI (CT 103).

- API sous le préfixe /api (pour ne pas entrer en conflit avec le front statique sur /).
- Front : dossier ../frontend ou variable FRONTEND_DIR.

En local : uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import copy
import csv
import io
import json
import logging
import os
import time
import threading
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
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from starlette.middleware.base import BaseHTTPMiddleware
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
from security_helpers import (
    client_ip_from_request,
    generate_api_key,
    get_password_policy_from_env,
    hash_api_key,
    is_ip_in_allowlist,
    parse_ip_allowlist_env,
    validate_password_strength,
)

logger = logging.getLogger("con4mity")

# --- Config ---
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-dev-only")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
# Clés API : hachage avec pepper dédié (prod : définir API_KEY_PEPPER)
API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", JWT_SECRET)
LOGIN_MAX_FAILED = int(os.getenv("LOGIN_MAX_FAILED_PER_IP_USER", "10"))
LOGIN_RATE_WINDOW_SEC = int(os.getenv("LOGIN_RATE_WINDOW_SEC", "900"))
_login_fail_lock = threading.Lock()
_login_fail_ts: dict[str, list[float]] = {}

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_NAME = os.getenv("PG_NAME", "con4mity")
PG_USER = os.getenv("PG_USER", "con4mity")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

OS_HOST = os.getenv("OS_HOST", "localhost")
OS_PORT = int(os.getenv("OS_PORT", "9200"))

# Fichier touché périodiquement par l’hôte (optionnel) — sinon statut filebeat: unknown
FILEBEAT_HEARTBEAT_FILE = os.getenv("FILEBEAT_HEARTBEAT_FILE", "")

OS_LOGS_INDEX = os.getenv("OS_LOGS_INDEX", "con4mity-logs-*")

_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_FRONT = _BACKEND_DIR.parent / "frontend"
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(_DEFAULT_FRONT)))

security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(title="Con4mity API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Si CON4MITY_IP_ALLOWLIST est défini, refuse les appels /api/* hors plages (sauf /api/health)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path == "/api/health":
            return await call_next(request)
        allow = parse_ip_allowlist_env()
        if not allow:
            return await call_next(request)
        ip = client_ip_from_request(
            request.headers.get("x-forwarded-for"),
            request.headers.get("x-real-ip"),
            request.client.host if request.client else None,
        )
        if is_ip_in_allowlist(ip, allow):
            return await call_next(request)
        return JSONResponse(
            status_code=403,
            content={"detail": "Adresse IP non autorisée (CON4MITY_IP_ALLOWLIST)."},
        )


app.add_middleware(IPAllowlistMiddleware)

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


def _empty_alert_stats() -> dict[str, Any]:
    return {
        "new_alerts": 0,
        "in_progress_alerts": 0,
        "resolved_alerts": 0,
        "total_alerts": 0,
        "incidents_open": 0,
        "critical_open": 0,
    }


def _stats_from_db() -> dict[str, Any]:
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        logger.warning("stats PG connect failed: %s", e)
        return _empty_alert_stats()
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
    except (pg_errors.UndefinedTable, pg_errors.UndefinedColumn) as e:
        logger.warning("stats: table ou colonnes alerts manquants — lancer SQL 006 / migrations: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return _empty_alert_stats()
    except psycopg2.Error as e:
        logger.warning("stats requête alerts: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return _empty_alert_stats()
    except Exception as e:
        logger.exception("stats inattendu: %s", e)
        return _empty_alert_stats()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not row:
        return _empty_alert_stats()
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
                GROUP BY COALESCE(rule_name, '—')
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


class SecurityPolicyOut(BaseModel):
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special: bool
    source: str = "merged"  # merged | env


class SecurityPolicyUpdate(BaseModel):
    min_length: int = Field(..., ge=8, le=256)
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = False


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=1, max_length=500)


class ApiKeyCreateIn(BaseModel):
    name: str = Field("default", max_length=200)


# Identifiants des blocs réordonnables sur la page Logs / tableau de bord (ordon = flex order)
LOGS_PANEL_IDS: tuple[str, ...] = (
    "intro",
    "services",
    "kpis",
    "controls",
    "charts",
    "maps",
    "logs_header",
    "log_kpis",
    "filters",
    "stream",
)


class UserPreferencesOut(BaseModel):
    theme: str = "dark"
    locale: str | None = None
    compact_mode: bool = False
    dashboard: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None
    source: str = "default"


class UserPreferencesUpdate(BaseModel):
    theme: str | None = None
    locale: str | None = None
    compact_mode: bool | None = None
    dashboard: dict[str, Any] | None = None


# ---------- Auth ----------
def create_token(sub: str, role: str | None, user_id: int | None = None) -> str:
    """python-jose attend surtout des timestamps numériques pour iat/exp."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=JWT_EXPIRE_HOURS)
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role or "",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if user_id is not None:
        payload["uid"] = int(user_id)
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_merged_password_policy() -> dict[str, Any]:
    """Ligne `security_policy` (id=1) prime sur les variables d'env, sinon env seul."""
    base = get_password_policy_from_env()
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError):
        return base
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    SELECT min_length, require_uppercase, require_lowercase, require_digit, require_special
                    FROM security_policy
                    WHERE id = 1
                    """
                )
            except pg_errors.UndefinedTable:
                return base
            row = cur.fetchone()
    except psycopg2.Error:
        return base
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not row:
        return base
    return {
        "min_length": int(row.get("min_length", base["min_length"])),
        "require_uppercase": bool(row.get("require_uppercase", base.get("require_uppercase"))),
        "require_lowercase": bool(row.get("require_lowercase", base.get("require_lowercase"))),
        "require_digit": bool(row.get("require_digit", base.get("require_digit"))),
        "require_special": bool(row.get("require_special", base.get("require_special"))),
    }


def _log_login_event(
    username: str | None,
    user_id: int | None,
    success: bool,
    reason: str | None,
    ip: str,
    user_agent: str | None,
    geo: str | None = None,
) -> None:
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError):
        return
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO login_events (username, user_id, success, reason, ip, user_agent, geo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (username, user_id, success, reason, ip, user_agent, geo),
                )
            except pg_errors.UndefinedTable:
                return
        conn.commit()
    except psycopg2.Error:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _login_throttle_key(ip: str, username: str) -> str:
    return f"{ip}:{username[:200]}"


def _is_login_throttled(key: str) -> bool:
    now = time.time()
    with _login_fail_lock:
        ts = _login_fail_ts.get(key, [])
        win = float(LOGIN_RATE_WINDOW_SEC)
        ts = [t for t in ts if now - t < win]
        _login_fail_ts[key] = ts
        return len(ts) >= LOGIN_MAX_FAILED


def _record_login_failure(key: str) -> None:
    now = time.time()
    with _login_fail_lock:
        _login_fail_ts.setdefault(key, []).append(now)


def _clear_login_throttle_key(key: str) -> None:
    with _login_fail_lock:
        _login_fail_ts.pop(key, None)


def _validate_api_key_and_user(raw_key: str) -> dict[str, Any] | None:
    h = hash_api_key(raw_key.strip(), API_KEY_PEPPER)
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError):
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    SELECT k.id, k.user_id, u.username, u.role
                    FROM api_keys k
                    JOIN users u ON u.id = k.user_id
                    WHERE k.key_hash = %s AND NOT k.revoked
                    """,
                    (h,),
                )
            except pg_errors.UndefinedTable:
                return None
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE id = %s",
                (row["id"],),
            )
        conn.commit()
    except psycopg2.Error:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "sub": row["username"],
        "role": (row.get("role") or ""),
        "uid": int(row["user_id"]),
        "auth": "api_key",
    }


async def require_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    api_key: str | None = Depends(api_key_header),
) -> dict[str, Any]:
    if api_key and api_key.strip():
        u = _validate_api_key_and_user(api_key)
        if u:
            return u
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou révoquée",
        )
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token or X-API-Key",
        )
    try:
        return decode_token(creds.credentials) | {"auth": "jwt"}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


def _is_admin(claims: dict[str, Any]) -> bool:
    r = (claims.get("role") or "").strip().lower()
    return r == "admin"


async def require_admin(
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    if not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé administrateur")
    return user


# ---------- Routes API ----------
@api.get("/health")
def api_health():
    return {"status": "Con4mity backend OK", "frontend": str(FRONTEND_DIR)}


def _user_id_from_claims(claims: dict[str, Any]) -> int | None:
    u = claims.get("uid")
    if isinstance(u, int):
        return u
    if isinstance(u, str) and u.isdigit():
        return int(u)
    sub = (claims.get("sub") or "").strip()
    if not sub:
        return None
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError):
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (sub,))
            r = cur.fetchone()
        return int(r[0]) if r else None
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


@api.get("/security/policy", response_model=SecurityPolicyOut)
def api_security_policy_public():
    """Politique courante (DB + env) — affichage formulaire changement de mot de passe."""
    p = get_merged_password_policy()
    src = "merged"
    try:
        c = pg_connect()
        try:
            with c.cursor() as cur:
                try:
                    cur.execute("SELECT 1 FROM security_policy WHERE id = 1")
                except pg_errors.UndefinedTable:
                    src = "env"
                else:
                    if not cur.fetchone():
                        src = "env"
        finally:
            c.close()
    except (psycopg2.Error, OSError):
        src = "env"
    return SecurityPolicyOut(
        min_length=int(p["min_length"]),
        require_uppercase=bool(p["require_uppercase"]),
        require_lowercase=bool(p["require_lowercase"]),
        require_digit=bool(p["require_digit"]),
        require_special=bool(p["require_special"]),
        source=src,
    )


@api.get("/security/session")
def api_security_session(user: dict[str, Any] = Depends(require_user)):
    """Rôle et mode d'auth (JWT vs clé API) pour l'UI Paramètres / Sécurité."""
    return {
        "username": user.get("sub"),
        "role": (user.get("role") or "").strip().lower() or "user",
        "auth": user.get("auth") or "jwt",
    }


@api.get("/security/ip-allowlist")
def api_security_ip_status():
    """Indique si CON4MITY_IP_ALLOWLIST est actif (sans divulguer les plages)."""
    nets = parse_ip_allowlist_env()
    return {"active": bool(nets), "count": len(nets)}


@api.put("/security/policy", response_model=SecurityPolicyOut)
def api_security_policy_put(
    body: SecurityPolicyUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
):
    """Met à jour la politique mots de passe (persistée en base)."""
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(500, detail=f"Base indisponible: {e}") from e
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO security_policy (id, updated_at, min_length, require_uppercase, require_lowercase, require_digit, require_special)
                    VALUES (1, NOW(), %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        updated_at = NOW(),
                        min_length = EXCLUDED.min_length,
                        require_uppercase = EXCLUDED.require_uppercase,
                        require_lowercase = EXCLUDED.require_lowercase,
                        require_digit = EXCLUDED.require_digit,
                        require_special = EXCLUDED.require_special
                    """,
                    (
                        body.min_length,
                        body.require_uppercase,
                        body.require_lowercase,
                        body.require_digit,
                        body.require_special,
                    ),
                )
            except pg_errors.UndefinedTable:
                raise HTTPException(
                    503,
                    detail="Migrations requises : exécuter backend/sql/005_security_production.sql",
                ) from None
        conn.commit()
    except HTTPException:
        raise
    except psycopg2.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    p = get_merged_password_policy()
    return SecurityPolicyOut(
        min_length=int(p["min_length"]),
        require_uppercase=bool(p["require_uppercase"]),
        require_lowercase=bool(p["require_lowercase"]),
        require_digit=bool(p["require_digit"]),
        require_special=bool(p["require_special"]),
        source="merged",
    )


@api.get("/security/login-events")
def api_security_login_events(
    _admin: dict[str, Any] = Depends(require_admin),
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(50, ge=1, le=200),
    username: str | None = None,
):
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e
    off = (page - 1) * page_size
    ufilter = (username or "").strip() or None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if ufilter:
                    cur.execute(
                        "SELECT count(*)::bigint AS c FROM login_events WHERE username = %s",
                        (ufilter,),
                    )
                else:
                    cur.execute("SELECT count(*)::bigint AS c FROM login_events")
            except pg_errors.UndefinedTable:
                return {"items": [], "total": 0, "page": page, "page_size": page_size}
            total = int((cur.fetchone() or {}).get("c", 0) or 0)
            if ufilter:
                cur.execute(
                    """
                    SELECT id, ts, username, user_id, success, reason, ip, user_agent, geo
                    FROM login_events
                    WHERE username = %s
                    ORDER BY ts DESC
                    LIMIT %s OFFSET %s
                    """,
                    (ufilter, page_size, off),
                )
            else:
                cur.execute(
                    """
                    SELECT id, ts, username, user_id, success, reason, ip, user_agent, geo
                    FROM login_events
                    ORDER BY ts DESC
                    LIMIT %s OFFSET %s
                    """,
                    (page_size, off),
                )
            rows = cur.fetchall()
    except HTTPException:
        raise
    except psycopg2.Error as e:
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "items": [dict(r) for r in rows or []],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@api.get("/security/api-keys")
def api_security_api_keys_list(_admin: dict[str, Any] = Depends(require_admin)):
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    SELECT k.id, k.created_at, k.name, k.key_prefix, k.last_used_at, k.revoked, u.username AS owner
                    FROM api_keys k
                    JOIN users u ON u.id = k.user_id
                    WHERE NOT k.revoked
                    ORDER BY k.created_at DESC
                    LIMIT 500
                    """
                )
            except pg_errors.UndefinedTable:
                return {"items": []}
            items = cur.fetchall()
    except psycopg2.Error as e:
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"items": [dict(x) for x in items]}


@api.post("/security/api-keys")
def api_security_api_keys_create(
    body: ApiKeyCreateIn,
    _admin: dict[str, Any] = Depends(require_admin),
):
    """Création : la valeur secrète n'est retournée qu'ici. Stocker là où il faut (vault, .env, etc.)."""
    uid = _user_id_from_claims(_admin)
    if not uid:
        raise HTTPException(400, detail="ID utilisateur introuvable (reconnectez-vous).")
    raw = generate_api_key()
    kh = hash_api_key(raw, API_KEY_PEPPER)
    prefix = raw[:12] + "…"
    nm = (body.name or "default").strip()[:200] or "default"
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO api_keys (user_id, name, key_hash, key_prefix, revoked)
                    VALUES (%s, %s, %s, %s, FALSE)
                    RETURNING id, created_at
                    """,
                    (uid, nm, kh, prefix),
                )
            except pg_errors.UndefinedTable:
                raise HTTPException(
                    503,
                    detail="Migrations requises : exécuter backend/sql/005_security_production.sql",
                ) from None
            row = cur.fetchone()
        conn.commit()
    except HTTPException:
        raise
    except psycopg2.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    _log_operator_activity(
        (_admin.get("sub") or "admin")[:200],
        "api_key_create",
        f"id {row.get('id') if row else '?'}"[:2000],
    )
    return {
        "id": int((row or {}).get("id", 0)),
        "name": nm,
        "key_prefix": prefix,
        "secret": raw,
        "message": "Conservez ce secret de façon sûre ; il ne sera plus affiché.",
    }


@api.delete("/security/api-keys/{key_id}")
def api_security_api_keys_delete(
    key_id: int,
    _admin: dict[str, Any] = Depends(require_admin),
):
    n = 0
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "UPDATE api_keys SET revoked = TRUE WHERE id = %s AND NOT revoked",
                    (key_id,),
                )
            except pg_errors.UndefinedTable:
                raise HTTPException(503, detail="Migrations requises") from None
            n = cur.rowcount
        conn.commit()
    except HTTPException:
        raise
    except psycopg2.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not n:
        raise HTTPException(404, detail="Clé inconnue ou déjà révoquée")
    return {"id": key_id, "revoked": True}


@api.post("/security/change-password")
def api_security_change_password(
    body: ChangePasswordIn,
    user: dict[str, Any] = Depends(require_user),
):
    if (user.get("auth") or "") == "api_key":
        raise HTTPException(
            400,
            detail="Changement de mot de passe réservé à une session web (Bearer JWT), pas à une clé API.",
        )
    pol = get_merged_password_policy()
    ok, msg = validate_password_strength(body.new_password, pol)
    if not ok:
        raise HTTPException(400, detail=msg)
    uid = _user_id_from_claims(user)
    if not uid:
        raise HTTPException(400, detail="Utilisateur non résolu. Reconnectez-vous pour obtenir un jeton récent (uid).")
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(500, detail=str(e)) from e
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, password_hash, username FROM users WHERE id = %s",
                (uid,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(404, detail="User not found")
        old_h = (row.get("password_hash") or "").encode("utf-8")
        if not bcrypt.checkpw(body.current_password.encode("utf-8"), old_h):
            raise HTTPException(401, detail="Mot de passe actuel incorrect")
        new_h = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt(rounds=12))
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_h.decode("utf-8"), uid),
            )
        conn.commit()
    except HTTPException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except psycopg2.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    uname = (row.get("username") or "user")[:200] if row else "user"
    _log_operator_activity(uname, "password_change", "self-service")
    return {"ok": True, "message": "Mot de passe mis à jour. Reconnectez-vous sur les autres appareils si besoin."}


def _default_dashboard_api() -> dict[str, Any]:
    return {
        "logs": {
            "panel_order": list(LOGS_PANEL_IDS),
            "charts_visible": True,
            "ws_default": False,
        }
    }


def _sanitize_logs_panel_order(order: list[Any] | None) -> list[str]:
    allowed = list(LOGS_PANEL_IDS)
    allowed_set = set(allowed)
    if not order:
        return list(allowed)
    seen: set[str] = set()
    out: list[str] = []
    for x in order:
        s = str(x).strip() if x is not None else ""
        if s in allowed_set and s not in seen:
            out.append(s)
            seen.add(s)
    for p in allowed:
        if p not in seen:
            out.append(p)
    return out


def _parse_dashboard_cell(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except Exception:
            return {}
    return {}


def _merge_dashboard_json(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    d = copy.deepcopy(base) if base else _default_dashboard_api()
    if not patch:
        return d
    if not isinstance(patch, dict):
        return d
    logs_in = patch.get("logs")
    if isinstance(logs_in, dict):
        lg: dict[str, Any] = dict(d.get("logs") or {})
        if "panel_order" in logs_in and isinstance(logs_in.get("panel_order"), list):
            lg["panel_order"] = _sanitize_logs_panel_order(logs_in.get("panel_order"))
        if "charts_visible" in logs_in:
            lg["charts_visible"] = bool(logs_in.get("charts_visible"))
        if "ws_default" in logs_in:
            lg["ws_default"] = bool(logs_in.get("ws_default"))
        d["logs"] = lg
    return d


def _prefs_out_defaults() -> UserPreferencesOut:
    return UserPreferencesOut(
        theme="dark",
        locale=None,
        compact_mode=False,
        dashboard=_default_dashboard_api(),
        updated_at=None,
        source="default",
    )


def _row_to_user_prefs_out(r: dict[str, Any]) -> UserPreferencesOut:
    upd = r.get("updated_at")
    if hasattr(upd, "isoformat"):
        uds = upd.isoformat()
    else:
        uds = str(upd) if upd else None
    dash = _merge_dashboard_json(_default_dashboard_api(), _parse_dashboard_cell(r.get("dashboard")))
    loc = (r.get("locale") or "").strip() if r.get("locale") is not None else ""
    return UserPreferencesOut(
        theme=((r.get("theme") or "dark").strip()[:16] or "dark"),
        locale=loc[:8] if loc else None,
        compact_mode=bool(r.get("compact_mode", False)),
        dashboard=dash,
        updated_at=uds,
        source="db",
    )


@api.get("/me/preferences", response_model=UserPreferencesOut)
def get_my_preferences(user: dict[str, Any] = Depends(require_user)):
    """Préférences interface (thème, locale, ordre des panneaux) — stockées côté serveur."""
    uid = _user_id_from_claims(user)
    if not uid:
        return _prefs_out_defaults()
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        logger.warning("GET /me/preferences: PG: %s", e)
        return _prefs_out_defaults()
    out: UserPreferencesOut = _prefs_out_defaults()
    r: Any = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    SELECT theme, locale, compact_mode, dashboard, updated_at
                    FROM user_preferences
                    WHERE user_id = %s
                    """,
                    (uid,),
                )
            except pg_errors.UndefinedTable:
                return _prefs_out_defaults()
            r = cur.fetchone()
    except psycopg2.Error as e:
        logger.warning("GET /me/preferences: %s", e)
        return _prefs_out_defaults()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if r:
        out = _row_to_user_prefs_out(dict(r))
    return out


@api.put("/me/preferences", response_model=UserPreferencesOut)
def put_my_preferences(
    body: UserPreferencesUpdate,
    user: dict[str, Any] = Depends(require_user),
):
    """Met à jour les préférences (merge partiel : champs absents = inchangés)."""
    uid = _user_id_from_claims(user)
    if not uid:
        raise HTTPException(
            status_code=400,
            detail="Reconnectez-vous pour un jeton avec id utilisateur (préférences par compte).",
        )
    if body.theme is not None and str(body.theme) not in ("dark", "light", "system"):
        raise HTTPException(status_code=400, detail="theme: utiliser dark, light ou system")
    loc_in = body.locale
    if loc_in is not None and str(loc_in).strip() != "":
        l2 = str(loc_in).strip().lower()[:8]
        if l2 not in ("fr", "en", "es"):
            raise HTTPException(status_code=400, detail="locale: fr, en ou es")
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(503, detail=f"Base indisponible: {e!s}"[:500]) from e
    current_merged: UserPreferencesOut = _prefs_out_defaults()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    "SELECT theme, locale, compact_mode, dashboard, updated_at FROM user_preferences WHERE user_id = %s",
                    (uid,),
                )
            except pg_errors.UndefinedTable:
                raise HTTPException(
                    status_code=503,
                    detail="Migrations requises : exécuter backend/sql/007_user_preferences.sql",
                ) from None
            ex = cur.fetchone()
        if ex:
            current_merged = _row_to_user_prefs_out(dict(ex))
    except HTTPException:
        try:
            conn.close()
        except Exception:
            pass
        raise
    except psycopg2.Error as e:
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(500, detail=str(e)) from e

    new_theme = (
        (body.theme or current_merged.theme or "dark") if body.theme is not None else (current_merged.theme or "dark")
    )
    new_theme = str(new_theme).strip()[:16] or "dark"
    if body.locale is not None:
        lraw = str(body.locale).strip().lower()[:8]
        new_loc = lraw if lraw in ("fr", "en", "es") else None
    else:
        new_loc = current_merged.locale
    new_compact = current_merged.compact_mode
    if body.compact_mode is not None:
        new_compact = bool(body.compact_mode)
    if body.dashboard is not None and body.dashboard == {}:
        new_dash = _default_dashboard_api()
    elif body.dashboard is not None:
        new_dash = _merge_dashboard_json(current_merged.dashboard, body.dashboard)
    else:
        new_dash = copy.deepcopy(current_merged.dashboard) or _default_dashboard_api()
    if not new_dash.get("logs"):
        new_dash = _merge_dashboard_json(_default_dashboard_api(), new_dash)

    row: tuple[Any, ...] | None = None
    try:
        with conn.cursor() as cur2:
            cur2.execute(
                """
                INSERT INTO user_preferences (user_id, theme, locale, compact_mode, dashboard, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    theme = EXCLUDED.theme,
                    locale = EXCLUDED.locale,
                    compact_mode = EXCLUDED.compact_mode,
                    dashboard = EXCLUDED.dashboard,
                    updated_at = NOW()
                RETURNING theme, locale, compact_mode, dashboard, updated_at
                """,
                (uid, new_theme, new_loc, new_compact, json.dumps(new_dash)),
            )
            row = cur2.fetchone()
        conn.commit()
    except psycopg2.Error as e:
        try:
            conn.rollback()
        except Exception:
            pass
        row = None
        raise HTTPException(500, detail=str(e)) from e
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        return _prefs_out_defaults()
    return _row_to_user_prefs_out(
        {
            "theme": row[0],
            "locale": row[1],
            "compact_mode": row[2],
            "dashboard": row[3],
            "updated_at": row[4],
        }
    )


@api.post("/login", response_model=TokenOut)
def login(request: Request, body: LoginBody):
    """Authentification classique : journal de connexions, anti-bruteforce (par IP+utilisateur)."""
    uname = (body.username or "").strip()[:200]
    ip = client_ip_from_request(
        request.headers.get("x-forwarded-for"),
        request.headers.get("x-real-ip"),
        request.client.host if request.client else None,
    )
    ua = (request.headers.get("user-agent") or "")[:2000] or None
    geo = (request.headers.get("cf-ipcountry") or request.headers.get("x-geo-country") or "")[:12] or None
    throttle_key = _login_throttle_key(ip, uname)
    if _is_login_throttled(throttle_key):
        _log_login_event(
            uname, None, False, "rate_limited", ip, ua, geo,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez plus tard.",
        )

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
        _record_login_failure(throttle_key)
        _log_login_event(uname, None, False, "unknown_user", ip, ua, geo)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    stored_hash = (row.get("password_hash") or "").strip()
    if not stored_hash:
        _log_login_event(uname, int(row["id"]), False, "empty_hash", ip, ua, geo)
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
        _log_login_event(uname, int(row["id"]), False, f"hash_error: {e}", ip, ua, geo)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password hash invalid: {e}",
        ) from e

    if not ok:
        _record_login_failure(throttle_key)
        _log_login_event(uname, int(row["id"]), False, "bad_password", ip, ua, geo)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    _clear_login_throttle_key(throttle_key)
    _log_login_event(uname, int(row["id"]), True, None, ip, ua, geo)
    token = create_token(sub=row["username"], role=row.get("role"), user_id=int(row["id"]))
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


def _alerts_list_normalize(d: dict[str, Any]) -> dict[str, Any]:
    d = dict(d)
    st = d.get("status")
    d["status"] = (st if st is not None and str(st).strip() else None) or "new"
    d.setdefault("log_ids", None)
    d.setdefault("status_note", "")
    d.setdefault("last_actor", "")
    if d.get("updated_at") is None and d.get("created_at") is not None:
        d["updated_at"] = d["created_at"]
    return d


def _alerts_list_fetch_with_fallback(cur: Any) -> list[Any]:
    """Enchaîne des SELECT compatibles schémas partiels (évite 500 en prod)."""
    sqls = (
        _alerts_list_query().strip(),
        """
        SELECT id, created_at, rule_name, severity, host, description, status, log_ids, updated_at
        FROM alerts
        ORDER BY created_at DESC NULLS LAST
        LIMIT 200
        """,
        """
        SELECT
            id, created_at, rule_name, severity, host, description
        FROM alerts
        ORDER BY created_at DESC NULLS LAST
        LIMIT 200
        """,
    )
    last_err: Exception | None = None
    for q in sqls:
        try:
            cur.execute(q)
            return list(cur.fetchall() or [])
        except pg_errors.UndefinedTable:
            return []
        except pg_errors.UndefinedColumn as e:
            last_err = e
            try:
                cur.connection.rollback()  # type: ignore[union-attr]
            except Exception:
                pass
            continue
    if last_err:
        logger.warning("alerts list: schéma incompatible: %s", last_err)
    return []


@api.get("/alerts")
def get_alerts(user: dict = Depends(require_user)):
    rows: list[dict[str, Any]] = []
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        logger.warning("get_alerts: connexion PG: %s", e)
        return []
    try:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                raw = _alerts_list_fetch_with_fallback(cur)
        except pg_errors.UndefinedTable:
            logger.warning("get_alerts: table alerts absente (SQL 006_alerts_bootstrap.sql)")
            return []
        except psycopg2.Error as e:
            logger.warning("get_alerts: %s", e)
            return []
        rows = [_alerts_list_normalize(dict(x)) for x in raw]
    except Exception as e:
        logger.exception("get_alerts: %s", e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return jsonable_encoder(rows)


@api.get("/alerts/daily")
def get_alerts_daily(
    user: dict = Depends(require_user),
    days: int = Query(30, ge=1, le=90),
):
    rrows: list[tuple[Any, ...]] = []
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        logger.warning("alerts/daily: connexion: %s", e)
        return []
    try:
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
                rrows = list(cur.fetchall() or [])
        except (pg_errors.UndefinedTable, pg_errors.UndefinedColumn) as e:
            logger.warning("alerts/daily: %s", e)
        except psycopg2.Error as e:
            logger.warning("alerts/daily: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [{"date": str(r[0]), "count": r[1]} for r in rrows]


def _alert_detail_fetch_with_fallback(cur: Any, alert_id: int) -> dict[str, Any] | None:
    pairs: tuple[tuple[str, tuple[Any, ...]], ...] = (
        (
            """
            SELECT
                id, created_at, rule_name, severity, host, description, status, log_ids, updated_at,
                COALESCE(status_note, '') AS status_note, COALESCE(last_actor, '') AS last_actor
            FROM alerts
            WHERE id = %s
            """,
            (alert_id,),
        ),
        (
            """
            SELECT id, created_at, rule_name, severity, host, description, status, log_ids, updated_at
            FROM alerts
            WHERE id = %s
            """,
            (alert_id,),
        ),
        (
            """
            SELECT id, created_at, rule_name, severity, host, description
            FROM alerts
            WHERE id = %s
            """,
            (alert_id,),
        ),
    )
    last_col: Exception | None = None
    for q, p in pairs:
        try:
            cur.execute(q, p)
            r = cur.fetchone()
            if not r:
                return None
            return _alerts_list_normalize(dict(r))
        except pg_errors.UndefinedTable:
            raise
        except pg_errors.UndefinedColumn as e:
            last_col = e
            try:
                cur.connection.rollback()  # type: ignore[union-attr]
            except Exception:
                pass
            continue
    if last_col:
        logger.warning("alert detail: schéma %s: %s", alert_id, last_col)
    return None


@api.get("/alerts/{alert_id}")
def get_alert_detail(alert_id: int, user: dict = Depends(require_user)):
    try:
        conn = pg_connect()
    except (psycopg2.Error, OSError) as e:
        raise HTTPException(
            status_code=503,
            detail=f"PostgreSQL indisponible: {e!s}"[:500],
        ) from e
    row: dict[str, Any] | None = None
    try:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    r = _alert_detail_fetch_with_fallback(cur, alert_id)
                except pg_errors.UndefinedTable:
                    raise HTTPException(
                        status_code=503,
                        detail="Table alerts absente — exécuter backend/sql/006_alerts_bootstrap.sql sur PostgreSQL",
                    ) from None
                row = r
        except HTTPException:
            raise
        except psycopg2.Error as e:
            logger.warning("get_alert_detail: %s", e)
            raise HTTPException(503, detail="Erreur base alertes") from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
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
    """
    Vue synthétique : stats PG + agrégations légères sur un échantillon de logs (Pi-friendly).
    Chaque sous-brique est isolée : une panne (PG, OS, requête SQL) ne renvoie plus tout le bloc en 500.
    """
    empty_stats: dict[str, int] = {
        "new_alerts": 0,
        "in_progress_alerts": 0,
        "resolved_alerts": 0,
        "total_alerts": 0,
        "incidents_open": 0,
        "critical_open": 0,
    }
    try:
        stats = _stats_from_db()
    except Exception as e:
        logger.exception("overview: stats PG failed: %s", e)
        stats = empty_stats

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
    except Exception as e:
        logger.exception("overview: OpenSearch sample failed: %s", e)
        docs = []

    timeline, top_hosts = _aggregate_logs_overview(docs, hours=24)
    events_24h = len(docs)
    recent_rate = sum(b["count"] for b in timeline[-3:]) if timeline else 0
    top_source_ips = aggregate_top_ips(docs, limit=5)

    try:
        vol24 = _opensearch_volume_24h()
    except Exception as e:
        logger.exception("overview: volume_24h failed: %s", e)
        vol24 = []

    try:
        top_rules = _top_alert_rules_from_db(5)
    except Exception as e:
        logger.exception("overview: top_alert_rules failed: %s", e)
        top_rules = []

    try:
        services = _os_cluster_services()
    except Exception as e:
        logger.exception("overview: services check failed: %s", e)
        services = {
            "opensearch": {"ok": False, "error": str(e)[:200]},
            "postgresql": {"ok": False},
            "filebeat": {"ok": None, "detail": "unavailable"},
        }

    return {
        "stats": stats,
        "timeline": timeline,
        "top_hosts": top_hosts,
        "top_source_ips": top_source_ips,
        "top_alert_rules": top_rules,
        "log_volume_24h": vol24,
        "services": services,
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
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        return



# === Webhook ElastAlert → alertes dans PostgreSQL ===
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "9JZU8IZv9nmj41mtYYnSZI0BlSYLUhRseC0tHfIuab4")

class AlertWebhook(BaseModel):
    rule_name: str
    severity: str = "medium"
    host: str | None = None
    description: str | None = None
    num_matches: int | None = None
    log_ids: list[str] | None = None


@api.post("/webhook/alert")
async def webhook_alert(body: AlertWebhook, request: Request):
    """Réception d'alertes ElastAlert — auth par token dans header X-Webhook-Token."""
    token = request.headers.get("X-Webhook-Token", "")
    if token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    sev = (body.severity or "medium").lower()
    if sev not in ("critical", "high", "medium", "low", "info"):
        sev = "medium"

    description = body.description or f"{body.num_matches or 0} matches détectés"
    log_ids_json = json.dumps(body.log_ids or [])

    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alerts (rule_name, severity, host, description, status, created_at, log_ids)
                VALUES (%s, %s, %s, %s, 'new', NOW(), %s)
                RETURNING id
                """,
                (body.rule_name, sev, body.host or "unknown", description, log_ids_json),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}") from e
    finally:
        conn.close()

    return {"id": new_id, "status": "inserted"}



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
