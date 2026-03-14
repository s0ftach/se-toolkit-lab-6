#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer", "source" (optional), and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI


# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10


def load_env():
    """Load environment variables from .env.agent.secret and .env.docker.secret."""
    # Load .env.agent.secret for LLM config
    agent_env_path = Path(__file__).parent / ".env.agent.secret"
    if agent_env_path.exists():
        load_dotenv(agent_env_path)
    else:
        print(f"Warning: {agent_env_path} not found", file=sys.stderr)

    # Load .env.docker.secret for LMS API key
    docker_env_path = Path(__file__).parent / ".env.docker.secret"
    if docker_env_path.exists():
        load_dotenv(docker_env_path, override=False)
    else:
        print(f"Warning: {docker_env_path} not found", file=sys.stderr)

    # Validate LLM required vars
    llm_required_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    for var in llm_required_vars:
        if not os.getenv(var):
            print(f"Error: Missing required LLM env var: {var}", file=sys.stderr)
            sys.exit(1)

    # LMS_API_KEY is required for query_api
    if not os.getenv("LMS_API_KEY"):
        print("Error: Missing required env var: LMS_API_KEY", file=sys.stderr)
        sys.exit(1)


def create_client():
    """Create and return the OpenAI-compatible client."""
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")

    return OpenAI(
        api_key=api_key,
        base_url=api_base
    )


def get_tool_schemas():
    """Return the tool schemas for function calling."""
    return [
        {
            "name": "read_file",
            "description": "Read a file from the project repository. Use for source code, documentation, configuration files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_files",
            "description": "List files and directories at a given path. Use to discover project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend')"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "query_api",
            "description": "Call the deployed backend API to query data, check status codes, or test endpoints. Use for runtime data and system behavior.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
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
    ]


def validate_path(path_str):
    """
    Validate that a path is safe and within the project directory.
    Returns the resolved absolute path or None if invalid.
    """
    # Reject empty paths
    if not path_str or not path_str.strip():
        return None

    # Reject absolute paths
    if path_str.startswith("/"):
        return None

    # Reject paths with traversal
    if ".." in path_str:
        return None

    # Resolve the path against project root
    try:
        full_path = (PROJECT_ROOT / path_str).resolve()

        # Ensure the resolved path is within project root
        if not str(full_path).startswith(str(PROJECT_ROOT)):
            return None

        return full_path
    except Exception:
        return None


def read_file(path):
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    print(f"Tool: read_file('{path}')", file=sys.stderr)

    validated_path = validate_path(path)
    if validated_path is None:
        return f"Error: Invalid path '{path}'"

    if not validated_path.exists():
        return f"Error: File not found: {path}"

    if not validated_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        content = validated_path.read_text(encoding="utf-8")
        print(f"  Read {len(content)} characters", file=sys.stderr)
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path):
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing, or error message
    """
    print(f"Tool: list_files('{path}')", file=sys.stderr)

    validated_path = validate_path(path)
    if validated_path is None:
        return f"Error: Invalid path '{path}'"

    if not validated_path.exists():
        return f"Error: Path not found: {path}"

    if not validated_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted([e.name for e in validated_path.iterdir()])
        result = "\n".join(entries)
        print(f"  Found {len(entries)} entries", file=sys.stderr)
        return result
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method, path, body=None):
    """
    Call the deployed backend API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path
        body: Optional JSON request body

    Returns:
        JSON string with status_code and body, or error message
    """
    print(f"Tool: query_api('{method}', '{path}', body={body})", file=sys.stderr)

    # Get API base URL from environment or use default
    api_base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")

    # Build URL
    url = f"{api_base.rstrip('/')}{path}"

    # Prepare headers
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, json=json.loads(body) if body else None)
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, json=json.loads(body) if body else None)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            elif method.upper() == "PATCH":
                response = client.patch(url, headers=headers, json=json.loads(body) if body else None)
            else:
                return f"Error: Unknown method: {method}"

        result = {
            "status_code": response.status_code,
            "body": response.text
        }
        result_str = json.dumps(result)
        print(f"  Status: {response.status_code}, Body: {len(response.text)} chars", file=sys.stderr)
        return result_str

    except httpx.ConnectError as e:
        return f"Error: Cannot connect to API at {url}: {e}"
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON body: {e}"
    except Exception as e:
        return f"Error: {e}"


def execute_tool(tool_name, args):
    """
    Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Dictionary of arguments

    Returns:
        Tool result as string
    """
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    elif tool_name == "query_api":
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body")
        )
    else:
        return f"Error: Unknown tool: {tool_name}"


def run_agentic_loop(client, question):
    """
    Run the agentic loop: send question to LLM, execute tool calls, repeat.

    Args:
        client: OpenAI client
        question: User's question

    Returns:
        Tuple of (answer, source, tool_calls_list)
    """
    model = os.getenv("LLM_MODEL")
    tool_schemas = get_tool_schemas()

    # System prompt instructs the LLM how to use tools
    system_prompt = """You are a documentation and system assistant that helps users find information in the project wiki, source code, and deployed backend API.

