from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, NavigableString

VLR_BASE = "https://www.vlr.gg"
MATCHES_URL = f"{VLR_BASE}/matches"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# vlr.gg renders times based on the requester's IP geolocation.
# Use Asia/Manila (PHT, UTC+8) to match the displayed times.
VLR_TZ = ZoneInfo("Asia/Manila")

# VCT 2026 event name patterns and their regions
VCT_REGION_PATTERNS = [
    ("Americas", re.compile(r"VCT\s+2026.*Americas", re.IGNORECASE)),
    ("Pacific",  re.compile(r"VCT\s+2026.*Pacific",  re.IGNORECASE)),
    ("EMEA",     re.compile(r"VCT\s+2026.*EMEA",     re.IGNORECASE)),
    ("China",    re.compile(r"VCT\s+2026.*China",     re.IGNORECASE)),
    # Generic VCT 2026 fallback (Champions, Masters, etc.)
    ("International", re.compile(r"VCT\s+2026",       re.IGNORECASE)),
]


@dataclass
class Match:
    id: int
    url: str
    start: datetime
    home_team: str
    away_team: str
    event: str
    series: str


@dataclass
class TeamInfo:
    name: str
    slug: str          # filename-safe slug, e.g. "sentinels"
    region: str
    logo_url: str      # absolute URL or empty string


def _own_text(element) -> str:
    """Get only the direct text of an element, not its children's text."""
    return "".join(
        child.strip() for child in element.children if isinstance(child, NavigableString)
    ).strip()


