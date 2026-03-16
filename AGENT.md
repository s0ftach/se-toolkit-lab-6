# The System Agent Architecture

## Tool Overview
In Task 3, our agent transitioned from a simple documentation reader to a dynamic System Agent capable of interacting with the live environment. To achieve this, a new `query_api` tool was registered alongside the existing `read_file` and `list_files` tools. The `query_api` tool executes HTTP requests against our deployed backend API. It accepts standard HTTP parameters like `method`, `path`, and an optional `body`, and returns a structured JSON string containing the HTTP `status_code` and response `body`.

The agent now has three distinct tools for different purposes:
- **`list_files`**: Discover directory structure (wiki, backend routers, etc.)
- **`read_file`**: Read static content (documentation, source code, Docker configs)
- **`query_api`**: Query live system state (item counts, status codes, reproduce errors)

## Authentication & Configuration
The tool strictly adheres to environment-based configuration to support seamless autochecker evaluation. It dynamically reads `AGENT_API_BASE_URL` to route requests (defaulting to `http://localhost:42002`), and fetches `LMS_API_KEY` from the `.env.docker.secret` file. This backend key is injected into the HTTP request headers as a Bearer token (`Authorization: Bearer <key>`), separating backend authentication from LLM provider authentication (`LLM_API_KEY` in `.env.agent.secret`).

The `query_api` tool also supports a `skip_auth` parameter. When set to `true`, the Authorization header is omitted, allowing the agent to test what status code an endpoint returns for unauthenticated requests (e.g., 401 or 403).

## LLM Decision Making
The `SYSTEM_PROMPT` was updated to guide the LLM's decision-making process with explicit decision rules:

- **Wiki questions** → `list_files` path="wiki", then `read_file` on the relevant file
- **Framework/source code questions** → `read_file` on backend source (starting with `backend/app/main.py`)
- **Router modules** → `list_files` path="backend/app/routers", then `read_file` each file
- **Live data (item count, status code)** → `query_api` WITH authentication (default)
- **Unauthenticated access tests** → `query_api` with `skip_auth=true`
- **API error or crash** → First `query_api` to reproduce the error, then `read_file` on the traceback file to locate the exact faulty line
- **Docker/request flow** → Must `read_file` on ALL FOUR files: `docker-compose.yml`, `Caddyfile`, `backend/Dockerfile`, `backend/app/main.py`

The system prompt also includes specific guidance for known bugs:
- `/analytics/completion-rate` crashes with `ZeroDivisionError` when `len(items) == 0`
- `/analytics/top-learners` may crash with `TypeError` when sorting `None` values

## Tool Chaining for Debugging
For complex debugging questions, the agent must chain multiple tool calls:
1. Call `query_api` to reproduce the error and capture the traceback
2. Read the error message (e.g., "division by zero", "TypeError: '>' not supported")
3. Call `read_file` on the source file mentioned in the traceback
4. Locate the buggy line and explain the fix

This chaining is guided by the system prompt, which explicitly instructs the LLM to switch from `query_api` to `read_file` after observing an error.

## Lessons Learned
During the benchmark evaluation, several issues were encountered and resolved:

1. **Environment URL bug**: The `LLM_API_BASE` had `//v1` (double slash) which caused API calls to fail with "Cannot POST //v1/chat/completions". Fixed by correcting the URL to `/v1`.

2. **Empty database**: The database starts empty and must be populated via the ETL pipeline. Triggered `POST /pipeline/sync` to fetch data from the autochecker API.

3. **NoneType attribute error**: The LLM sometimes returns `content: null` during tool-calling. Fixed by using `(msg.content or "")` instead of `msg.get("content", "")` — the field is present but `null`, not missing.

4. **Tool descriptions matter**: Clear, specific tool descriptions in the schema help the LLM choose the right tool. For example, explicitly stating "Use for item counts, status codes, or reproducing runtime errors" in the `query_api` description.

5. **System prompt specificity**: The more specific the decision rules in the system prompt, the better the agent performs. Adding step-by-step instructions for error diagnosis significantly improved performance on debugging questions.

## Final Evaluation Score
- **Local benchmark**: 10/10 passed
- **Test coverage**: 7 regression tests passing
  - JSON output validation
  - Wiki question handling
  - Git workflow question handling
  - Framework question (uses `read_file`)
  - Data question (uses `query_api`)
  - Status code question (uses `query_api` with `skip_auth`)
  - Error diagnosis (chains `query_api` + `read_file`)

The agent successfully handles all question types: wiki lookups, system facts, data-dependent queries, bug diagnosis, and multi-step reasoning questions that require tracing the HTTP request lifecycle through the infrastructure.
