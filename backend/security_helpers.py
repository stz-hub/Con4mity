"""
Politique de mots de passe, filtrage IP et utilitaires clés API (hachage) — production.
Aucun accès BDD ici.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import secrets
from typing import Any


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_bool01(name: str, default: bool) -> bool:
    v = os.getenv(name, "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    if v == "":
        return default
    return default


def get_password_policy_from_env() -> dict[str, Any]:
    return {
        "min_length": _env_int("PASSWORD_MIN_LENGTH", 12),
        "require_uppercase": _env_bool01("PASSWORD_REQUIRE_UPPER", True),
        "require_lowercase": _env_bool01("PASSWORD_REQUIRE_LOWER", True),
        "require_digit": _env_bool01("PASSWORD_REQUIRE_DIGIT", True),
        "require_special": _env_bool01("PASSWORD_REQUIRE_SPECIAL", False),
    }


def validate_password_strength(
    password: str,
    policy: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    p = policy or get_password_policy_from_env()
    if not password or len(password) < int(p.get("min_length", 12)):
        return False, f"Le mot de passe doit contenir au moins {p.get('min_length', 12)} caractères."
    if p.get("require_uppercase") and not re.search(r"[A-Z]", password):
        return False, "Le mot de passe doit contenir au moins une majuscule."
    if p.get("require_lowercase") and not re.search(r"[a-z]", password):
        return False, "Le mot de passe doit contenir au moins une minuscule."
    if p.get("require_digit") and not re.search(r"\d", password):
        return False, "Le mot de passe doit contenir au moins un chiffre."
    if p.get("require_special") and not re.search(r"[!@#$%^&*()_+\-=[\]{};':\"|,.<>/?`~\\]", password):
        return False, "Le mot de passe doit contenir au moins un caractère spécial."
    if len(password) > 500:
        return False, "Mot de passe trop long."
    return True, ""


def parse_ip_allowlist_env() -> list[ipaddress._BaseNetwork]:
    """
    CON4MITY_IP_ALLOWLIST=192.168.0.0/24,10.0.0.0/8,127.0.0.1/32
    Chaîne vide = pas de filtre (tout autorisé).
    """
    raw = os.getenv("CON4MITY_IP_ALLOWLIST", "").strip()
    if not raw:
        return []
    nets: list[ipaddress._BaseNetwork] = []
    for part in raw.split(","):
        s = part.strip()
        if not s:
            continue
        try:
            nets.append(ipaddress.ip_network(s, strict=False))
        except ValueError:
            continue
    return nets


def client_ip_from_request(
    x_forwarded_for: str | None,
    x_real_ip: str | None,
    direct: str | None,
) -> str:
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if x_real_ip and x_real_ip.strip():
        return x_real_ip.strip()
    if direct:
        return direct
    return "0.0.0.0"


def is_ip_in_allowlist(ip_s: str, allowlist: list[ipaddress._BaseNetwork] | None = None) -> bool:
    nets = allowlist if allowlist is not None else parse_ip_allowlist_env()
    if not nets:
        return True
    try:
        ip = ipaddress.ip_address(ip_s.split("%")[0])
    except ValueError:
        return False
    for n in nets:
        if ip in n:
            return True
    return False


def generate_api_key() -> str:
    return f"c4_{secrets.token_urlsafe(32)}"


def hash_api_key(raw: str, pepper: str) -> str:
    return hashlib.sha256(f"{pepper}::{raw}".encode("utf-8")).hexdigest()
