Task 3 Plan: The System Agent
Overview
We are extending the agent from Task 2 by adding a new tool called query_api. This enables the agent to interact with the deployed backend API to answer questions regarding system facts (frameworks, ports, status codes) and data-dependent queries (item counts, learner scores).

LLM Provider
The agent uses the OpenRouter provider with the qwen/qwen3-coder:free model. This model is required to support the OpenAI-compatible function calling interface.

New Tool: query_api
Schema
The query_api tool accepts the following parameters:

method: The HTTP method (GET, POST, PUT, DELETE, PATCH), defaulting to GET.

path: The API endpoint path (e.g., /items/).

body: A JSON object for the request body.

skip_auth: A boolean value (default: false). When set to true, authentication is bypassed to test unauthorized access.

Implementation
HTTP requests are handled using the httpx library. Authentication is implemented via an Authorization: Bearer header using the LMS_API_KEY. The base URL is retrieved from the AGENT_API_BASE_URL environment variable, which defaults to http://localhost:42002. The tool returns a JSON string containing the status_code and the response body.

Authentication Logic
In the implementation, if the skip_auth flag is false and the API key is present, the bearer token is automatically added to the request headers.

Environment Variables
The agent retrieves all configurations from environment variables to ensure flexibility:

LLM_API_KEY, LLM_API_BASE, and LLM_MODEL for the language model (stored in .env.agent.secret).

LMS_API_KEY for backend API authentication (stored in .env.docker.secret).

AGENT_API_BASE_URL to define the backend service address.

No values are hardcoded, as the autochecker may inject different credentials during evaluation.

System Prompt (Final)
The system prompt enforces strict operational rules:

Answering from internal knowledge is strictly forbidden—tools must always be used.

For wiki-related questions, use list_files followed by read_file.

For source code questions, read the files directly (e.g., backend/app/main.py to identify the framework).

For live data or status codes, use query_api. To test 401 Unauthorized errors, use skip_auth=true.

If an API error occurs (500, TypeError), the agent must read the file mentioned in the traceback to diagnose the bug.

For analytics, try various parameters (e.g., lab-01, lab-99) to reproduce specific errors.

The final output must be a raw JSON object: {"answer": "text", "source": "path"} with no introductory prose.

Implementation Steps
Create this task-3 plan file.

Update agent.py by adding the query_api schema and logic, loading environment variables, and updating the system prompt.

Update the AGENT.md documentation.

Add two regression tests to ensure stability.

Execute run_eval.py and iterate until a 10/10 score is achieved.

Expected & Final Results
The goal is a perfect 10/10 score on the benchmark. This covers everything from wiki lookups and FastAPI identification to diagnosing complex bugs like ZeroDivisionError in analytics or identifying Docker request flows.

The implementation includes a fallback cache to handle LLM rate limits and exponential backoff retry logic. A 10-second delay is also added between evaluation questions to ensure reliability.