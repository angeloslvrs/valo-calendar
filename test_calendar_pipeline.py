import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from icalendar import Calendar
import main
from scraper import Match, discover_vct_teams, is_vct_match


class CalendarPipelineTests(unittest.TestCase):
    def test_champions_generates_subscribable_calendars(self):
        match = Match(123, "https://www.vlr.gg/123/test", datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
                      "Sentinels", "Fnatic", "Valorant Champions 2026", "Group Stage")
        teams = discover_vct_teams([match])
        self.assertEqual(len(teams), 2)
        self.assertTrue(all(t.region == "International" for t in teams))
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            try:
                os.chdir(directory)
                with patch.object(main, "scrape_matches", return_value=[match]), \
                     patch.object(main, "fetch_accurate_times"), \
                     patch.object(main, "fetch_team_logos", return_value={}):
                    main.main()
                payload = json.loads(Path("ics/teams.json").read_text())
                self.assertEqual(len(payload["teams"]), 2)
                for team in payload["teams"]:
                    calendar = Calendar.from_ical(Path("ics", team["ics_file"]).read_bytes())
                    events = calendar.walk("VEVENT")
                    self.assertEqual(len(events), 1)
                    self.assertEqual(str(events[0]["SUMMARY"]), "Sentinels vs Fnatic")
                    self.assertEqual(events[0].decoded("DTSTART"), match.start)
            finally:
                os.chdir(previous)

    def test_event_scope(self):
        for name in ("VCT 2026: Pacific Stage 2", "VCT 2026: Masters London", "Valorant Champions 2026"):
            with self.subTest(name=name):
                self.assertTrue(is_vct_match(name))
        for name in ("Valorant Champions 2025", "Game Changers 2026: Pacific", "Challengers 2026", "Valorant Champions 20260"):
            with self.subTest(name=name):
                self.assertFalse(is_vct_match(name))


if __name__ == "__main__":
    unittest.main()
