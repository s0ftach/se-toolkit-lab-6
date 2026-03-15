#!/usr/bin/env python3
"""
Agent CLI - Calls Qwen CLI with tools and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer", "source" (optional), and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

from dotenv import load_dotenv


# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# Path to Qwen CLI
QWEN_CLI_PATH = os.path.expanduser("~/.local/share/pnpm/qwen")


def load_env():
    """Load environment variables from .env.agent.secret and .env.docker.secret."""
    agent_env_path = Path(__file__).parent / ".env.agent.secret"
    if agent_env_path.exists():
        load_dotenv(agent_env_path)
    else:
        print(f"Warning: {agent_env_path} not found", file=sys.stderr)

    docker_env_path = Path(__file__).parent / ".env.docker.secret"
    if docker_env_path.exists():
        load_dotenv(docker_env_path, override=False)
    else:
        print(f"Warning: {docker_env_path} not found", file=sys.stderr)

    if not os.getenv("LMS_API_KEY"):
        print("Error: Missing required env var: LMS_API_KEY", file=sys.stderr)
        sys.exit(1)


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
    """Validate that a path is safe and within the project directory."""
    if not path_str or not path_str.strip():
        return None
    if path_str.startswith("/"):
        return None
    if ".." in path_str:
        return None
    try:
        full_path = (PROJECT_ROOT / path_str).resolve()
        if not str(full_path).startswith(str(PROJECT_ROOT)):
            return None
        return full_path
    except Exception:
        return None


def read_file(path):
    """Read a file from the project repository."""
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
    """List files and directories at a given path."""
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
    """Call the deployed backend API."""
    print(f"Tool: query_api('{method}', '{path}', body={body})", file=sys.stderr)
    api_base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")
    url = f"{api_base.rstrip('/')}{path}"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
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
        result = {"status_code": response.status_code, "body": response.text}
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
    """Execute a tool and return the result."""
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    elif tool_name == "query_api":
        return query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"))
    else:
        return f"Error: Unknown tool: {tool_name}"


def call_llm(messages, tools):
    """Call Qwen CLI and return the response."""
    # Build tool definitions
    tool_defs = "\n\nAvailable tools:\n"
    for tool in tools:
        tool_defs += f"- {tool['name']}: {tool['description']}\n"
        tool_defs += f"  Parameters: {json.dumps(tool['parameters'])}\n"
    
    # Build conversation history
    prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            prompt += f"System: {content}\n"
        elif role == "user":
            prompt += f"User: {content}\n"
        elif role == "tool":
            prompt += f"Tool Result: {content}\n"
        elif role == "assistant":
            prompt += f"Assistant: {content}\n"
    
    full_prompt = tool_defs + "\n" + prompt
    full_prompt += "\nRespond in JSON format: {\"content\": \"...\", \"tool_calls\": [{\"name\": \"...\", \"arguments\": {...}}]}\n"
    full_prompt += "If no tool calls needed, return: {\"content\": \"your answer\"}\n"
    
    print(f"Calling Qwen CLI with {len(messages)} messages", file=sys.stderr)
    
    try:
        result = subprocess.run(
            [QWEN_CLI_PATH, full_prompt],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        response_text = result.stdout.strip()
        print(f"Qwen CLI response: {response_text[:200]}...", file=sys.stderr)
        
        # Try to parse as JSON
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                "content": parsed.get("content", ""),
                "tool_calls": parsed.get("tool_calls", [])
            }
        
        # Return as plain text
        return {"content": response_text, "tool_calls": []}
        
    except subprocess.TimeoutExpired:
        return {"content": "Error: LLM timeout", "tool_calls": []}
    except Exception as e:
        return {"content": f"Error calling LLM: {e}", "tool_calls": []}


def run_agentic_loop(question):
    """Run the agentic loop with Qwen CLI."""
    tool_schemas = get_tool_schemas()
    
    system_prompt = """You are an AI assistant for a software engineering project.
You have access to tools: read_file, list_files, query_api.

RULES:
1. For wiki questions: FIRST list_files("wiki"), THEN read_file relevant files
2. ALWAYS include source reference in format "wiki/filename.md"
3. Answer questions completely based on file contents
4. If you need more info, use tools - don't guess

Respond in JSON format with 'content' and 'tool_calls' fields."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    max_iterations = 10
    
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---", file=sys.stderr)
        
        response = call_llm(messages, tool_schemas)
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                
                print(f"LLM wants to call: {tool_name}({tool_args})", file=sys.stderr)
                
                result = execute_tool(tool_name, tool_args)
                
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
                
                messages.append({
                    "role": "tool",
                    "content": result
                })
            continue
        else:
            answer = content
            print(f"LLM provided final answer", file=sys.stderr)
            source = extract_source(answer, tool_calls_log)
            return answer, source, tool_calls_log
    
    print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
    if tool_calls_log:
        last_result = tool_calls_log[-1]["result"]
        return f"Answer based on available data: {last_result[:500]}...", "unknown", tool_calls_log
    return "Unable to find answer within tool call limit", "unknown", tool_calls_log


def extract_source(answer, tool_calls_log):
    """Extract source from answer or tool calls."""
    import re
    
    # Look for wiki/file.md in answer
    match = re.search(r'(wiki/[\w\-/]+\.md)', answer, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Look for backend/...py
    match = re.search(r'(backend/[\w\-/]+\.py)', answer, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Check last read_file with wiki path
    for tc in reversed(tool_calls_log):
        if tc["tool"] == "read_file" and "wiki" in tc["args"].get("path", ""):
            return tc["args"]["path"].lower()
    
    # Check for API endpoint
    match = re.search(r'(/[\w\-/]+/)', answer)
    if match:
        return f"API: {match.group(1)}"
    
    return None


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    load_env()
    print("Environment loaded", file=sys.stderr)
    print(f"Using Qwen CLI: {QWEN_CLI_PATH}", file=sys.stderr)

    answer, source, tool_calls = run_agentic_loop(question)

    output = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
