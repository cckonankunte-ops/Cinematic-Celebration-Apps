"""Channel rule and attribution clean-up (lead-crm R17.7-R17.9, R19.19).

One case per Channel, the rule priority, and Hypothesis properties for
determinism, sanitising and phone normalisation (design properties 1-3).
"""

from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.phone import normalize_indian_mobile
from app.models.lead import LEAD_CHANNELS, URLISH_MAX, UTM_MAX
from app.services.lead_channel import (
    Attribution,
    clean_attribution,
    derive_channel,
    manual_channel,
)

OWN = frozenset({"cinematiccelebration.in", "www.cinematiccelebration.in"})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"fbclid": "IwAR123"}, "meta_ads"),
        ({"utm_source": "Instagram", "utm_medium": "Paid"}, "meta_ads"),
        ({"utm_source": "fb", "utm_medium": "paid_social"}, "meta_ads"),
        ({"gclid": "Cj0KCQ"}, "google_ads"),
        ({"utm_source": "google", "utm_medium": "cpc"}, "google_ads"),
        ({"utm_source": "google", "utm_medium": "gbp"}, "google_business_profile"),
        ({"referrer": "https://www.google.com/"}, "google_search"),
        ({"referrer": "https://www.google.co.in/search?q=private+theatre"}, "google_search"),
        ({"referrer": "https://l.instagram.com/"}, "instagram_organic"),
        ({"utm_source": "instagram", "utm_medium": "bio"}, "instagram_organic"),
        ({"referrer": "https://m.facebook.com/"}, "facebook_organic"),
        ({"utm_source": "facebook"}, "facebook_organic"),
        ({"referrer": "https://www.justdial.com/x"}, "other_referral"),
        ({"utm_source": "newsletter"}, "other_referral"),
        ({"landing_path": "/book"}, "direct"),
        (None, "direct"),
        ({}, "direct"),
    ],
)
def test_channel_rules(raw: dict | None, expected: str) -> None:
    assert derive_channel(clean_attribution(raw, own_hosts=OWN)) == expected


def test_fbclid_beats_google_referrer_and_gclid() -> None:
    a = clean_attribution(
        {"fbclid": "x", "gclid": "y", "referrer": "https://www.google.com/"}
    )
    assert derive_channel(a) == "meta_ads"


def test_own_site_referrer_is_dropped() -> None:
    a = clean_attribution(
        {"referrer": "https://www.cinematiccelebration.in/locations?x=1"}, own_hosts=OWN
    )
    assert a is None
    assert derive_channel(a) == "direct"


def test_query_and_fragment_are_stripped() -> None:
    a = clean_attribution(
        {
            "landing_path": "/?utm_source=ig&phone=9876543210#top",
            "referrer": "https://l.instagram.com/?u=abc",
        }
    )
    assert a is not None
    assert a.landing_path == "/"
    assert a.referrer == "https://l.instagram.com/"


def test_manual_channel() -> None:
    assert manual_channel("whatsapp_ad") == "meta_ads"
    for source in ("whatsapp", "phone", "walk_in", "instagram_dm", "other"):
        assert manual_channel(source) == "manual"


def test_clean_attribution_accepts_objects_and_ignores_junk() -> None:
    class Raw:
        utm_source = "  google "
        utm_medium = 42  # not a string -> ignored
        gclid = ""

    a = clean_attribution(Raw())
    assert a == Attribution(utm_source="google")
    assert derive_channel(a) == "other_referral"


# --- properties -------------------------------------------------------------

_text = st.one_of(st.none(), st.text(max_size=600), st.integers())
_raw = st.fixed_dictionaries(
    {},
    optional={
        k: _text
        for k in (
            "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
            "fbclid", "gclid", "landing_path", "referrer",
        )
    },
)


@given(_raw)
def test_property_channel_total_and_fbclid_priority(raw: dict) -> None:
    a = clean_attribution(raw)
    assert derive_channel(a) in LEAD_CHANNELS
    with_fbclid = clean_attribution({**raw, "fbclid": "IwAR1"})
    assert derive_channel(with_fbclid) == "meta_ads"


@given(_raw)
def test_property_sanitised_values(raw: dict) -> None:
    a = clean_attribution(raw)
    if a is None:
        return
    for value in (a.landing_path, a.referrer):
        if value is not None:
            assert "?" not in value and "#" not in value
            assert len(value) <= URLISH_MAX
    for value in (a.utm_source, a.utm_medium, a.utm_campaign, a.utm_content, a.utm_term):
        assert value is None or len(value) <= UTM_MAX


_mobile = st.builds(
    lambda first, rest: first + rest,
    st.sampled_from("6789"),
    st.text(alphabet=string.digits, min_size=9, max_size=9),
)


@given(_mobile, st.sampled_from(["{m}", "+91 {m}", "+91{m}", "91{m}", "0{m}",
                                 "{a} {b}", "{a}-{b}", "+91-{a}-{b}", " 0{m} "]))
def test_property_phone_variants_normalise(mobile: str, fmt: str) -> None:
    raw = fmt.format(m=mobile, a=mobile[:5], b=mobile[5:])
    assert normalize_indian_mobile(raw) == mobile
