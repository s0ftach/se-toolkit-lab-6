# Task 3 Plan: The System Agent

## Overview

Extend the agent from Task 2 with a new tool (`query_api`) to query the deployed backend API. This enables the agent to answer static system facts (framework, ports, status codes) and data-dependent queries (item count, scores).

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** qwen3-coder-plus
- **API Compatibility:** OpenAI-compatible function calling API

## New Tool: query_api

### Schema

```json
{
  "name": "query_api",
  "description": "Call the deployed backend API to query data or check system status",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
      },
      "path": {
        "type": "string",
        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT/PATCH requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

### Implementation

- Use `httpx` library for HTTP requests
- Authenticate with `LMS_API_KEY` from `.env.docker.secret`
- Base URL from `AGENT_API_BASE_URL` env var (default: `http://localhost:42002`)
- Return JSON string with `status_code` and `body`

### Authentication

```python
headers = {
    "X-API-Key": os.getenv("LMS_API_KEY"),
    "Content-Type": "application/json"
}
```

## Environment Variables

The agent must read ALL configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (optional) | `.env.agent.secret`, default: `http://localhost:42002` |

**Important:** The autochecker injects different values. No hardcoded values!

## System Prompt Update

The system prompt will instruct the LLM to:

1. **For wiki/documentation questions** → Use `list_files` and `read_file`
2. **For system facts (framework, ports, status codes)** → Use `query_api` or `read_file` on source code
3. **For data queries (item count, scores)** → Use `query_api`
4. **For bug diagnosis** → Use `query_api` to reproduce error, then `read_file` to find bug in source

Example guidance:
- "What framework does the backend use?" → `read_file` on `backend/app/main.py` or `pyproject.toml`
- "How many items in the database?" → `query_api` GET `/items/`
- "What status code for unauthenticated request?" → `query_api` GET `/items/` without auth header

## Agentic Loop

No changes to the loop structure — just add `query_api` to the tool schemas.

```
1. Send question + all 3 tool schemas to LLM
2. LLM decides which tool to call
3. Execute tool, feed result back
4. Repeat until answer or max 10 iterations
```

## Implementation Steps

1. ✅ Create `plans/task-3.md` (this file)
2. ⬜ Update `agent.py`:
   - Add `query_api` tool schema
   - Implement `query_api()` function with authentication
   - Load `LMS_API_KEY` and `AGENT_API_BASE_URL` from environment
   - Update system prompt
3. ⬜ Update `AGENT.md` documentation
4. ⬜ Add 2 regression tests
5. ⬜ Run `run_eval.py` and iterate until all 10 questions pass

## Testing

Test questions:
1. "What framework does the backend use?" → expects `read_file`
2. "How many items are in the database?" → expects `query_api`

Run benchmark:
```bash
uv run run_eval.py
```

## Expected Benchmark Results

Target: 10/10 questions passed

| # | Question Type | Tool Required |
|---|---------------|---------------|
| 0 | Wiki lookup | read_file |
| 1 | Wiki lookup | read_file |
| 2 | Source code | read_file |
| 3 | Source code | list_files |
| 4 | Data query | query_api |
| 5 | Status code | query_api |
| 6 | Bug diagnosis | query_api + read_file |
| 7 | Bug diagnosis | query_api + read_file |
| 8 | Reasoning | read_file |
| 9 | Reasoning | read_file |
