#!/usr/bin/env python3
"""Valorant Calendar Generator — scrape vlr.gg and produce per-team ICS files."""

from scraper import scrape_matches, filter_by_teams
from calendar_generator import write_ics_files

# Teams to generate calendars for (easy to extend)
TEAMS = [
    "Team Secret",
    "Sentinels",
]

PAGES_TO_SCRAPE = 5


def main():
    print(f"[*] Scraping {PAGES_TO_SCRAPE} pages from vlr.gg/matches ...")
    matches = scrape_matches(pages=PAGES_TO_SCRAPE)
    print(f"[*] Found {len(matches)} total upcoming matches")

    team_matches = filter_by_teams(matches, TEAMS)

    for team, tmatches in team_matches.items():
        print(f"    {team}: {len(tmatches)} matches")

    files = write_ics_files(team_matches, output_dir="ics")

    if files:
        print(f"\n[*] Generated {len(files)} calendar file(s) in ics/")
    else:
        print("\n[!] No calendar files generated — teams may not have upcoming matches on scraped pages")
        print("    Try increasing PAGES_TO_SCRAPE in main.py")


if __name__ == "__main__":
    main()
