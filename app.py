"""
Minimal web app for the Rhetorical Agent.

Anyone can open the page, paste a tweet URL or thread text, and get advice —
no Cursor required. Run with: flask --app app run (or python -m flask --app app run).

Environment:
  OPENAI_API_KEY   – required for LLM (or set llm.provider to use another backend later)
  X_BEARER_TOKEN   – required only when user submits a tweet URL (for fetching the thread)
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Path to the Cursor skill; used to load system prompt.
SKILL_DIR = Path(__file__).resolve().parent / ".cursor" / "skills" / "rhetoric-x-reply-helper"
DEFAULT_QUESTION = "What's the smartest way to respond to this?"
TWEET_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+",
    re.IGNORECASE,
)


def load_system_prompt() -> str:
    """Load SKILL.md + reference.md as the LLM system prompt."""
    skill_path = SKILL_DIR / "SKILL.md"
    ref_path = SKILL_DIR / "reference.md"
    parts = []
    if skill_path.exists():
        parts.append(skill_path.read_text(encoding="utf-8"))
    if ref_path.exists():
        parts.append("\n\n---\n\n# Reference\n\n" + ref_path.read_text(encoding="utf-8"))
    return "\n".join(parts) if parts else "You advise on X (Twitter) crypto conversations. Be concise and practical."


def get_block_from_request() -> Tuple[str, Optional[str]]:
    """
    Parse JSON body: url or thread_text, optional context, voice.
    Returns (user_message_block, error).
    """
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    thread_text = (data.get("thread_text") or "").strip()
    context = (data.get("context") or "").strip()
    voice = (data.get("voice") or "").strip().lower()

    if url and thread_text:
        return "", "Send either url or thread_text, not both."
    if not url and not thread_text:
        return "", "Send either url or thread_text."

    if url:
        # Fetch thread via existing module
        try:
            from x_thread_fetcher import (
                fetch_tweet_and_replies,
                format_thread_for_agent,
                XApiError,
            )
        except ImportError as e:
            return "", f"URL fetch not available: {e}"
        try:
            op, replies = fetch_tweet_and_replies(url, max_replies=5)
            block = format_thread_for_agent(
                op, replies,
                our_context=context or None,
                voice=voice or None,
            )
        except Exception as e:
            return "", str(e)
    else:
        lines = [thread_text]
        if context:
            lines.append("")
            lines.append("OUR CONTEXT:")
            lines.append(context)
        if voice:
            lines.append(f"VOICE: {voice}")
        block = "\n".join(lines).strip() + "\n"

    block = block.rstrip() + "\n\n" + DEFAULT_QUESTION + "\n"
    return block, None


def call_llm(system_prompt: str, user_message: str) -> str:
    """Call OpenAI Chat Completions; return assistant content or raise."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("Install openai: pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in the environment")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=os.environ.get("RHETORICAL_LLM_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=2048,
    )
    choice = resp.choices and resp.choices[0]
    if not choice or not choice.message:
        raise RuntimeError("Empty response from LLM")
    return (choice.message.content or "").strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rhetorical Agent</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 0 auto; padding: 1.5rem; }
    h1 { font-size: 1.25rem; margin-bottom: 0.5rem; }
    p.sub { color: #555; font-size: 0.9rem; margin-bottom: 1.25rem; }
    label { display: block; font-weight: 600; margin-bottom: 0.35rem; }
    input, textarea, select { width: 100%; padding: 0.5rem; margin-bottom: 1rem; border: 1px solid #ccc; border-radius: 4px; }
    textarea { min-height: 120px; resize: vertical; }
    button { background: #111; color: #fff; border: none; padding: 0.6rem 1.2rem; border-radius: 4px; cursor: pointer; font-size: 1rem; }
    button:hover { background: #333; }
    button:disabled { background: #999; cursor: not-allowed; }
    #result { margin-top: 1.5rem; padding: 1rem; background: #f5f5f5; border-radius: 4px; white-space: pre-wrap; }
    #error { color: #c00; margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Rhetorical Agent</h1>
  <p class="sub">Paste a tweet URL or thread text. Get advice on the smartest way to respond (X crypto conversations, AgenC/RaiderKit-aware).</p>
  <form id="form">
    <label for="input">Tweet URL or thread text</label>
    <textarea id="input" name="input" placeholder="https://x.com/user/status/123... or paste OP and replies here"></textarea>
    <label for="context">Your context (optional)</label>
    <input type="text" id="context" name="context" placeholder="e.g. We're a research account for protocol X">
    <label for="voice">Voice (optional)</label>
    <select id="voice" name="voice">
      <option value="">Random</option>
      <option value="fuckhead">fuckhead</option>
      <option value="didion">didion</option>
      <option value="carver">carver</option>
      <option value="thompson">thompson</option>
      <option value="oconnor">oconnor</option>
      <option value="hammett">hammett</option>
    </select>
    <button type="submit" id="btn">Get advice</button>
  </form>
  <div id="result"></div>
  <div id="error"></div>
  <script>
    const form = document.getElementById('form');
    const input = document.getElementById('input');
    const context = document.getElementById('context');
    const voice = document.getElementById('voice');
    const result = document.getElementById('result');
    const errEl = document.getElementById('error');
    const btn = document.getElementById('btn');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errEl.textContent = '';
      result.textContent = 'Thinking…';
      btn.disabled = true;
      const text = input.value.trim();
      const isUrl = /^https?:\\/\\/(www\\.)?(twitter\\.com|x\\.com)\\/.+/i.test(text);
      const body = isUrl ? { url: text } : { thread_text: text };
      if (context.value.trim()) body.context = context.value.trim();
      if (voice.value) body.voice = voice.value;
      try {
        const r = await fetch('/advice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await r.json();
        if (!r.ok) { errEl.textContent = data.error || r.statusText; result.textContent = ''; }
        else { result.textContent = data.advice || ''; }
      } catch (e) { errEl.textContent = e.message || 'Request failed'; result.textContent = ''; }
      btn.disabled = false;
    });
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/advice", methods=["POST"])
def advice():
    block, err = get_block_from_request()
    if err:
        return jsonify({"error": err}), 400
    try:
        system_prompt = load_system_prompt()
        advice_text = call_llm(system_prompt, block)
        return jsonify({"advice": advice_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """
    AgenC daemon compatibility: POST { "messages": [ { "role", "content" } ] }
    Returns { "content": "..." }. Used when the daemon is configured with
    llm.provider = "rhetorical" and llm.baseUrl = this app's URL.
    """
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    if not isinstance(messages, list) or len(messages) == 0:
        return jsonify({"error": "messages array required"}), 400
    # Build a single block from the conversation for the rhetoric prompt
    lines = []
    for m in messages:
        role = (m.get("role") or "user").lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            lines.append("CONTEXT: " + content)
        elif role == "user":
            lines.append("USER: " + content)
        elif role == "assistant":
            lines.append("ASSISTANT: " + content)
    if not lines:
        return jsonify({"error": "No message content"}), 400
    block = "\n\n".join(lines)
    if "smartest way to respond" not in block.lower() and "how should" not in block.lower():
        block = block.rstrip() + "\n\n" + DEFAULT_QUESTION
    try:
        system_prompt = load_system_prompt()
        reply = call_llm(system_prompt, block)
        return jsonify({"content": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
