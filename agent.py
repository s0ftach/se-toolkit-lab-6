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

    # LMS_API_KEY is required for query_api
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
    """
    Validate that a path is safe and within the project directory.
    Returns the resolved absolute path or None if invalid.
    """
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
    """
    Call Qwen CLI and return the response.
    
    Args:
        messages: List of message dicts with role and content
        tools: List of tool schemas
    
    Returns:
        Dict with 'content' and/or 'tool_calls'
    """
    # Build the prompt with tool definitions
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
    
    # Add tool definitions to system message
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
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "content": parsed.get("content", ""),
                    "tool_calls": parsed.get("tool_calls", [])
                }
        except json.JSONDecodeError:
            pass
        
        # Return as plain text
        return {"content": response_text, "tool_calls": []}
        
    except subprocess.TimeoutExpired:
        return {"content": "Error: LLM timeout", "tool_calls": []}
    except Exception as e:
        return {"content": f"Error calling LLM: {e}", "tool_calls": []}


def run_agentic_loop(question):
    """Run the agentic loop with Qwen CLI."""
    tool_schemas = get_tool_schemas()
    
    system_prompt = """You are a documentation and system assistant that helps users find information in the project wiki, source code, and deployed backend API.

You have access to three tools:
1. read_file - Read the contents of a file (source code, documentation, configuration)
2. list_files - List files and directories in a folder  
3. query_api - Call the deployed backend API to query data or test endpoints

CRITICAL RULES:
1. For ANY question about wiki documentation - you MUST use read_file to read the file content before answering
2. list_files returns ONLY file names - it does NOT contain the content you need to answer
3. After using list_files, you MUST use read_file on the relevant file(s) to get the actual information
4. NEVER answer based on list_files results alone - that's just a file listing!

Step-by-step process:
1. Use list_files to find which files exist
2. Use read_file to read the specific file(s) that contain the answer
3. Only then provide your answer based on what you READ

For data/API questions: Use query_api to get the data first.

Always respond in JSON format: {"content": "...", "tool_calls": [...]}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    iteration = 0
    
    while iteration < MAX_TOOL_CALLS:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---", file=sys.stderr)
        
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
    """Extract source reference from the answer or tool calls."""
    import re
    
    # First try to find wiki/ pattern
    pattern = r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)'
    match = re.search(pattern, answer, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Try backend/ pattern
    pattern = r'(backend/[\w\-/]+\.py)'
    match = re.search(pattern, answer, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Try to find .md file references and assume wiki/
    pattern = r'\b([\w\-]+\.md)\b'
    match = re.search(pattern, answer, re.IGNORECASE)
    if match:
        return f"wiki/{match.group(1).lower()}"
    
    # Check tool calls for read_file with wiki path
    for tc in tool_calls_log:
        if tc.get('tool') == 'read_file':
            path = tc.get('args', {}).get('path', '')
            if path.startswith('wiki/'):
                return path.lower()
    
    # Try API pattern
    pattern = r'(/[\w\-/]+/)'
    match = re.search(pattern, answer)
    if match:
        return f"API: {match.group(1)}"
    
    return "unknown"


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
    
    # If source is still unknown, try to extract from answer/tool_calls
    if source == "unknown":
        source = extract_source(answer, tool_calls)
    
    output = {
        "answer": answer,
        "source": source if source != "unknown" else None,
        "tool_calls": tool_calls
    }
    
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
