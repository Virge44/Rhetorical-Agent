import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

# Voice names must match the VOICE: lines used in the rhetoric skill.
VOICE_NAMES = ["fuckhead", "didion", "carver", "thompson", "oconnor", "hammett"]

TWEET_URL_REGEX = re.compile(
    r"""https?://(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(?P<id>\d+)""",
    re.IGNORECASE,
)


class XApiError(RuntimeError):
    """Raised when an X API request fails."""


def extract_tweet_id(url_or_id: str) -> str:
    """
    Extract a tweet ID from either:
    - A full tweet URL (twitter.com or x.com), or
    - A bare numeric ID string.

    Raises ValueError if it cannot find a valid ID.
    """
    url_or_id = url_or_id.strip()
    if url_or_id.isdigit():
        return url_or_id

    match = TWEET_URL_REGEX.search(url_or_id)
    if match:
        return match.group("id")

    raise ValueError(f"Could not extract tweet ID from input: {url_or_id!r}")


def _get_bearer_token(explicit_token: Optional[str] = None) -> str:
    """
    Resolve the X API bearer token.

    Order of precedence:
    1) Explicit argument.
    2) X_BEARER_TOKEN environment variable.

    Strips whitespace and removes any character that can't be sent in HTTP
    headers (Latin-1), e.g. smart quotes that sometimes get into the env var.
    """
    token = explicit_token or os.getenv("X_BEARER_TOKEN")
    if not token:
        raise RuntimeError(
            "No X API bearer token provided. "
            "Set the X_BEARER_TOKEN environment variable or pass bearer_token=..."
        )
    # HTTP headers must be Latin-1; strip smart quotes / other non-ASCII
    token = "".join(c for c in token if ord(c) < 256).strip()
    if not token:
        raise RuntimeError(
            "Bearer token is empty after removing invalid characters. "
            "Check that X_BEARER_TOKEN contains only straight quotes and no smart quotes."
        )
    return token


