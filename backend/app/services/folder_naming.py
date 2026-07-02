"""Folder naming follows the lab convention seen across 372 real folders:
    MM-DD_<location>_<site>_<treatment>_<interval>
e.g.  09-03_RG_1_C_1
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# Letters/digits, plus parens because real lab folders include forms like
# ``C(S)`` for "control with scent" treatments.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9()]+$")
_DATE_RE = re.compile(r"^\d{2}-\d{2}$")


class FolderNameError(ValueError):
    pass


def _clean(value: str, field: str) -> str:
    v = (value or "").strip()
    if not v:
        raise FolderNameError(f"{field} is required")
    if not _TOKEN_RE.match(v):
        raise FolderNameError(
            f"{field} '{value}' must contain only letters and digits"
        )
    return v


def _clean_date(value: str) -> str:
    v = (value or "").strip()
    if _DATE_RE.match(v):
        return v
    try:
        dt = datetime.strptime(v, "%Y-%m-%d")
        return dt.strftime("%m-%d")
    except ValueError:
        pass
    raise FolderNameError(
        f"date '{value}' must be MM-DD or YYYY-MM-DD"
    )


def build_folder_name(
    date: str,
    location: str,
    site: str,
    treatment: str,
    interval: str,
) -> str:
    return "_".join(
        [
            _clean_date(date),
            _clean(location, "location"),
            _clean(site, "site"),
            _clean(treatment, "treatment"),
            _clean(interval, "interval"),
        ]
    )


def parse_folder_name(name: str) -> Optional[dict]:
    """Try to split ``MM-DD_<loc>_<site>_<treatment>_<interval>`` into fields.

    Returns ``None`` if the name doesn't match the convention. We split on
    underscores and require exactly 5 parts; when treatments themselves
    contain parens (e.g. ``C(S)``) underscore-splitting still works because
    parens are inside the token, not separators.
    
    Also supports alternate user convention: ``loc-site-trt-int-date`` or
    ``loc_site_trt_int_date`` where date is like ``m.d.yy``.
    """
    name = name.strip()
    
    # 1. Standard format: MM-DD_loc_site_trt_int
    parts = name.split("_")
    if len(parts) == 5 and _DATE_RE.match(parts[0]):
        date, location, site, treatment, interval = parts
        if all(_TOKEN_RE.match(v) for v in (location, site, treatment, interval)):
            return {
                "date": date,
                "location": location,
                "site": site,
                "treatment": treatment,
                "interval": interval,
            }

    # 2. Alternate format: loc_site_trt_int_date OR loc-site-trt-int-date
    alt_parts = re.split(r"[-_]", name)
    if len(alt_parts) == 5:
        location, site, treatment, interval, raw_date = alt_parts
        if all(_TOKEN_RE.match(v) for v in (location, site, treatment, interval)):
            # Parse date like '4.2.24' or '1.24.24'
            date_parts = raw_date.split(".")
            if len(date_parts) == 3:
                try:
                    m, d, _ = date_parts
                    formatted_date = f"{int(m):02d}-{int(d):02d}"
                    return {
                        "date": formatted_date,
                        "location": location,
                        "site": site,
                        "treatment": treatment,
                        "interval": interval,
                    }
                except ValueError:
                    pass

    return None
