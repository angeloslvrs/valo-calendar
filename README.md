# Valo Calendar

Generate subscribable ICS calendars for Valorant esports matches, sourced from [vlr.gg](https://www.vlr.gg).

## Features

- Per-team ICS calendar generation
- Clean event format: **Title** = matchup, **Location** = tournament, **Description** = stage + vlr.gg link
- Static HTML page with Google Calendar / Apple Calendar subscribe buttons
- Configurable team list

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Edit the `TEAMS` list in `main.py`, then run:

```bash
python3 main.py
```

ICS files are written to `ics/`. Serve `index.html` to access the subscription page.

## Calendar Event Format

```
SUMMARY:  Team A vs Team B
LOCATION: VCT 2026: Pacific Stage 1
DESCRIPTION: Group Stage–Week 3
             https://www.vlr.gg/644666/...
```
