"""SSRF-Guard für nutzergesteuerte Outbound-URLs (z. B. Webhook-Alerts).

Der alte Filter matchte nur nackte IPv4-Literale im Hostname. Umgehbar durch:
  * DNS-Namen, die auf 127.0.0.1 / 169.254.169.254 (Cloud-Metadata) auflösen
  * IPv6 (``[::1]``, ``[fe80::1]``)
  * dezimal/oktal/hex kodierte IPv4-Adressen (``2130706433`` == 127.0.0.1)

Dieser Guard löst den Hostnamen tatsächlich auf und prüft **alle** aufgelösten
IP-Adressen (IPv4 *und* IPv6, inkl. IPv4-mapped) gegen private/reservierte
Bereiche. Weil ``socket.getaddrinfo`` die kodierten IPv4-Formen ebenfalls auf die
echte Adresse normalisiert, sind auch diese abgedeckt.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class SSRFValidationError(ValueError):
    """Wird geworfen, wenn eine URL auf einen nicht-öffentlichen Host zeigt."""


def _ip_is_blocked(ip: _IPAddress) -> bool:
    """True, wenn die IP nicht öffentlich routbar ist (SSRF-Ziel).

    Deckt Loopback, private RFC-1918-Netze, Link-Local (inkl. AWS/GCP-Metadata
    169.254.169.254), Unique-Local-IPv6 (fc00::/7), reservierte, Multicast- und
    unspezifizierte Adressen ab. IPv4-mapped IPv6 (``::ffff:127.0.0.1``) wird auf
    die eingebettete IPv4 zurückgeführt.
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_https_url(url: str) -> None:
    """Validiert, dass ``url`` https ist und auf eine öffentliche IP auflöst.

    Raises:
        SSRFValidationError: bei falschem Schema, fehlendem/unauflösbarem Host
            oder wenn irgendeine aufgelöste IP in einem gesperrten Bereich liegt.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover - urlparse wirft praktisch nie
        raise SSRFValidationError("Ungültige URL.") from exc

    if parsed.scheme != "https":
        raise SSRFValidationError(
            "Webhook-URL muss mit https:// beginnen (http:// und andere Schemas sind nicht erlaubt)."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("Webhook-URL enthält keinen gültigen Hostname.")

    port = parsed.port or 443
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFValidationError(
            "Webhook-Host konnte nicht aufgelöst werden — URL wird abgelehnt."
        ) from exc

    resolved = {info[4][0] for info in infos}
    if not resolved:
        raise SSRFValidationError("Webhook-Host lieferte keine IP-Adresse.")

    for addr in resolved:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:  # pragma: no cover - getaddrinfo liefert valide IPs
            raise SSRFValidationError("Webhook-Host lieferte eine ungültige IP.") from None
        if _ip_is_blocked(ip):
            raise SSRFValidationError(
                "Webhook-URL darf nicht auf private/interne Adressen zeigen "
                "(Loopback, RFC-1918, Link-Local/Metadata, IPv6-ULA etc. sind blockiert)."
            )


def is_public_https_url(url: str) -> bool:
    """Bool-Variante von :func:`validate_public_https_url` (kein Raise)."""
    try:
        validate_public_https_url(url)
    except SSRFValidationError:
        return False
    return True
