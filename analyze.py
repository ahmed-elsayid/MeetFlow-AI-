"""
analyze.py -- Sends the meeting transcript to Groq (Llama 3.3 70B)
and returns a structured analysis dict.
"""

import os
import json
from groq import Groq

_SYSTEM_PROMPT = """\
You are a professional meeting analyst.
Analyze the meeting transcript and return a single JSON object with these exact keys:

{
  "title":        "<short meeting title, max 6 words>",
  "summary":      "<2-3 sentence executive summary>",
  "key_points":   ["<topic 1>", "<topic 2>", ...],
  "decisions":    ["<decision 1>", ...],
  "action_items": [{"task": "<what>", "owner": "<who>"}, ...]
}

"decisions" and "action_items" may be empty lists if none were found.
Return ONLY valid JSON -- no markdown fences, no explanation.
"""


def analyze(transcript: str) -> dict:
    """Analyze transcript with Groq Llama 3.3 70B. Returns structured dict."""
    if not transcript.strip():
        print("[WARN] Transcript is empty -- skipping analysis.")
        return {
            "title": "Empty Meeting",
            "summary": "No speech was detected in the recording.",
            "key_points": [],
            "decisions": [],
            "action_items": [],
        }

    print("[LLM] Analyzing with Groq / Llama 3.3 70B...")
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Meeting transcript:\n\n{transcript}"},
        ],
        temperature=0.1,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    n_actions = len(result.get("action_items", []))
    print(f"[LLM] '{result.get('title')}' | {n_actions} action item(s)")
    return result
