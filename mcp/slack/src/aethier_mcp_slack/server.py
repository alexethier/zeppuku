"""Slack MCP server.

Tools:
  post(text, channel=None)
                     Post a message. `channel` defaults to
                     $AETHIER_BOT_NOTIFICATIONS_SLACK_CHANNEL_ID. Remembers
                     the ts per-channel so a subsequent await_response()
                     on the same channel can poll for replies.
  await_response(channel=None)
                     Single-shot long-poll for a reply from a specific
                     user in `channel` (defaults to the env channel),
                     after that channel's most recent post(). Tiered
                     sleep schedule (10s/60s/600s), 4-hour hard deadline.
                     Follows the BYOC await_logs convention: returns
                     immediately; if status is "in_progress", caller
                     sleeps for sleep_before_retry_s then re-calls.
  start_conversation(name=None)
                     Create a new private Slack channel and invite
                     $AETHIER_USER_SLACK_USER_ID. Auto-names as
                     `aethier-chat-<ts>` when name is omitted. Returns
                     {ok, channel_id, channel_name, invited_user}.

Env vars:
  SLACK_BOT_TOKEN                            xoxb-...  Bot User OAuth Token
                                                       (needs chat:write,
                                                       channels:history /
                                                       groups:history,
                                                       groups:write)
  AETHIER_BOT_NOTIFICATIONS_SLACK_CHANNEL_ID  C...      Channel ID for posts
  AETHIER_USER_SLACK_USER_ID                  U...      User ID whose messages
                                                       count as "responses"
"""
from __future__ import annotations

import os
import re
import time

import httpx

from aethier_mcp_core import add_log_fields, create_server, run

mcp = create_server("slack")

BOT_TOKEN: str = os.environ["SLACK_BOT_TOKEN"]
CHANNEL: str = os.environ["AETHIER_BOT_NOTIFICATIONS_SLACK_CHANNEL_ID"]
USER_ID: str = os.environ["AETHIER_USER_SLACK_USER_ID"]

# (elapsed_threshold_s, sleep_s) - first row whose threshold > elapsed wins.
SLEEP_SCHEDULE: list[tuple[int, int]] = [
    (12,    3),     # first 12s: poll every 3s (snappy initial response)
    (60,    10),    # rest of the first minute: poll every 10s
    (600,   60),    # next 9 minutes: poll every 1 min
    (14400, 600),   # next ~4 hours: poll every 10 min
]
MAX_WAIT_S = 14400  # 4 hours hard deadline

# In-process state shared between post() and await_response(), keyed by
# channel id. A second post() to the same channel before its
# await_response() resolves implicitly abandons the prior wait for that
# channel; waits on different channels coexist independently.
# Shape per slot: {"ts": str, "started_at": float, "polls": int}
#
# CONCURRENCY CAVEAT: only one agent at a time is supported per channel.
# The wait slot is a single shared entry per channel id and is popped on
# `found`/`timeout`, so if two agents call await_response() on the same
# channel concurrently:
#   - both will poll Slack and (usually) both see the same reply, but
#     whichever consumes the slot first returns `found`; the other then
#     raises "no prior post on that channel" on its next call;
#   - two concurrent post()s to the same channel will clobber each
#     other's anchor ts (the earlier wait is silently abandoned).
# Different channels are fully independent, so the supported pattern is
# "one agent per channel" (e.g. one channel per JIRA ticket via
# start_conversation()). If we ever need genuine multi-agent fan-out on
# a single channel, switch this to a list-of-waits per channel and have
# callers thread their own anchor ts.
_pending_responses: dict[str, dict] = {}


def _resolve_channel(channel: str | None) -> str:
    """Pick the channel to act on: caller-supplied or the env default."""
    return channel if channel else CHANNEL


def _sanitize_channel_name(raw: str) -> str:
    """Coerce a string into a valid Slack channel name.

    Slack requires lowercase, 1-80 chars, only a-z/0-9/-/_.
    """
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s).strip("-_")
    return s[:80] or "aethier-chat"


