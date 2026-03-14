# Agent Architecture

## Overview

This agent is a Python CLI that calls an LLM with tools (function calling) and returns structured JSON answers. It implements an agentic loop that allows the LLM to discover and read files from the project wiki to answer questions.

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

- Reads `.env.agent.secret` using `python-dotenv`
- Validates required variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
- Exits with code 1 if any are missing

#### 2. LLM Client (`create_client()`)

- Uses the `openai` Python library (compatible with Qwen API)
- Configured with API key and base URL from environment

#### 3. Tool Definitions (`get_tool_schemas()`)

Two tools are registered with the LLM:

**`read_file`**
- Purpose: Read a file from the project repository
- Parameters: `path` (string) — relative path from project root
- Security: Validates path doesn't contain `..` traversal

**`list_files`**
- Purpose: List files and directories at a given path
- Parameters: `path` (string) — relative directory path from project root
- Security: Validates path doesn't contain `..` traversal

#### 4. Tool Execution (`execute_tool()`, `read_file()`, `list_files()`)

- `read_file`: Reads file contents, returns error if file doesn't exist or path is invalid
- `list_files`: Returns newline-separated listing of directory entries
- Both tools validate paths against `PROJECT_ROOT` to prevent directory traversal

#### 5. Agentic Loop (`run_agentic_loop()`)

The core loop that enables agentic behavior:

1. **Send request** — User question + tool schemas to LLM
2. **Parse response** — Check if LLM wants to call tools
3. **Execute tools** — Run requested tools, log results
4. **Feed back** — Send tool results to LLM as `tool` role messages
5. **Repeat** — Continue until LLM provides final answer or max 10 iterations

#### 6. Output (`main()`)

- Builds JSON: `{"answer": "...", "source": "...", "tool_calls": [...]}`
- `source` is extracted from answer (looks for `wiki/...md#...` pattern)
- `tool_calls` contains all tool invocations with arguments and results
- Prints to stdout (single line, valid JSON)
- All debug/progress output goes to stderr

### System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover relevant files in the wiki/ directory
2. Use `read_file` to read specific files and find the answer
3. Include source references (file path + section anchor) in the final answer
4. Call tools one at a time, waiting for results before making the next call

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

Create `.env.agent.secret` from `.env.agent.example`:

```bash
cp .env.agent.example .env.agent.secret
```

Fill in your credentials:

```
LLM_API_KEY=your-api-key
LLM_API_BASE=http://<vm-ip>:42005/v1
LLM_MODEL=qwen3-coder-plus
```

## Dependencies

- `openai` — LLM client (OpenAI-compatible API with function calling)
- `python-dotenv` — Environment variable loading

Install with:
```bash
uv add openai python-dotenv
```

## Security

### Path Validation

Tools validate paths to prevent directory traversal attacks:

1. Reject empty paths
2. Reject absolute paths (starting with `/`)
3. Reject paths containing `..`
4. Resolve path against `PROJECT_ROOT`
5. Verify resolved path starts with `PROJECT_ROOT`

### Example Attack Prevention

```python
# These are rejected:
read_file("../.env.secret")      # Contains ..
read_file("/etc/passwd")         # Absolute path
read_file("")                    # Empty path
```

## Error Handling

- **Missing env vars:** Validates at startup, exits with code 1
- **Network errors:** Caught and logged to stderr, exits with code 1
- **API errors:** Caught and logged to stderr, exits with code 1
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

## Task History

### Task 1: Basic LLM Integration

- Simple CLI that calls LLM without tools
- Output: `{"answer": "...", "tool_calls": []}`

### Task 2: Documentation Agent (Current)

- Added `read_file` and `list_files` tools
- Implemented agentic loop with max 10 iterations
- Output: `{"answer": "...", "source": "...", "tool_calls": [...]}`

### Task 3: Future Extensions

- Additional tools (API queries, code execution)
- Enhanced system prompt for domain knowledge
- Improved source extraction
