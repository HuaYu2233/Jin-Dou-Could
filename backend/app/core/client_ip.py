from functools import cache

from fastapi import Request
from starlette.types import Scope

from app.core.config import settings


@cache
def get_trusted_proxies() -> frozenset[str]:
    if not settings.TRUSTED_PROXIES:
        return frozenset()
    return frozenset(p.strip() for p in settings.TRUSTED_PROXIES.split(",") if p.strip())


def _resolve(direct_ip: str | None, xff: str | None, x_real_ip: str | None) -> str:
    if not direct_ip:
        return "unknown"
    if direct_ip not in get_trusted_proxies():
        return direct_ip
    if xff:
        return xff.split(",")[0].strip()
    if x_real_ip:
        return x_real_ip.strip()
    return direct_ip


def get_client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else None
    return _resolve(
        direct_ip,
        request.headers.get("x-forwarded-for"),
        request.headers.get("x-real-ip"),
    )


def get_client_ip_from_scope(scope: Scope) -> str:
    client = scope.get("client")
    direct_ip = client[0] if client else None
    headers = dict(scope.get("headers", []))
    xff = headers.get(b"x-forwarded-for")
    x_real_ip = headers.get(b"x-real-ip")
    return _resolve(
        direct_ip,
        xff.decode() if xff else None,
        x_real_ip.decode() if x_real_ip else None,
    )
