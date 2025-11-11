import json
import os


def find_candidate_seconds(client, timestamped_text: str) -> dict:
    """Ask GPT to propose suspicious timestamps from transcript."""
    prompt = f"""
You are a QA assistant. Analyze this timestamped transcript and identify the likely moments where a bug or unexpected behavior occurs.
Return STRICT JSON with:
{{
  "candidates": [{{ "second": <int>, "reason": "<why this moment is suspicious>" }}],
  "notes": "<short high-level synopsis>"
}}

Transcript (timestamped):
{timestamped_text}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a meticulous QA Bug Triage assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except Exception:
        start_idx = raw.find("{")
        end_idx = raw.rfind("}")
        fp_slice = raw[start_idx:end_idx+1] if start_idx != - \
            1 and end_idx != -1 else "{}"
        try:
            return json.loads(fp_slice)
        except Exception:
            return {"candidates": [], "notes": "Parsing failed"}


def analyze_with_transcript(client, timestamped_text: str) -> list:
    """Analyze transcript and return list of bug dicts with time ranges."""
    instructions = """
You are analyzing a timestamped transcript from a QA video to identify bugs.

Tasks:
1) Identify distinct bugs/issues from the transcript.
2) For each bug, determine the time range where it occurs (start_sec and end_sec).
3) For each bug, produce a JSON entry with:
   - summary: Brief bug title
   - description: Expected vs actual behavior, steps to reproduce
   - priority: High/Medium/Low
   - start_sec: Start time in seconds (float)
   - end_sec: End time in seconds (float)

Output STRICT JSON array only. Example:
[
  {
    "summary": "Login button unresponsive",
    "description": "Expected: ... Actual: ... Steps: ...",
    "priority": "High",
    "start_sec": 9.0,
    "end_sec": 12.0
  }
]
"""
    messages = [
        {"role": "system", "content": "You are an expert QA Bug Reporter that analyzes transcripts to identify bugs and their time ranges."},
        {
            "role": "user",
            "content": f"{instructions.strip()}\n\nTranscript (timestamped):\n{timestamped_text[:6000]}"
        }
    ]
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2
    )
    raw = resp.choices[0].message.content or "[]"
    try:
        return json.loads(raw)
    except Exception:
        start_idx = raw.find("[")
        end_idx = raw.rfind("]")
        slice_ = raw[start_idx:end_idx+1] if start_idx != - \
            1 and end_idx != -1 else "[]"
        try:
            return json.loads(slice_)
        except Exception:
            return []