def _sleep_hint_for(elapsed_s: int, remaining_s: int) -> int:
    """Pick the per-phase sleep, clamped to whatever's left in the budget."""
    for threshold_s, sleep_s in SLEEP_SCHEDULE:
        if elapsed_s < threshold_s:
            return min(sleep_s, remaining_s)
    # Past every threshold: fall back to the slowest phase (shouldn't happen
    # in practice since remaining_s would be 0 by now, but be defensive).
    return min(SLEEP_SCHEDULE[-1][1], remaining_s)


@mcp.tool()
async def post(text: str, channel: str | None = None) -> dict:
    """Post a message to Slack.

    CRITICAL: Always call await_response() after post(). If you skip this
    call, the user's Slack reply will be lost and never delivered back to you.
    THERE ARE NO EXCEPTIONS — even if you think you know better, just start polling await_response(). 
    
    Call usage('post') for details.
    """
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    target_channel = _resolve_channel(channel)

    async with httpx.AsyncClient(
        base_url="https://slack.com/api",
        headers={
            "Authorization": f"Bearer {BOT_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        resp = await client.post(
            "/chat.postMessage",
            json={"channel": target_channel, "text": text},
        )

    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"Slack chat.postMessage failed: {data.get('error', 'unknown_error')}"
        )

    ts = data.get("ts")
    # Key the wait slot on the channel Slack echoed back when available
    # (handles the rare case where Slack resolves a channel name/alias to
    # a different id than what we sent). Falls back to what we asked for.
    resolved_channel = data.get("channel") or target_channel
    _pending_responses[resolved_channel] = {
        "ts": ts,
        "started_at": time.monotonic(),
        "polls": 0,
    }
    add_log_fields(channel=resolved_channel, ts=ts)
    return {
        "ok": True,
        "ts": ts,
        "channel": resolved_channel,
        "next_action": (
            f"YOUR TURN IS NOT OVER. The message was posted to Slack, "
            f"but the user has not yet seen or responded to it. You MUST "
            f"now call slack.await_response(channel={resolved_channel!r}) "
            f"as your very next tool call to wait for the user's reply. "
            f"Do NOT end your turn, do NOT summarize, do NOT proceed to "
            f"any other work — call await_response immediately. The only "
            f"exception is if the user has explicitly told you not to "
            f"wait for a reply."
        ),
    }


