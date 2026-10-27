# Copyright 2026 EuroValidate (https://eurovalidate.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""HTTP client for the EuroValidate VAT endpoint.

Deliberately Odoo-free (no ``odoo`` import) so the response mapping can be
unit-tested outside an Odoo instance. ``res_partner.py`` turns the dicts
returned here into field values, warnings and ``UserError``s.

Outcome contract (``parse_response``)::

    {
        "outcome":  "ok" | "bad_key" | "forbidden" | "quota" | "unavailable" | "bad_input",
        "status":   "valid" | "invalid" | "unavailable" | "error" | "unverified" | "unknown",
        "confidence": "high" | "medium" | "low" | "unknown",
        "company_name": str | None, "company_address": str | None,
        "request_id": str | None, "source": str | None, "last_verified": str | None,
        "detail": str,   # human-readable, safe to show
    }

Notes for implementers:
* Germany and Spain never return company name/address through VIES (national
  data-protection law); ``company_name`` is ``None`` for them even when valid.
* ``status: unavailable`` means the national backend is down and nothing is
  cached yet. Treat it as "pending", never as "invalid".
* ``status: unverified`` (CL/TR/IL/MX/CA/PH) is a format/checksum check only.
"""

import logging

try:  # requests is an external dependency declared in the manifest
    import requests
except ImportError:  # pragma: no cover - surfaced by Odoo's dependency check
    requests = None

_logger = logging.getLogger(__name__)

MODULE_VERSION = "18.0.1.0.0"
DEFAULT_BASE_URL = "https://api.eurovalidate.com"
SIGNUP_URL = "https://eurovalidate.com/v1/auth/signup?utm_source=odoo&utm_medium=module&utm_campaign=error"
UPGRADE_URL = "https://api.eurovalidate.com/v1/auth/dashboard"
TIMEOUT = (3.05, 15)  # connect, read — slow member states (CZ/DK/FR) take 9-11 s
VALID_STATUSES = ("valid", "invalid", "unavailable", "error", "unverified")


def mask_vat(vat):
    """``DE811569869`` -> ``DE***69`` — for logs only."""
    vat = (vat or "").strip()
    return vat[:2] + "***" + vat[-2:] if len(vat) > 6 else "***"


def normalise_vat(vat):
    """Strip spaces, dots and dashes, uppercase. ``CHE-116.281.710`` -> ``CHE116281710``."""
    return "".join(ch for ch in (vat or "").upper() if ch not in " .-\t\n")


def is_plausible(vat):
    """Two-letter prefix plus at least four characters — enough to be worth a call."""
    v = normalise_vat(vat)
    return len(v) >= 6 and v[:2].isalpha()


def parse_response(status_code, payload):
    """Map an HTTP status + JSON body to the outcome contract (see module doc)."""
    payload = payload if isinstance(payload, dict) else {}
    detail = payload.get("detail") or payload.get("title") or ""
    base = {
        "status": "unknown",
        "confidence": "unknown",
        "company_name": None,
        "company_address": None,
        "request_id": None,
        "source": None,
        "last_verified": None,
        "detail": detail,
    }
    if status_code == 200:
        meta = payload.get("meta") or {}
        status = payload.get("status")
        if status not in VALID_STATUSES:
            status = "error"
        return dict(
            base,
            outcome="ok",
            status=status,
            confidence=(meta.get("confidence") or "unknown").lower(),
            company_name=payload.get("company_name") or None,
            company_address=payload.get("company_address") or None,
            request_id=payload.get("request_id"),
            source=meta.get("source"),
            last_verified=meta.get("last_verified"),
            detail=detail or (meta.get("upstream_status") or ""),
        )
    if status_code == 401:
        return dict(base, outcome="bad_key", detail="Invalid EuroValidate API key. Check Settings > EuroValidate.")
    if status_code == 403:
        return dict(base, outcome="forbidden", status="unknown", detail=detail or "This lookup needs a paid EuroValidate plan.")
    if status_code == 429:
        return dict(base, outcome="quota", status="unavailable", detail=detail or "EuroValidate monthly quota reached.")
    if status_code in (400, 422):
        return dict(base, outcome="bad_input", status="error", detail=detail or "The VAT number was rejected as malformed.")
    return dict(base, outcome="unavailable", status="unavailable", detail=detail or "EuroValidate is temporarily unavailable (HTTP %s)." % status_code)


def lookup_vat(vat, api_key, base_url=DEFAULT_BASE_URL):
    """GET /v1/vat/{number}. Never raises: network problems become ``unavailable``."""
    number = normalise_vat(vat)
    if requests is None:
        return dict(parse_response(503, {}), detail="The python package 'requests' is not installed.")
    url = "%s/v1/vat/%s" % ((base_url or DEFAULT_BASE_URL).rstrip("/"), number)
    headers = {
        "X-API-Key": api_key or "",
        "User-Agent": "eurovalidate-odoo/%s" % MODULE_VERSION,
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.exceptions.RequestException as exc:  # timeouts, DNS, TLS, connection
        _logger.info("eurovalidate: request failed for %s (%s)", mask_vat(number), type(exc).__name__)
        return dict(parse_response(503, {}), detail="EuroValidate could not be reached (%s)." % type(exc).__name__)
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    result = parse_response(resp.status_code, payload)
    _logger.info("eurovalidate: %s -> %s/%s", mask_vat(number), result["outcome"], result["status"])
    return result
