# Claude Code Integration with Respan

This integration automatically sends Claude Code conversation traces to Respan for observability and monitoring.

## Overview

Claude Code is Anthropic's agentic coding tool that lives in your terminal. This integration uses Claude Code's hooks system to automatically capture and send conversation traces to Respan after each response.

## Features

- ✅ **Automatic tracing** - Captures every Claude Code turn automatically
- ✅ **Hierarchical traces** - Each turn becomes a trace with chat + tool spans
- ✅ **Thread grouping** - All turns in a session grouped by `thread_identifier`
- ✅ **Incremental processing** - Processes only new messages (tracks state)
- ✅ **Error resilient** - Graceful failures don't break Claude Code

## Prerequisites

1. **Claude Code** - Install from [code.claude.com](https://code.claude.com)
2. **Python 3.9+** - Verify with `python3 --version`
3. **Respan API Key** - Get from [platform.respan.ai](https://platform.respan.ai/platform/api/api-keys)

## Installation

### Step 1: Install Dependencies

```bash
cd example_scripts/python/claude_code
pip install -r requirements.txt
```

### Step 2: Copy Hook Script

Copy the hook script to Claude Code's hooks directory:

```bash
# Create hooks directory if it doesn't exist
mkdir -p ~/.claude/hooks

# Copy the hook script
cp respan_hook.py ~/.claude/hooks/

# Make it executable
chmod +x ~/.claude/hooks/respan_hook.py
```

### Step 3: Configure Global Hook

Add the Stop hook to your global Claude Code settings (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/hooks/respan_hook.py"
      }]
    }]
  }
}
```

### Step 4: Enable Per-Project

For each project where you want tracing, create `.claude/settings.local.json`:

```json
{
  "env": {
    "TRACE_TO_RESPAN": "true",
    "RESPAN_API_KEY": "your-api-key-here",
    "RESPAN_BASE_URL": "https://api.respan.ai/api"
  }
}
```

**Note:** Tracing is opt-in per project. The hook runs globally but exits immediately if `TRACE_TO_RESPAN` is not set to `"true"`.

## How It Works

1. **Hook Execution**: After each Claude Code response, the Stop hook runs
2. **Transcript Reading**: Script finds the latest transcript file (`*.jsonl` in `~/.claude/projects/`)
3. **Incremental Processing**: Reads only new messages since last run (tracks state)
4. **Turn Grouping**: Groups messages into turns (user → assistant → tools)
5. **Span Creation**: Converts each turn into Respan spans:
   - Chat span (root) with `log_type: "chat"`
   - Tool spans (children) with `log_type: "tool"`
6. **Batch Sending**: Sends spans via `/api/traces/ingest/` endpoint
7. **State Update**: Saves progress to `~/.claude/state/respan_state.json`

## Data Structure

Each turn becomes a separate trace:

```
Session (sessionId)
  ├─ Turn 1 → Trace (trace_unique_id: "sessionId_turn_1")
  │   ├─ Chat Span (root, span_parent_id: null)
  │   └─ Tool Spans (children, span_parent_id: chat_span_id)
  │
  ├─ Turn 2 → Trace (trace_unique_id: "sessionId_turn_2")
  │   └─ Chat Span (root)
  │
  └─ Turn 3 → Trace (trace_unique_id: "sessionId_turn_3")
      └─ Chat Span (root)
```

All turns share the same `thread_identifier` (sessionId) for grouping in the Threads view.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TRACE_TO_RESPAN` | Set to `"true"` to enable tracing | Yes |
| `RESPAN_API_KEY` | Your Respan API key | Yes |
| `RESPAN_BASE_URL` | API base URL (default: `https://api.respan.ai/api`) | No |
| `CC_RESPAN_DEBUG` | Set to `"true"` for verbose debug logging | No |

## Troubleshooting

### No traces appearing in Respan

1. **Check hook is running:**
   ```bash
   tail -f ~/.claude/state/respan_hook.log
   ```

2. **Verify environment variables** in `.claude/settings.local.json`:
   - `TRACE_TO_RESPAN` must be `"true"` (string, not boolean)
   - API key must be correct

3. **Enable debug mode:**
   ```json
   {
     "env": {
       "CC_RESPAN_DEBUG": "true"
     }
   }
   ```

4. **Check script is executable:**
   ```bash
   chmod +x ~/.claude/hooks/respan_hook.py
   ```

### Permission errors

Make sure the hook script is executable:
```bash
chmod +x ~/.claude/hooks/respan_hook.py
```

### Hook script errors

Test the script manually:
```bash
TRACE_TO_RESPAN=true \
RESPAN_API_KEY="your-key" \
python3 ~/.claude/hooks/respan_hook.py
```

Check the log file:
```bash
cat ~/.claude/state/respan_hook.log
```

## Viewing Traces

Open your Respan dashboard to see:
- **Threads view**: All turns in a session as a linear conversation
- **Traces view**: Each turn as a hierarchical trace with spans
- **Logs view**: Individual spans/logs

Filter by `thread_identifier` to see all turns from a Claude Code session.

## Files

- `respan_hook.py` - Main hook script (copy to `~/.claude/hooks/`)
- `requirements.txt` - Python dependencies
- `README.md` - This file

## State Files

The hook creates state files in `~/.claude/state/`:
- `respan_state.json` - Tracks last processed line per session
- `respan_hook.log` - Debug logs

## Security Note

The hook script runs with your user's permissions. Review the script before installing, especially if downloading from an untrusted source.

## License

MIT