def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse vlr.gg date + time strings into a UTC datetime."""
    if not date_str or not time_str or time_str.upper() == "TBD":
        return None

    # Clean up date string (remove "Today" suffix)
    date_str = re.sub(r"\s*Today\s*$", "", date_str).strip()

    combined = f"{date_str} {time_str}"
    try:
        dt = datetime.strptime(combined, "%a, %B %d, %Y %I:%M %p")
        dt = dt.replace(tzinfo=VLR_TZ)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_match(match_el, current_date: str) -> Match | None:
    """Parse a single match element into a Match object."""
    href = match_el.get("href", "")
    parts = href.strip("/").split("/")
    if not parts:
        return None
    try:
        match_id = int(parts[0])
    except ValueError:
        return None

    # Time
    time_el = match_el.select_one("div.match-item-time")
    time_str = time_el.get_text(strip=True) if time_el else ""

    start = _parse_datetime(current_date, time_str)
    if not start:
        return None

    # Teams
    team_els = match_el.select("div.match-item-vs-team-name div.text-of")
    if len(team_els) < 2:
        return None
    home_team = team_els[0].get_text(strip=True)
    away_team = team_els[1].get_text(strip=True)

    # Event + series
    event_el = match_el.select_one("div.match-item-event.text-of")
    event = _own_text(event_el) if event_el else ""
    series_el = match_el.select_one("div.match-item-event-series.text-of")
    series = series_el.get_text(strip=True) if series_el else ""

    return Match(
        id=match_id,
        url=f"{VLR_BASE}{href}",
        start=start,
        home_team=home_team,
        away_team=away_team,
        event=event,
        series=series,
    )


def scrape_matches(pages: int = 5) -> list[Match]:
    """Scrape upcoming matches from vlr.gg across multiple pages."""
    all_matches = []

    for page in range(1, pages + 1):
        url = f"{MATCHES_URL}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Failed to fetch page {page}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        container = soup.select_one("div.col.mod-1")
        if not container:
            print(f"[!] No match container found on page {page}")
            continue

        current_date = ""
        # Filter to only Tag elements (skip whitespace NavigableStrings)
        tags = [c for c in container.children if hasattr(c, "get")]

        for tag in tags:
            class_str = " ".join(tag.get("class", []))

            if "wf-label" in class_str:
                current_date = _own_text(tag).strip()

            elif "wf-card" in class_str and "mod-header" not in class_str:
                match_items = tag.select("a.wf-module-item.match-item")
                for match_el in match_items:
                    m = _parse_match(match_el, current_date)
                    if m:
                        all_matches.append(m)

        # Be polite to vlr.gg
        if page < pages:
            time.sleep(1)

    return all_matches


def filter_by_teams(matches: list[Match], teams: list[str]) -> dict[str, list[Match]]:
    """Filter matches by team names (case-insensitive). Returns dict of team -> matches."""
    result = {team: [] for team in teams}

    for match in matches:
        home_lower = match.home_team.lower()
        away_lower = match.away_team.lower()
        for team in teams:
            team_lower = team.lower()
            if team_lower in home_lower or team_lower in away_lower:
                result[team].append(match)

    return result


def is_vct_match(event: str) -> bool:
    """Return True if the event name looks like a VCT 2026 league match."""
    return bool(re.search(r"VCT\s+2026", event, re.IGNORECASE))


def extract_region(event: str) -> str:
    """Extract the VCT region from an event name. Returns one of the known regions."""
    for region, pattern in VCT_REGION_PATTERNS:
        if pattern.search(event):
            return region
    return "International"


def _make_slug(name: str) -> str:
    """Convert a team name to a filename-safe ASCII slug."""
    import unicodedata
    # Normalize unicode to closest ASCII (e.g. Ü -> U, É -> E)
    slug = unicodedata.normalize("NFKD", name)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


_PLACEHOLDER_LOGO_PATHS = {"/img/vlr/tmp/vlr.png", "/img/vlr-red.png"}


def _is_valid_logo(url: str) -> bool:
    """Return True only for absolute logo URLs we want to use."""
    if not url:
        return False
    if url.startswith("/"):
        return False
    return True


def fetch_team_logo(team_name: str, match_url: str) -> str:
    """Fetch a team logo URL from a match detail page."""
    try:
        resp = requests.get(match_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[!] Failed to fetch match page {match_url}: {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Match header has two team links — find the one matching our team name
    team_name_lower = team_name.lower()
    for link in soup.select("a.match-header-link"):
        name_el = link.select_one(".wf-title-med")
        if not name_el:
            continue
        if team_name_lower in name_el.get_text(strip=True).lower():
            img = link.select_one("img")
            if img and img.get("src"):
                src = img["src"].strip()
                if src.startswith("//"):
                    src = "https:" + src
                return src

    return ""


_SKIP_TEAM_NAMES = {"tbd", "tba", ""}


def discover_vct_teams(matches: list[Match]) -> list[TeamInfo]:
    """
    From a list of matches, find all unique VCT 2026 teams with their regions.
    Logo URLs are left empty — call fetch_team_logos() to fill them in.
    """
    seen: dict[str, TeamInfo] = {}  # slug -> TeamInfo

    for match in matches:
        if not is_vct_match(match.event):
            continue
        region = extract_region(match.event)

        for team_name in (match.home_team, match.away_team):
            if team_name.strip().lower() in _SKIP_TEAM_NAMES:
                continue
            slug = _make_slug(team_name)
            if not slug or slug in _SKIP_TEAM_NAMES:
                continue
            if slug not in seen:
                seen[slug] = TeamInfo(
                    name=team_name,
                    slug=slug,
                    region=region,
                    logo_url="",
                )

    # Sort by region then name for stable output
    return sorted(seen.values(), key=lambda t: (t.region, t.name))


def fetch_team_logos(
    teams: list[TeamInfo],
    matches: list[Match],
    cached: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Fetch logo URLs for all teams that don't already have one cached.
    Returns dict of slug -> logo_url.

    cached: existing slug->url mapping to avoid re-fetching.
    """
    cached = cached or {}
    result = dict(cached)

    # Build a quick lookup: team_slug -> list of match URLs involving that team
    slug_to_match_urls: dict[str, list[str]] = {}
    for match in matches:
        if not is_vct_match(match.event):
            continue
        for team_name in (match.home_team, match.away_team):
            slug = _make_slug(team_name)
            slug_to_match_urls.setdefault(slug, []).append(match.url)

    needs_fetch = [t for t in teams if t.slug not in result or not result[t.slug]]

    for i, team in enumerate(needs_fetch):
        match_urls = slug_to_match_urls.get(team.slug, [])
        if not match_urls:
            print(f"[!] No match URLs found for {team.name}, skipping logo")
            result[team.slug] = ""
            continue

        print(f"[~] Fetching logo for {team.name} ({i+1}/{len(needs_fetch)}) ...")
        logo = fetch_team_logo(team.name, match_urls[0])
        if not _is_valid_logo(logo):
            logo = ""
        result[team.slug] = logo
        if logo:
            print(f"    -> {logo}")
        else:
            print(f"    -> not found")

        time.sleep(0.75)  # polite delay

    return result
