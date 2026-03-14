# Agent Architecture

## Overview

This agent is a Python CLI that calls an LLM and returns structured JSON answers. It forms the foundation for the agentic system that will be extended in Tasks 2–3 with tools and an agentic loop.

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** qwen3-coder-plus
- **API Compatibility:** OpenAI-compatible chat completions API
- **Endpoint:** http://10.93.25.98:42005/v1

## Architecture

### Data Flow

```
User Question (CLI arg)
    ↓
agent.py (parse input)
    ↓
Qwen Code API (LLM)
    ↓
JSON Response {"answer": "...", "tool_calls": []}
    ↓
stdout
```

### Components

1. **Environment Loading** (`load_env()`)
   - Reads `.env.agent.secret` using `python-dotenv`
   - Validates required variables: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
   - Exits with code 1 if any are missing

2. **LLM Client** (`create_client()`)
   - Uses the `openai` Python library (compatible with Qwen API)
   - Configured with API key and base URL from environment

3. **Answer Generation** (`get_answer()`)
   - Sends user question as a chat completion request
   - System prompt: "You are a helpful assistant. Answer questions concisely and accurately."
   - Extracts answer from response

4. **Output** (`main()`)
   - Builds JSON: `{"answer": "...", "tool_calls": []}`
   - Prints to stdout (single line, valid JSON)
   - All debug/progress output goes to stderr

## Usage

```bash
# Run with a question
uv run agent.py "What does REST stand for?"

# Expected output
{"answer": "Representational State Transfer.", "tool_calls": []}
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

- `openai` — LLM client (OpenAI-compatible API)
- `python-dotenv` — Environment variable loading

Install with:
```bash
uv add openai python-dotenv
```

## Error Handling

- **Missing env vars:** Validates at startup, exits with code 1
- **Network errors:** Caught and logged to stderr, exits with code 1
- **API errors:** Caught and logged to stderr, exits with code 1
- **Invalid arguments:** Shows usage message to stderr, exits with code 1

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

The test verifies:
- Agent outputs valid JSON
- `answer` field is present and non-empty
- `tool_calls` field is present (empty array for Task 1)

## Future Extensions (Tasks 2–3)

- **Task 2:** Add tools (file operations, API queries)
- **Task 3:** Implement agentic loop with tool execution
