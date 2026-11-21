"""Landing attribution clean-up and the Channel rule (lead-crm R17).

Pure functions: no database, no clock, never raise. The raw attribution is stored
on the lead / enquiry code, so these rules can be refined later without a schema
change (A12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from urllib.parse import urlsplit

from app.models.lead import URLISH_MAX, UTM_MAX

# Channel values (mirrors app.models.lead.LEAD_CHANNELS).
META_ADS = "meta_ads"
GOOGLE_ADS = "google_ads"
GOOGLE_BUSINESS_PROFILE = "google_business_profile"
GOOGLE_SEARCH = "google_search"
INSTAGRAM_ORGANIC = "instagram_organic"
FACEBOOK_ORGANIC = "facebook_organic"
OTHER_REFERRAL = "other_referral"
DIRECT = "direct"
MANUAL = "manual"

_META_SOURCES = {"facebook", "fb", "instagram", "ig", "meta"}
_META_PAID_MEDIUMS = {"paid", "cpc", "ppc", "ad", "ads", "paid_social"}
_GOOGLE_PAID_MEDIUMS = {"cpc", "ppc", "paid"}
_INSTAGRAM_SOURCES = {"instagram", "ig"}
_FACEBOOK_SOURCES = {"facebook", "fb"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "l.instagram.com"}
_FACEBOOK_HOSTS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "l.facebook.com",
    "lm.facebook.com",
}
# google.com, www.google.com, google.co.in, www.google.com.au, ...
_GOOGLE_HOST = re.compile(r"^(www\.)?google\.[a-z]{2,3}(\.[a-z]{2})?$")


@dataclass(frozen=True)
class Attribution:
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    fbclid: str | None = None
    gclid: str | None = None
    landing_path: str | None = None
    referrer: str | None = None
    landed_at: datetime | None = None

    def is_empty(self) -> bool:
        return all(
            getattr(self, f) is None
            for f in (
                "utm_source", "utm_medium", "utm_campaign", "utm_content",
                "utm_term", "fbclid", "gclid", "landing_path", "referrer",
            )
        )


def _clean_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s[:limit] if s else None


def _strip_query(value: object) -> str | None:
    """Drop any query string and fragment, keep at most URLISH_MAX characters."""
    s = _clean_text(value, 10_000)
    if s is None:
        return None
    s = s.split("#", 1)[0].split("?", 1)[0].strip()
    return s[:URLISH_MAX] if s else None


def host_of(url: str | None) -> str | None:
    """Lower-case host of a URL, or None when it has no usable host."""
    if not url:
        return None
    try:
        host = urlsplit(url if "//" in url else f"//{url}").hostname
    except ValueError:
        return None
    return host.lower() if host else None


def clean_attribution(
    raw: object, *, own_hosts: frozenset[str] = frozenset()
) -> Attribution | None:
    """Normalise client-supplied attribution; None when nothing usable remains.

    ``raw`` may be a mapping or an object with the attribution attributes (e.g. a
    Pydantic model). A referrer on one of ``own_hosts`` (the Customer_Site's own
    domains) is dropped, since internal navigation is not a source.
    """
    if raw is None:
        return None

    def get(name: str) -> object:
        if isinstance(raw, dict):
            return raw.get(name)
        return getattr(raw, name, None)

    landed_at = get("landed_at")
    a = Attribution(
        utm_source=_clean_text(get("utm_source"), UTM_MAX),
        utm_medium=_clean_text(get("utm_medium"), UTM_MAX),
        utm_campaign=_clean_text(get("utm_campaign"), UTM_MAX),
        utm_content=_clean_text(get("utm_content"), UTM_MAX),
        utm_term=_clean_text(get("utm_term"), UTM_MAX),
        fbclid=_clean_text(get("fbclid"), URLISH_MAX),
        gclid=_clean_text(get("gclid"), URLISH_MAX),
        landing_path=_strip_query(get("landing_path")),
        referrer=_strip_query(get("referrer")),
        landed_at=landed_at if isinstance(landed_at, datetime) else None,
    )
    ref_host = host_of(a.referrer)
    if a.referrer is not None and (ref_host is None or ref_host in own_hosts):
        a = replace(a, referrer=None)
    return None if a.is_empty() else a


def derive_channel(a: Attribution | None) -> str:
    """Channel for a website/form lead. First matching rule wins (R17.9)."""
    if a is None or a.is_empty():
        return DIRECT
    source = (a.utm_source or "").lower()
    medium = (a.utm_medium or "").lower()
    ref_host = host_of(a.referrer)

    if a.fbclid or (source in _META_SOURCES and medium in _META_PAID_MEDIUMS):
        return META_ADS
    if a.gclid or (source == "google" and medium in _GOOGLE_PAID_MEDIUMS):
        return GOOGLE_ADS
    if source == "google" and medium == "gbp":
        return GOOGLE_BUSINESS_PROFILE
    if ref_host and _GOOGLE_HOST.match(ref_host):
        return GOOGLE_SEARCH
    if source in _INSTAGRAM_SOURCES or ref_host in _INSTAGRAM_HOSTS:
        return INSTAGRAM_ORGANIC
    if source in _FACEBOOK_SOURCES or ref_host in _FACEBOOK_HOSTS:
        return FACEBOOK_ORGANIC
    if ref_host or source:
        return OTHER_REFERRAL
    return DIRECT


def manual_channel(source: str) -> str:
    """Channel for a staff-entered lead without an enquiry code (R4.7)."""
    return META_ADS if source == "whatsapp_ad" else MANUAL
