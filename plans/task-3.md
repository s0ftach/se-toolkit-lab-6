# Task 3: The System Agent - Implementation Plan

## 1. Tool Schema (`query_api`)
I will add a new tool called `query_api`. The schema will accept:
- `method` (string): HTTP method (GET, POST, etc.)
- `path` (string): The API endpoint path (e.g., `/items/`)
- `body` (string, optional): JSON request body for POST/PUT requests.
The tool will return a JSON-encoded string containing `status_code` and `body`.

## 2. Authentication & Configuration
The tool will construct the target URL using `AGENT_API_BASE_URL` (defaulting to `http://localhost:42002`). 
Authentication will be handled by reading `LMS_API_KEY` from the environment and passing it in the request headers (typically as `Authorization: Bearer <KEY>` or `X-API-Key`). Both `.env.agent.secret` and `.env.docker.secret` will be loaded using `dotenv`.

## 3. System Prompt Updates
I will update the system prompt to explicitly instruct the LLM:
- Use `list_files` and `read_file` for static wiki documentation or source code debugging.
- Use `query_api` for dynamic data-dependent questions (e.g., item count) or to observe live system status/errors.
- Make the `source` field optional in the final JSON output, as system facts may not have a wiki source.

## 4. Handling `NoneType` bugs
I will fix the message appending logic in the while-loop to handle cases where the LLM returns `content: null` (using `content = message.content or ""`).

## Iteration Strategy & Benchmark
After implementing the tool, I will run `uv run run_eval.py`. If the agent fails to use `query_api` for data queries or struggles with multi-step debugging, I will refine the system prompt or tool descriptions to be more explicit.

## Benchmark Results

### Initial Run
- **Score:** 10/10 passed
- **First failures:** None - all questions passed on the first run after fixing the `LLM_API_BASE` URL (removed double slash `//v1` → `/v1`)

### Key Issues Fixed
1. **Environment URL bug:** The `LLM_API_BASE` had `//v1` (double slash) which caused API calls to fail with "Cannot POST //v1/chat/completions"
2. **Database was empty:** Had to trigger the ETL pipeline via `POST /pipeline/sync` to populate items data

### Iteration Strategy
The agent worked well because:
- The `query_api` tool was already implemented in Task 2
- The system prompt had clear decision rules for when to use each tool
- The `NoneType` bug fix (`msg.content or ""`) was already in place

For future iterations, if failures occur:
1. Check if the agent is using the correct tool (examine `tool_calls`)
2. Refine tool descriptions if the LLM calls with wrong arguments
3. Add more specific hints in the system prompt for error diagnosis questions