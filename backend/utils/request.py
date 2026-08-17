from typing import Optional
import socket


def get_request_host(request) -> str:
    """
    Obtiene el hostname o dominio preferido a partir de la Request (Tailscale VPN, Proxies inversos, Host Header o DNS).
    """
    try:
        if not request:
            return "sistema"

        # 1. Cabecera Host o X-Forwarded-Host (especialmente útil en Tailscale Serve / Funnel / Nginx / Dominios)
        host_header = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host_header:
            # Quitar puerto si viene incluido (ej. 'desktop-2atnf0e.taile4a3e8.ts.net:50000' -> 'desktop-2atnf0e.taile4a3e8.ts.net')
            h = host_header.split(":")[0].strip()
            if h and h not in ["127.0.0.1", "localhost", "0.0.0.0", "::1"]:
                return h

        # 2. Obtener IP del cliente (priorizando X-Forwarded-For o socket real)
        xff = request.headers.get("x-forwarded-for") or ""
        client_ip = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else ""))
        if not client_ip:
            return host_header or "unknown"

        # 3. Intentar resolución DNS inversa de la IP
        try:
            return socket.gethostbyaddr(client_ip)[0]
        except Exception:
            return client_ip

    except Exception:
        return "unknown"
