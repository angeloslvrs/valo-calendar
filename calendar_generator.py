from datetime import timedelta

from icalendar import Calendar, Event

from scraper import Match


def _sanitize_filename(name: str) -> str:
    """Convert a team name to a safe filename slug."""
    return name.lower().replace(" ", "-").replace(".", "")


def generate_ics(team_name: str, matches: list[Match]) -> str:
    """Generate an ICS calendar string for a team's matches."""
    cal = Calendar()
    cal.add("prodid", "-//ValoCalendar//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"{team_name} - Valorant Matches")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    for match in matches:
        event = Event()
        event.add("uid", f"vlr-{match.id}@valo-calendar")
        event.add("dtstamp", match.start)
        event.add("dtstart", match.start)
        event.add("dtend", match.start + timedelta(hours=2))
        event.add("summary", f"{match.home_team} vs {match.away_team}")
        event.add("location", match.event)
        if match.series:
            event.add("description", f"{match.series}\n{match.url}")
        else:
            event.add("description", match.url)
        cal.add_component(event)

    return cal.to_ical().decode("utf-8")


def write_ics_files(team_matches: dict[str, list[Match]], output_dir: str = "ics") -> dict[str, str]:
    """Write ICS files for each team. Returns dict of team -> filename."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    files = {}
    for team, matches in team_matches.items():
        if not matches:
            print(f"[!] No matches found for {team}, skipping ICS generation")
            continue

        filename = f"{_sanitize_filename(team)}.ics"
        filepath = os.path.join(output_dir, filename)
        ics_content = generate_ics(team, matches)

        with open(filepath, "w") as f:
            f.write(ics_content)

        files[team] = filename
        print(f"[+] {filepath}: {len(matches)} matches")

    return files
