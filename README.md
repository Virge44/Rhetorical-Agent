## Rhetorical Agent for X (Crypto)

This project hosts a Cursor-based rhetorical assistant designed to help craft effective responses to cryptocurrency conversations on X (Twitter).

The core of the project is a Cursor skill that:

- Analyzes the original post (and optionally replies) in a crypto-related X thread.
- Infers how the thread will be perceived by both the person you're replying to and the broader audience of lurkers and onlookers.
- Suggests a smart way to respond, with concrete example phrasings, without exposing rhetorical theory jargon.

The assistant speaks in a **Fuckhead-inspired voice** (after Denis Johnson’s character):

- Colloquial, a little raw; no corporate polish.
- Darkly observant—notices who’s performing for whom, what the incentives are.
- Straight about trade-offs; blunt when it helps; a little dark humor or understatement is fine.
- Wounded but paying attention; long-term credibility over short-term dunks.

**Easiest for everyone (no Cursor):** Run the **web app** so anyone can open a link, paste a tweet URL or thread text, and get advice in the browser.

```bash
cd "Rhetorical Agent"
pip install -r requirements.txt
export OPENAI_API_KEY="your_openai_key"
export X_BEARER_TOKEN="your_x_bearer_token"   # only needed when users paste tweet URLs
flask --app app run --host 0.0.0.0 --port 5000
```

Open http://localhost:5000 (or your server’s URL). Users paste a tweet URL or the thread text, optionally add context/voice, click **Get advice**, and see the response. No Cursor, no Python, no terminal — just a browser. You can deploy this (e.g. Railway, Fly.io, or a small VPS) and share the link.

---

If you use **Cursor** and have the skill loaded:

**Streamlined:** From the project folder, run:
```bash
export X_BEARER_TOKEN="your_x_api_bearer_token"
python x_thread_fetcher.py "https://x.com/user/status/123..."
```
The script fetches the thread, formats it for the agent, and **appends the question** so you can copy the output and paste it **once** into Cursor; the agent will answer with analysis and example replies in one go. Optional: `--max-replies 5`, `--context "..."`, `--voice didion`, `--no-question`.

**Manual flow:**
1. Paste the OP (and optionally a few notable replies) from X.
2. Briefly describe who they are speaking as (e.g. "research account for protocol X").
3. Ask: "What’s the smartest way to respond?"
4. Receive a conversational analysis and several candidate reply lines to adapt and post.

See `.cursor/skills/rhetoric-x-reply-helper/SKILL.md` for the agent’s detailed behavior and voice specification.

