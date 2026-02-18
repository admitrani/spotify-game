# Spotify Guessing Game (CLI)

A portfolio-friendly Python CLI game that turns your saved Spotify tracks into a song guessing challenge.

## What It Does

- Authenticates with Spotify using OAuth and token caching (`.spotifycache`)
- Pulls your full saved library with Spotify pagination (50/page until complete)
- Caches normalized track metadata in `library_data.json` for fast startup
- Plays 15-second random snippets on your active Spotify device
- Shows non-cropped song/artist options in a cleaner CLI layout
- Renders album artwork as ASCII in the terminal (best effort)
- Uses a live countdown timer and ends the game if time runs out
- Writes run metrics to `game_history.jsonl` for lightweight analytics

## Quick Start

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your env file:

```bash
cp .env.example .env
```

4. Fill `.env` with your Spotify app credentials.

5. In your Spotify Developer app settings, add the same redirect URI as in `.env`.

6. Run:

```bash
python3 main.py
```

## OAuth Notes

- First run requires authorization.
- After that, refresh/access tokens are reused from `.spotifycache`, so you do not re-auth every run.
- If Spotify requires secure redirects for your app, use:
  - `https://127.0.0.1:8888/callback`

## Useful Commands

```bash
# Re-sync full saved library from Spotify
python3 main.py --refresh-library

# Customize snippet length
python3 main.py --snippet-seconds 15

# Limit game length
python3 main.py --max-rounds 10

# Disable artwork rendering
python3 main.py --no-artwork
```

## Outputs

- `library_data.json`: local cached library snapshot
- `game_history.jsonl`: one JSON record per game run (score, accuracy, duration, etc.)
