# Task 1 Plan: Call an LLM from Code

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** qwen3-coder-plus
- **API Base:** http://10.93.25.98:42005/v1
- **Authentication:** API key stored in `.env.agent.secret`

## Architecture

### Data Flow

```
Command line argument → agent.py → Qwen API → JSON response → stdout
```

### Components

1. **Environment Loading**
   - Read `.env.agent.secret` using `python-dotenv`
   - Extract `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

2. **LLM Client**
   - Use `openai` Python library (compatible with Qwen API)
   - Send user question as a chat completion request
   - Parse the response to extract the answer

3. **Output Formatting**
   - Build JSON object: `{"answer": "...", "tool_calls": []}`
   - Print to stdout as a single line
   - All debug logs go to stderr

### Error Handling

- Network errors: catch and log to stderr, exit with code 1
- API errors: catch and log to stderr, exit with code 1
- Missing env vars: validate at startup, exit with code 1

## Implementation Steps

1. ✅ Create `.env.agent.secret` with credentials
2. ⬜ Create `agent.py`:
   - Load environment variables
   - Initialize OpenAI client
   - Send question to LLM
   - Parse response and output JSON
3. ⬜ Create `AGENT.md` documentation
4. ⬜ Write 1 regression test

## Testing

- Run: `uv run agent.py "What is Python?"`
- Expected: Valid JSON with `answer` and `tool_calls` fields
- Test: Python script that runs agent as subprocess and validates output
