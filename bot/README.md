# MeetFlow-AI Meeting Bot

A Python CLI tool that joins Microsoft Teams meetings and scrapes **real-time captions** directly from the browser DOM. No audio capture, no Whisper, no diarization — Teams' built-in captions already include speaker names.

The bot uses a **vision-guided approach** — instead of hardcoded CSS selectors, it sends browser screenshots to a Groq vision model that decides what to click, making the join flow resilient to Teams UI changes. A static Playwright automation runs first as the fast path, with Groq vision as fallback.

## How It Works

```
Teams Meeting URL
       │
       ▼
┌──────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│ Groq Vision  │     │ Caption Scraper      │     │ Pipeline             │
│ + Playwright │     │                      │     │                      │
│              │     │ Enables captions     │     │ Writes finalized     │
│ Joins the    │     │ MutationObserver     │     │ captions to disk     │
│ meeting      │     │ watches DOM changes  │     │                      │
│ automatically│     │ Extracts speaker +   │     │ Optionally forwards  │
└──────────────┘     │ text from captions   │────►│ to app server via    │
                     │     │                │     │ HTTP                 │
                     │     ▼                │     │     │                │
                     │ asyncio.Queue        │     │     ▼                │
                     └──────────────────────┘     │ transcript.json      │
                                                  │ transcript.txt       │
                                                  └──────────────────────┘
```

## Output Files

| File | Description |
|------|-------------|
| `transcript.json` | Machine-readable array of segments: `{speaker, text, start, timestamp_human}` |
| `transcript.txt` | Human-readable transcript: `[HH:MM:SS] Speaker: text` |
| `bot.log` | Full debug log for the session |

## Caption Scraping Approach

Instead of capturing audio and running local speech-to-text + diarization models, this bot:

1. **Enables Teams captions** — clicks the "More" menu and enables "Live captions"
2. **Injects a MutationObserver** — watches `div[data-tid="closed-caption-renderer-wrapper"]` for new caption nodes
3. **Extracts speaker + text** — reads `span[data-tid="author"]` for the speaker and the caption text from sibling elements
4. **Detects finalized captions** — waits for terminal punctuation (`.`, `!`, `?`) before emitting
5. **Deduplicates** — strips punctuation and compares to the last emitted caption to avoid partial-update spam

This approach is based on the [Recall.ai browser automation method](https://www.recall.ai/post/how-to-build-a-microsoft-teams-bot).

> **⚠ Brittleness Warning:** Caption scraping relies on Teams' DOM structure. Microsoft may change selectors without notice. The user agent is locked to Chrome 125 to reduce DOM variability.

## Prerequisites

1. **Python 3.11+** with `uv` or `pip`
2. **Groq API key** (free tier at [console.groq.com](https://console.groq.com))
3. **Playwright** (browser automation — installs Chromium automatically)

### Setup

```bash
# 1. Install dependencies
uv sync

# 2. Install Playwright browsers
uv run playwright install chromium

# 3. Copy env file
cp .env.example .env
# Edit .env with your Groq API key
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for vision-guided joining |
| `GROQ_VISION_MODEL` | No | Vision model (default: `meta-llama/llama-4-scout-17b-16e-instruct`) |
| `BOT_DISPLAY_NAME` | No | Name shown in Teams (default: `Meeting Recorder`) |
| `OUTPUT_DIR` | No | Where to write transcripts (default: `./output`) |
| `APP_SERVER_URL` | No | URL to forward captions via HTTP (e.g., `http://localhost:8080`) |

## Usage

```bash
# Join a meeting by URL
python main.py --url "https://teams.microsoft.com/l/meetup-join/..."

# Custom display name
python main.py --url "..." --display-name "MeetFlow Bot"

# Custom output directory
python main.py --url "..." --output-dir ./my_meeting
```

## Docker

```bash
# Build
docker build -t meetflow-bot .

# Run
docker run --rm \
  --env-file .env \
  meetflow-bot \
  --url "https://teams.microsoft.com/l/meetup-join/..."
```

## Testing

```bash
uv run pytest tests/ -v
```

## Project Structure

```
bot/
├── main.py                 # CLI entry point
├── pipeline.py             # Reads caption queue → writes to disk
├── bot/
│   ├── __init__.py
│   └── joiner.py           # Vision-guided Teams meeting joiner (Playwright + Groq)
├── captions/
│   ├── __init__.py
│   └── captions.py         # MutationObserver-based caption scraper
├── output/
│   ├── __init__.py
│   └── writer.py           # JSON + TXT transcript writer
├── tests/
│   └── test_writer.py      # Writer tests
├── Dockerfile
├── entrypoint.sh
├── pyproject.toml
├── requirements.txt
└── .env.example
```

## Limitations

- **English only** (Teams captions default to English)
- **Single meeting at a time** per bot instance
- **DOM brittleness** — Teams UI changes may break caption selectors
- **No audio recording** — if you need raw audio, this bot doesn't capture it
- **Caption quality** — depends on Teams' built-in speech recognition
