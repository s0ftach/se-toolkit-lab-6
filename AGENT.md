# Agent Architecture

## Overview

This agent is a Python CLI that calls an LLM with tools (function calling) and returns structured JSON answers. It implements an agentic loop that allows the LLM to discover and read files from the project wiki, query the deployed backend API, and reason about the results to answer questions.

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** qwen3-coder-plus
- **API Compatibility:** OpenAI-compatible chat completions API with function calling
- **Endpoint:** http://10.93.25.98:42005/v1

## Architecture

### Data Flow

```
User Question
    ↓
Agentic Loop (max 10 iterations)
    ↓
1. Send question + tool schemas to LLM
    ↓
2. LLM decides: call tool OR give answer
    ↓
3a. Tool call → Execute → Send result back → Go to 1
3b. Answer → Extract source → Output JSON → Exit
    ↓
JSON Response {"answer": "...", "source": "...", "tool_calls": [...]}
```

### Components

#### 1. Environment Loading (`load_env()`)

- Reads `.env.agent.secret` for LLM configuration
- Reads `.env.docker.secret` for LMS API key
- Validates required variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`, `LMS_API_KEY`
- Exits with code 1 if any are missing

#### 2. LLM Client (`create_client()`)

- Uses the `openai` Python library (compatible with Qwen API)
- Configured with API key and base URL from environment

#### 3. Tool Definitions (`get_tool_schemas()`)

Three tools are registered with the LLM:

**`read_file`**
- Purpose: Read a file from the project repository (source code, documentation, configuration)
- Parameters: `path` (string) — relative path from project root
- Security: Validates path doesn't contain `..` traversal

**`list_files`**
- Purpose: List files and directories at a given path (discover project structure)
- Parameters: `path` (string) — relative directory path from project root
- Security: Validates path doesn't contain `..` traversal

**`query_api`**
- Purpose: Call the deployed backend API to query data or test endpoints
- Parameters: `method` (string: GET/POST/PUT/DELETE/PATCH), `path` (string), `body` (string, optional)
- Authentication: Uses `LMS_API_KEY` from `.env.docker.secret`
- Base URL: `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)

#### 4. Tool Execution (`execute_tool()`, `read_file()`, `list_files()`, `query_api()`)

- `read_file`: Reads file contents, returns error if file doesn't exist or path is invalid
- `list_files`: Returns newline-separated listing of directory entries
- `query_api`: Makes HTTP request to backend API with authentication, returns JSON with status_code and body
- All file tools validate paths against `PROJECT_ROOT` to prevent directory traversal

#### 5. Agentic Loop (`run_agentic_loop()`)

The core loop that enables agentic behavior:

1. **Send request** — User question + tool schemas to LLM
2. **Parse response** — Check if LLM wants to call tools
3. **Execute tools** — Run requested tools, log results
4. **Feed back** — Send tool results to LLM as `tool` role messages
5. **Repeat** — Continue until LLM provides final answer or max 10 iterations

#### 6. Output (`main()`)

- Builds JSON: `{"answer": "...", "source": "...", "tool_calls": [...]}`
- `source` is extracted from answer (wiki file, source file, or API endpoint)
- `tool_calls` contains all tool invocations with arguments and results
- Prints to stdout (single line, valid JSON)
- All debug/progress output goes to stderr

### System Prompt

The system prompt instructs the LLM to:

1. **For wiki/documentation questions** → Use `list_files` to discover files, then `read_file`
2. **For source code questions** → Use `list_files` to find modules, then `read_file`
3. **For data queries (item count, scores)** → Use `query_api`
4. **For system facts (framework, ports, status codes)** → Use `query_api` or `read_file` on source
5. **For bug diagnosis** → Use `query_api` to reproduce error, then `read_file` to find bug

## Usage

```bash
# Run with a question
uv run agent.py "How do you resolve a merge conflict?"

# Expected output
{
  "answer": "To resolve a merge conflict, edit the conflicting file...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Configuration

### Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (optional) | `.env.agent.secret`, default: `http://localhost:42002` |

**Important:** The autochecker injects different values. No hardcoded values!

### Setup

```bash
# Copy and fill LLM config
cp .env.agent.example .env.agent.secret

# LMS_API_KEY is already in .env.docker.secret
```

## Dependencies

- `openai` — LLM client (OpenAI-compatible API with function calling)
- `python-dotenv` — Environment variable loading
- `httpx` — HTTP client for query_api tool

Install with:
```bash
uv add openai python-dotenv httpx
```

## Security

### Path Validation

File tools validate paths to prevent directory traversal attacks:

1. Reject empty paths
2. Reject absolute paths (starting with `/`)
3. Reject paths containing `..`
4. Resolve path against `PROJECT_ROOT`
5. Verify resolved path starts with `PROJECT_ROOT`

### API Authentication

The `query_api` tool authenticates with the backend using `LMS_API_KEY`:

```python
headers = {
    "X-API-Key": os.getenv("LMS_API_KEY"),
    "Content-Type": "application/json"
}
```

## Error Handling

- **Missing env vars:** Validates at startup, exits with code 1
- **Network errors:** Caught and logged to stderr, returns error message
- **API errors:** Returns status_code and error body
- **Invalid arguments:** Shows usage message to stderr, exits with code 1
- **Max iterations:** After 10 tool calls, returns partial answer

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
1. Agent outputs valid JSON with `answer`, `source`, and `tool_calls`
2. Question about wiki files triggers `list_files` tool
3. Question about git workflow triggers `read_file` tool
4. Question about framework triggers `read_file` tool
5. Question about database items triggers `query_api` tool

## Benchmark Evaluation

Run the benchmark:

```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all classes:
- Wiki lookup (read_file)
- System facts (read_file, query_api)
- Data queries (query_api)
- Bug diagnosis (query_api + read_file)
- Reasoning (read_file)

## Task History

### Task 1: Basic LLM Integration

- Simple CLI that calls LLM without tools
- Output: `{"answer": "...", "tool_calls": []}`

### Task 2: Documentation Agent

- Added `read_file` and `list_files` tools
- Implemented agentic loop with max 10 iterations
- Output: `{"answer": "...", "source": "...", "tool_calls": [...]}`

### Task 3: System Agent (Current)

- Added `query_api` tool for backend API access
- Updated system prompt to distinguish wiki vs API questions
- Source field is now optional (null for system questions)
- Reads all config from environment variables (no hardcoding)

## Lessons Learned

1. **Tool descriptions matter:** Vague descriptions confuse the LLM. Be specific about when to use each tool.

2. **Error handling is critical:** The LLM needs clear error messages to recover from failed tool calls.

3. **Path security:** Always validate file paths to prevent directory traversal attacks.

4. **Environment separation:** Keep LLM credentials (`LLM_API_KEY`) separate from backend credentials (`LMS_API_KEY`).

5. **Iteration limit:** The 10-iteration limit prevents infinite loops but may truncate complex reasoning.

6. **Source extraction:** Regex-based source extraction is fragile; consider having the LLM explicitly state the source.

7. **API authentication:** The `X-API-Key` header is a common pattern for API authentication.

8. **Timeout handling:** HTTP requests need timeouts to prevent hanging on unresponsive endpoints.

## Final Eval Score

Run `run_eval.py` to see the current score. Target: 10/10 questions passed.
