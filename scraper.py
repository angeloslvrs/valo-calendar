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


@dataclass
class Match:
    id: int
    url: str
    start: datetime
    home_team: str
    away_team: str
    event: str
    series: str


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