You have access to three tools:
1. read_file - Read the contents of a file (source code, documentation, configuration)
2. list_files - List files and directories in a folder
3. query_api - Call the deployed backend API to query data or test endpoints

To answer questions:
- For wiki/documentation questions: Use list_files to discover files, then read_file to find the answer
- For source code questions: Use list_files to find relevant modules, then read_file to read the code
- For data queries (item count, scores, etc.): Use query_api to query the backend
- For system facts (framework, ports, status codes): Use query_api to test endpoints or read_file on source code
- For bug diagnosis: Use query_api to reproduce the error, then read_file to find the bug in source code

When you find the answer:
- For wiki/source answers: Include a source reference (file path + optional section anchor)
- For API answers: The source is the API endpoint you queried

Rules:
- Call tools one at a time, waiting for results before making the next call
- If you can't find the answer after exploring, say so honestly
- Section anchors are lowercase with hyphens (e.g., #resolving-merge-conflicts)
- For API queries, use the exact endpoint paths (e.g., /items/, /analytics/completion-rate)"""

    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    tool_calls_log = []
    iteration = 0

    while iteration < MAX_TOOL_CALLS:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---", file=sys.stderr)

        # Send request to LLM
        print(f"Sending to LLM: {len(messages)} messages", file=sys.stderr)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )

        choice = response.choices[0]
        message = choice.message

        # Check if LLM wants to call tools
        if message.tool_calls:
            # Log tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"LLM wants to call: {tool_name}({tool_args})", file=sys.stderr)

                # Execute the tool
                result = execute_tool(tool_name, tool_args)

                # Log to our record
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

            # Continue loop - LLM will process tool results
            continue
        else:
            # LLM provided final answer
            answer = message.content or ""
            print(f"LLM provided final answer", file=sys.stderr)

            # Extract source from answer (look for wiki/...md#... pattern or API endpoints)
            source = extract_source(answer)

            return answer, source, tool_calls_log

    # Max iterations reached
    print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)

    # Try to extract answer from last message
    if tool_calls_log:
        last_result = tool_calls_log[-1]["result"]
        return f"Answer based on available data: {last_result[:500]}...", "unknown", tool_calls_log

    return "Unable to find answer within tool call limit", "unknown", tool_calls_log


def extract_source(answer):
    """
    Extract source reference from the answer.
    Looks for patterns like wiki/filename.md, backend/...py, or API endpoints.
    """
    import re

    # Look for wiki file references
    pattern = r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)'
    match = re.search(pattern, answer, re.IGNORECASE)

    if match:
        return match.group(1).lower()

    # Look for backend source files
    pattern = r'(backend/[\w\-/]+\.py)'
    match = re.search(pattern, answer, re.IGNORECASE)

    if match:
        return match.group(1).lower()

    # Look for API endpoints
    pattern = r'(/[\w\-/]+/)'
    match = re.search(pattern, answer)

    if match:
        return f"API: {match.group(1)}"

    # Default if no source found
    return "unknown"


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load environment
    load_env()
    print("Environment loaded", file=sys.stderr)

    # Create client
    client = create_client()
    print(f"Client created for model: {os.getenv('LLM_MODEL')}", file=sys.stderr)

    # Run agentic loop
    answer, source, tool_calls = run_agentic_loop(client, question)

    # Build output - source is now optional (can be null for system questions)
    output = {
        "answer": answer,
        "source": source if source != "unknown" else None,
        "tool_calls": tool_calls
    }

    # Output JSON to stdout
    print(json.dumps(output))

    return 0


if __name__ == "__main__":
    sys.exit(main())