@mcp.tool()
async def await_response(channel: str | None = None) -> dict:
    """Poll for a user reply after a post(). Pollable. Call usage('await_response') for details."""
    target_channel = _resolve_channel(channel)
    slot = _pending_responses.get(target_channel)
    if slot is None:
        raise RuntimeError(
            f"await_response(channel={target_channel!r}) called without a "
            f"prior post() on that channel; call post(text, channel=...) "
            f"first so we know what to wait after."
        )

    slot["polls"] += 1
    polls = slot["polls"]
    anchor_ts: str = slot["ts"]
    elapsed_s = int(time.monotonic() - slot["started_at"])
    remaining_s = max(0, MAX_WAIT_S - elapsed_s)

    async with httpx.AsyncClient(
        base_url="https://slack.com/api",
        headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        timeout=30.0,
    ) as client:
        resp = await client.get(
            "/conversations.history",
            params={
                "channel": target_channel,
                "oldest": anchor_ts,
                "inclusive": "false",
                "limit": 100,
            },
        )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"Slack conversations.history failed: "
            f"{data.get('error', 'unknown_error')}"
        )

    # Messages newest-first. Find the oldest reply from USER_ID (so we
    # surface the earliest response, not the latest).
    reply: dict | None = None
    for m in reversed(data.get("messages", []) or []):
        if m.get("user") == USER_ID:
            reply = m
            break

    if reply is not None:
        _pending_responses.pop(target_channel, None)
        add_log_fields(
            status="found",
            channel=target_channel,
            polls=polls,
            elapsed_s=elapsed_s,
            reply_ts=reply.get("ts"),
        )
        return {
            "status": "found",
            "channel": target_channel,
            "next_action": (
                f"The user replied (see `message.text`). Act on their "
                f"message, then ALWAYS report back when you're done by "
                f"calling slack.post(text=<your response or status "
                f"update>, channel={target_channel!r}). Keep this "
                f"post/await loop going every turn until the user "
                f"explicitly tells you to stop."
            ),
            "message": {
                "ts": reply.get("ts"),
                "user": reply.get("user"),
                "text": reply.get("text", ""),
            },
            "polls": polls,
            "elapsed_s": elapsed_s,
        }

    if remaining_s <= 0:
        _pending_responses.pop(target_channel, None)
        add_log_fields(
            status="timeout",
            channel=target_channel,
            polls=polls,
            elapsed_s=elapsed_s,
        )
        return {
            "status": "timeout",
            "channel": target_channel,
            "next_action": (
                f"The user did not respond within 4h. Post a final "
                f"summary of where you got to by calling "
                f"slack.post(text=<final summary>, "
                f"channel={target_channel!r}) so the thread captures "
                f"the outcome, then stop waiting."
            ),
            "polls": polls,
            "elapsed_s": elapsed_s,
        }

    sleep_hint = _sleep_hint_for(elapsed_s, remaining_s)
    add_log_fields(
        status="in_progress",
        channel=target_channel,
        polls=polls,
        elapsed_s=elapsed_s,
        remaining_s=remaining_s,
        sleep_before_retry_s=sleep_hint,
    )
    return {
        "status": "in_progress",
        "channel": target_channel,
        "next_action": (
            f"YOUR TURN IS NOT OVER. The user has NOT yet replied; "
            f"this is just one poll in an ongoing wait. You MUST sleep "
            f"for {sleep_hint} seconds and then call "
            f"slack.await_response(channel={target_channel!r}) AGAIN "
            f"as your very next tool call. Do NOT end your turn, do NOT "
            f"summarize, do NOT report status to the user yet — just "
            f"keep polling until status becomes 'found' or 'timeout'. "
            f"{remaining_s} s remain in the wait budget."
        ),
        "sleep_before_retry_s": sleep_hint,
        "polls": polls,
        "elapsed_s": elapsed_s,
        "remaining_s": remaining_s,
    }


@mcp.tool()
async def start_conversation(name: str | None = None) -> dict:
    """Create a private Slack channel and invite the user. Call usage('start_conversation') for details."""
    raw_name = name if name else f"aethier-chat-{int(time.time())}"
    channel_name = _sanitize_channel_name(raw_name)

    async with httpx.AsyncClient(
        base_url="https://slack.com/api",
        headers={
            "Authorization": f"Bearer {BOT_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        create_resp = await client.post(
            "/conversations.create",
            json={"name": channel_name, "is_private": True},
        )
        create_data = create_resp.json()
        if not create_data.get("ok"):
            raise RuntimeError(
                f"Slack conversations.create failed: "
                f"{create_data.get('error', 'unknown_error')}"
            )

        channel = create_data.get("channel") or {}
        channel_id = channel.get("id")
        # Slack may normalize the name (truncate/lowercase further); prefer
        # the server-returned value when present.
        final_name = channel.get("name", channel_name)

        invite_resp = await client.post(
            "/conversations.invite",
            json={"channel": channel_id, "users": USER_ID},
        )
        invite_data = invite_resp.json()
        if not invite_data.get("ok"):
            err = invite_data.get("error", "unknown_error")
            # Idempotent edge cases: the user is already in or we tried to
            # invite the bot itself. Treat as success.
            if err not in {"already_in_channel", "cant_invite_self"}:
                raise RuntimeError(
                    f"Slack conversations.invite failed: {err}"
                )

    add_log_fields(
        channel_id=channel_id,
        channel_name=final_name,
        invited_user=USER_ID,
    )
    return {
        "ok": True,
        "channel_id": channel_id,
        "channel_name": final_name,
        "invited_user": USER_ID,
    }


def main() -> None:
    run(mcp)
