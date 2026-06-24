# How to Use the MeetFlow Bot

The MeetFlow bot joins Microsoft Teams meetings automatically and scrapes real-time captions directly from the browser window. It writes these captions to a JSON and text file.

## Prerequisites

1. **Python 3.11+** installed.
2. **uv** installed (`pip install uv`).
3. A **Groq API Key** (free at [console.groq.com](https://console.groq.com)).

## Setup

1. Open your terminal in the `bot/` directory.
2. Install the dependencies:
   ```bash
   uv sync
   ```
3. Install Playwright browsers (Chromium):
   ```bash
   uv run playwright install chromium
   ```
4. Copy the environment variables file and edit it:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and add your `GROQ_API_KEY`.

## Running the Bot Locally

To make the bot join a meeting, you just need the meeting URL:

```bash
uv run python main.py --url "https://teams.microsoft.com/l/meetup-join/..."
```

**Optional Arguments:**
- `--display-name "My Custom Name"`: Change the name the bot uses in the lobby.
- `--output-dir ./custom_folder`: Change where the transcript files are saved.

**What happens next?**
1. A Chromium browser window will open in the background (headless).
2. The bot will automatically navigate the Microsoft Teams lobby, bypass audio/video prompts, enter its name, and join.
3. Once inside, it automatically clicks "More" -> "Turn on live captions".
4. It silently scrapes the captions and writes them to `output/transcript.txt` and `output/transcript.json`.
5. When the meeting ends (or everyone leaves), the bot shuts down automatically.

## Running the Bot in Docker

If you prefer to run the bot cleanly inside a container without installing Python dependencies on your host:

1. Build the Docker image:
   ```bash
   docker build -t meetflow-bot .
   ```
2. Run the container:
   ```bash
   docker run --rm \
     --env-file .env \
     meetflow-bot \
     --url "https://teams.microsoft.com/l/meetup-join/..."
   ```

## Transcript Outputs

In the `output/` folder (or your custom directory), you will see:
- `transcript.txt`: A readable text file (e.g., `[0:00:12] Sarah: Hello world!`).
- `transcript.json`: A structured JSON file useful for feeding into an LLM or database.
- `bot.log`: The raw internal logs of the bot's decisions.
