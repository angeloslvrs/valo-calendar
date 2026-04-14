#!/usr/bin/env python3
"""Valorant Calendar Generator — scrape vlr.gg and produce per-team ICS files."""

import json
import os

from scraper import (
    discover_vct_teams,
    fetch_team_logos,
    filter_by_teams,
    is_vct_match,
    scrape_matches,
)
from calendar_generator import write_ics_files

PAGES_TO_SCRAPE = 15
TEAMS_JSON_PATH = "ics/teams.json"

# Region logo URLs (VCT official assets on owcdn.net)
REGION_LOGOS = {
    "Americas":     "https://owcdn.net/img/640f5ab71dfbb.png",
    "Pacific":      "https://owcdn.net/img/640f5ae002674.png",
    "EMEA":         "https://owcdn.net/img/640f5acfb8dcb.png",
    "China":        "https://owcdn.net/img/6523a79282dc1.png",
    "International": "",
}


def load_cached_teams() -> dict:
    """Load existing teams.json if present, to avoid re-fetching logos."""
    if os.path.exists(TEAMS_JSON_PATH):
        with open(TEAMS_JSON_PATH) as f:
            return json.load(f)
    return {}


def main():
    print(f"[*] Scraping {PAGES_TO_SCRAPE} pages from vlr.gg/matches ...")
    matches = scrape_matches(pages=PAGES_TO_SCRAPE)
    print(f"[*] Found {len(matches)} total upcoming matches")

    vct_matches = [m for m in matches if is_vct_match(m.event)]
    print(f"[*] {len(vct_matches)} VCT 2026 matches")

    teams = discover_vct_teams(matches)
    print(f"[*] Discovered {len(teams)} VCT 2026 teams")

    # Load cached logo URLs to avoid hammering vlr.gg on every run
    cached_data = load_cached_teams()
    cached_logos = {t["slug"]: t.get("logo_url", "") for t in cached_data.get("teams", [])}

    logo_map = fetch_team_logos(teams, matches, cached=cached_logos)

    # Build teams.json
    os.makedirs("ics", exist_ok=True)
    teams_payload = {
        "teams": [
            {
                "name": t.name,
                "slug": t.slug,
                "region": t.region,
                "logo_url": logo_map.get(t.slug, ""),
                "region_logo_url": REGION_LOGOS.get(t.region, ""),
                "ics_file": f"{t.slug}.ics",
            }
            for t in teams
        ]
    }
    with open(TEAMS_JSON_PATH, "w") as f:
        json.dump(teams_payload, f, indent=2)
    print(f"[+] Wrote {TEAMS_JSON_PATH} ({len(teams)} teams)")

    # Generate ICS files (all VCT matches only)
    team_names = [t.name for t in teams]
    team_matches = filter_by_teams(vct_matches, team_names)

    for team, tmatches in team_matches.items():
        if tmatches:
            print(f"    {team}: {len(tmatches)} matches")

    files = write_ics_files(team_matches, output_dir="ics")

    if files:
        print(f"\n[*] Generated {len(files)} calendar file(s) in ics/")
    else:
        print("\n[!] No calendar files generated")
        print("    Try increasing PAGES_TO_SCRAPE in main.py")


if __name__ == "__main__":
    main()