def _x_get(
    path: str,
    bearer_token: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Minimal helper to call the X API.

    NOTE: The base URL may change over time. Check the latest X API docs and
    update BASE_URL if needed.
    """
    base_url = "https://api.x.com/2"
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=10)
    if not resp.ok:
        raise XApiError(
            f"X API request failed ({resp.status_code}): {resp.text[:500]}"
        )
    return resp.json()


def fetch_tweet_and_replies(
    url_or_id: str,
    *,
    bearer_token: Optional[str] = None,
    max_replies: int = 5,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Fetch the original tweet and a small set of replies suitable for rhetorical analysis.

    Returns a tuple of:
        (op_tweet, replies)

    where:
        - op_tweet is a raw tweet JSON dict.
        - replies is a list of raw tweet JSON dicts (may be empty).

    This is intentionally minimal and focused on supplying enough text/context
    for the rhetorical agent. You can enrich or reshape this data further
    before passing it into your analysis pipeline.

    Parameters
    ----------
    url_or_id:
        Either a tweet URL (x.com/twitter.com) or a numeric tweet ID.
    bearer_token:
        Optional bearer token. If omitted, X_BEARER_TOKEN env var is used.
    max_replies:
        Rough cap on how many replies to fetch. This is a soft target and may
        not be exact depending on API behavior.
    """
    token = _get_bearer_token(bearer_token)
    tweet_id = extract_tweet_id(url_or_id)

    # 1) Fetch the original tweet.
    # Include basic author and public metrics so you can reason about power dynamics.
    op_data = _x_get(
        f"/tweets/{tweet_id}",
        token,
        params={
            "expansions": "author_id",
            "tweet.fields": "created_at,public_metrics,conversation_id",
            "user.fields": "username,name,public_metrics,verified",
        },
    )

    # The conversation_id tells us the thread root; we treat that as the "OP".
    op_tweet = op_data.get("data", {})
    conversation_id = op_tweet.get("conversation_id", tweet_id)

    # 2) Fetch a slice of replies in the same conversation.
    # We use a search endpoint filtered by conversation_id.
    # Check the latest X API docs for any changes to this endpoint or query syntax.
    replies_data = _x_get(
        "/tweets/search/recent",
        token,
        params={
            "query": f"conversation_id:{conversation_id}",
            "max_results": max(10, max_replies),
            "tweet.fields": "created_at,public_metrics,author_id,in_reply_to_user_id",
            "expansions": "author_id,in_reply_to_user_id",
            "user.fields": "username,name,public_metrics,verified",
        },
    )

    replies = replies_data.get("data", []) or []

    # Filter out the OP itself if it appears in the search results.
    replies = [tw for tw in replies if tw.get("id") != conversation_id]

    # Roughly cap to max_replies.
    if max_replies and max_replies > 0:
        replies = replies[:max_replies]

    return op_tweet, replies


def format_thread_for_agent(
    op_tweet: Dict[str, Any],
    replies: List[Dict[str, Any]],
    *,
    our_context: Optional[str] = None,
    voice: Optional[str] = None,
) -> str:
    """
    Build a simple text block from raw tweet JSON that you can paste directly
    into the Cursor rhetorical agent chat.

    If our_context is None or empty, defaults to AgenC support + RaiderKit
    positioning so the agent assumes you're replying in support of AgenC.

    If voice is None, a random voice is chosen from VOICE_NAMES and appended
    as "VOICE: <name>" so the agent uses that voice. Pass a voice name (e.g.
    "fuckhead", "didion") to force one, or pass "" to omit the VOICE line.

    Example usage:

        op, replies = fetch_tweet_and_replies(url)
        prompt_snippet = format_thread_for_agent(op, replies, our_context="We are a research account for protocol X.")
        print(prompt_snippet)

    Then copy/paste the printed text into the Cursor chat and ask:
        "What’s the smartest way to respond?"
    """
    lines: List[str] = []

    author = op_tweet.get("author_id", "unknown")
    op_text = op_tweet.get("text", "").strip()

    lines.append("OP:")
    if author != "unknown":
        lines.append(f"[author_id: {author}]")
    lines.append(op_text or "[no text]")
    lines.append("")

    if replies:
        lines.append("REPLIES:")
        for idx, tw in enumerate(replies, start=1):
            reply_author = tw.get("author_id", "unknown")
            reply_text = (tw.get("text") or "").strip()
            lines.append(f"{idx}) [author_id: {reply_author}] {reply_text}")
        lines.append("")

    context = (our_context or "").strip()
    if not context:
        context = "Replying in support of AgenC. Use RaiderKit positioning and proof points when relevant."
    lines.append("OUR CONTEXT:")
    lines.append(context)

    # Random or explicit voice for the rhetoric agent
    if voice is None:
        voice = random.choice(VOICE_NAMES)
    if voice:
        lines.append(f"VOICE: {voice.strip().lower()}")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


# Default question the rhetoric skill expects; appended so one paste is enough.
DEFAULT_QUESTION = "What's the smartest way to respond to this?"


def main() -> None:
    """CLI: fetch thread from URL, format for the agent, print (with question appended by default)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch an X thread and format it for the Rhetorical Agent (Cursor skill). "
        "Paste the output into Cursor and the agent will answer in one go."
    )
    parser.add_argument(
        "url",
        help="Tweet URL (e.g. https://x.com/user/status/123...) or numeric tweet ID",
    )
    parser.add_argument(
        "--max-replies",
        type=int,
        default=5,
        metavar="N",
        help="Max replies to fetch (default: 5)",
    )
    parser.add_argument(
        "--context",
        default="",
        metavar="TEXT",
        help="OUR CONTEXT line (who you are / how you're replying). Default: AgenC + RaiderKit.",
    )
    parser.add_argument(
        "--voice",
        choices=VOICE_NAMES,
        default=None,
        help="Force a voice (e.g. fuckhead, didion). Default: random.",
    )
    parser.add_argument(
        "--no-question",
        action="store_true",
        help="Do not append the default question (old behavior: you ask in a follow-up).",
    )
    args = parser.parse_args()

    op, replies = fetch_tweet_and_replies(
        args.url,
        max_replies=args.max_replies,
    )
    block = format_thread_for_agent(
        op,
        replies,
        our_context=args.context.strip() or None,
        voice=args.voice,
    )
    if not args.no_question:
        block = block.rstrip() + "\n\n" + DEFAULT_QUESTION + "\n"
    print(block, end="")


if __name__ == "__main__":
    main()

