# aethier-mcp-slack

MCP server for posting to a statically configured Slack channel and waiting on a human reply.

## Tools

| Tool | Description |
|------|-------------|
| `post(text, channel=None)` | Post `text` to a Slack channel. `channel` defaults to `$AETHIER_BOT_NOTIFICATIONS_SLACK_CHANNEL_ID` when omitted. Returns `{ok, ts, channel}`. Also remembers the `ts` per-channel so a follow-up `await_response(channel=...)` on the same channel knows what to wait after. |
| `await_response(channel=None)` | Single-shot long-poll for a reply from `$AETHIER_USER_SLACK_USER_ID` in `channel` (defaults to the env channel), posted after that channel's most recent `post()`. Timing is fully owned by the tool. |
| `start_conversation(name=None)` | Create a new private Slack channel and invite `$AETHIER_USER_SLACK_USER_ID`. If `name` is omitted it auto-generates `aethier-chat-<unix-ts>`; supplied names are sanitized to Slack's rules. Returns `{ok, channel_id, channel_name, invited_user}`. Pass the returned `channel_id` to `post()` / `await_response()` to drive a conversation in the new channel. |

### `await_response()` long-polling

Mirrors the BYOC `await_logs` convention: the tool tracks elapsed time internally and tells the caller how long to sleep before the next call. The caller just follows `next_action`.

Tiered sleep schedule:

| Elapsed since `post()` | Sleep between polls |
|------------------------|---------------------|
| 0–12 s | 3 s |
| 12–60 s | 10 s |
| 60–600 s | 60 s |
| 600–14 400 s (up to 4 h total) | 600 s |
| > 14 400 s | returns `status: "timeout"` |

Return shapes:

- `{status: "found", message: {ts, user, text}, next_action, polls, elapsed_s}` — the user replied; state cleared.
- `{status: "timeout", next_action, polls, elapsed_s}` — 4-hour budget exhausted; state cleared.
- `{status: "in_progress", sleep_before_retry_s, next_action, polls, elapsed_s, remaining_s}` — keep polling; sleep `sleep_before_retry_s` seconds then re-call `await_response()`.

Wait state is keyed by channel: a second `post()` to the same channel before its `await_response()` resolves implicitly abandons the prior wait for that channel (the new `ts` replaces it). Waits on different channels are independent and can be in flight concurrently.

## Env vars

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | yes | `xoxb-...` Bot User OAuth Token (needs `chat:write` for `post`, `channels:history` / `groups:history` for `await_response` in the target channel, and `groups:write` for `start_conversation` to create + invite to private channels) |
| `AETHIER_BOT_NOTIFICATIONS_SLACK_CHANNEL_ID` | yes | Default channel ID (`C...`) used by `post()` / `await_response()` when no `channel` arg is supplied |
| `AETHIER_USER_SLACK_USER_ID` | yes | Slack user ID (`U...`) whose messages count as a "response" |

## Usage

```bash
export SLACK_BOT_TOKEN=xoxb-...
export AETHIER_BOT_NOTIFICATIONS_SLACK_CHANNEL_ID=C0123456789
export AETHIER_USER_SLACK_USER_ID=U0123456789
./bin/manager build slack
./bin/manager start slack
```
