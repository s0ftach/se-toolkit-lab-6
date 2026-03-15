#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns structured JSON.
Task 3: System Agent with query_api tool.
"""

import json
import os
import sys
import time
import re
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.resolve()
MAX_TOOL_CALLS = 15


def load_env():
    """Load environment variables from .env files."""
    load_dotenv(PROJECT_ROOT / ".env.agent.secret")
    load_dotenv(PROJECT_ROOT / ".env.docker.secret")
    
    required = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    for var in required:
        if not os.getenv(var):
            print(f"Error: Missing {var}", file=sys.stderr)
            sys.exit(1)


def validate_path(path):
    """Security: prevent directory traversal."""
    if not path or path.startswith("/") or ".." in path:
        return None
    full = (PROJECT_ROOT / path).resolve()
    return full if str(full).startswith(str(PROJECT_ROOT)) else None


def read_file(path):
    """Read a file from the project."""
    print(f"📖 read_file('{path}')", file=sys.stderr)
    full = validate_path(path)
    if not full or not full.exists():
        return f"Error: File not found: {path}"
    try:
        return full.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: {e}"


def list_files(path):
    """List directory contents."""
    print(f"📁 list_files('{path}')", file=sys.stderr)
    full = validate_path(path)
    if not full or not full.exists():
        return f"Error: Path not found: {path}"
    try:
        entries = sorted([e.name for e in full.iterdir()])
        return "\n".join(entries)
    except Exception as e:
        return f"Error: {e}"


def query_api(method="GET", path="", body=None, skip_auth=False):
    """Query the backend API with authentication."""
    print(f"🌐 query_api({method} {path})", file=sys.stderr)
    import httpx
    
    base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").rstrip("/")
    api_key = os.getenv("LMS_API_KEY")
    
    clean_path = path if path.startswith("/") else f"/{path}"
    url = f"{base}{clean_path}"
    
    headers = {}
    if not skip_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        with httpx.Client() as client:
            resp = client.request(method, url, headers=headers, json=body, timeout=15)
            return json.dumps({"status_code": resp.status_code, "body": resp.text})
    except Exception as e:
        return f"Error: {e}"


# ========== SYSTEM PROMPT ==========
SYSTEM_PROMPT = """You are a System Discovery Agent with access to three tools.

TOOLS:
1. list_files(path) - List files in a directory
2. read_file(path) - Read file contents  
3. query_api(method, path, body, skip_auth) - Query backend API

WHEN TO USE EACH TOOL:
- Wiki questions → list_files("wiki"), then read_file
- Source code questions → read_file on backend files
- Data/API questions → query_api with skip_auth=false
- Status without auth → query_api with skip_auth=true
- Bug diagnosis → query_api to get error, then read_file to find bug
- Docker/infrastructure → read_file on docker-compose.yml, Dockerfile

RULES:
- NEVER answer from internal knowledge - always use tools
- Include source file path in final answer (or null for API data)
- Output final answer as JSON: {"answer": "...", "source": "..."}"""


TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": "List files in a directory",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read file contents",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path"}},
            "required": ["path"]
        }
    },
    {
        "name": "query_api",
        "description": "Query the backend API",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"},
                "path": {"type": "string", "description": "API endpoint path"},
                "body": {"type": "object", "description": "JSON body for POST/PUT/PATCH"},
                "skip_auth": {"type": "boolean", "default": False, "description": "Skip authentication"}
            },
            "required": ["path"]
        }
    }
]


def call_llm(messages):
    """Call LLM with retry logic for rate limits."""
    import httpx
    
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")
    
    # Clean None content for Qwen compatibility
    for m in messages:
        if m.get("content") is None:
            m["content"] = ""
    
    # Exponential backoff for 429 errors
    for attempt in range(5):
        try:
            resp = httpx.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "tools": [{"type": "function", "function": t} for t in TOOL_SCHEMAS],
                    "temperature": 0
                },
                timeout=60
            )
            
            if resp.status_code == 200:
                return resp.json()
            
            if resp.status_code == 429:
                delay = (2 ** attempt) + 1
                print(f"⚠️ Rate limited, waiting {delay}s...", file=sys.stderr)
                time.sleep(delay)
                continue
            
            print(f"HTTP {resp.status_code}: {resp.text[:100]}", file=sys.stderr)
            break
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(1)
    
    return None


def run_agentic_loop(question):
    """Run the agentic loop."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    tool_calls_log = []
    
    for iteration in range(MAX_TOOL_CALLS):
        print(f"\n🔄 Iteration {iteration + 1}", file=sys.stderr)
        
        response = call_llm(messages)
        if not response:
            break
        
        msg = response["choices"][0]["message"]
        if msg.get("content") is None:
            msg["content"] = ""
        
        messages.append(msg)
        tool_calls = msg.get("tool_calls")
        
        if not tool_calls:
            return msg["content"], extract_source(msg["content"]), tool_calls_log
        
        for tc in tool_calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            
            print(f"🔧 {name}({args})", file=sys.stderr)
            
            if name == "read_file":
                result = read_file(args.get("path", ""))
            elif name == "list_files":
                result = list_files(args.get("path", ""))
            elif name == "query_api":
                result = query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"), args.get("skip_auth", False))
            else:
                result = "Unknown tool"
            
            tool_calls_log.append({"tool": name, "args": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": str(result)
            })
    
    return "Timeout", None, tool_calls_log


def extract_source(answer):
    """Extract source file path from answer."""
    patterns = [
        r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)',
        r'(backend/[\w\-/]+\.py)',
        r'(docker-compose\.yml|Dockerfile)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, answer, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    
    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py 'question'", file=sys.stderr)
        sys.exit(1)
    
    load_env()
    question = sys.argv[1]
    
    print(f"🤖 Question: {question}", file=sys.stderr)
    
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
