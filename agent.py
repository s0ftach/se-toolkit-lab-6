#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns structured JSON.
"""

import json
import os
import sys
import time
import re
from pathlib import Path
from dotenv import load_dotenv

# ========== НАСТРОЙКИ ==========
PROJECT_ROOT = Path(__file__).parent.resolve()
MAX_TOOL_CALLS = 15
TIMEOUT_SECONDS = 120

# ========== ЗАГРУЗКА КОНФИГА ==========
def load_env():
    """Load environment variables."""
    env_path = PROJECT_ROOT / ".env.agent.secret"
    if not env_path.exists():
        print("❌ .env.agent.secret not found", file=sys.stderr)
        sys.exit(1)
    
    load_dotenv(env_path)
    
    required = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {missing}", file=sys.stderr)
        sys.exit(1)

# ========== ИНСТРУМЕНТЫ ==========
def validate_path(path):
    """Security: prevent directory traversal."""
    if not path or path.startswith("/") or ".." in path:
        return None
    full = (PROJECT_ROOT / path).resolve()
    return full if str(full).startswith(str(PROJECT_ROOT)) else None

def read_file(path):
    """Read a file."""
    print(f"📖 read_file('{path}')", file=sys.stderr)
    full = validate_path(path)
    if not full or not full.exists():
        return f"Error: File not found: {path}"
    if not full.is_file():
        return f"Error: Not a file: {path}"
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
    if not full.is_dir():
        return f"Error: Not a directory: {path}"
    try:
        return "\n".join(sorted([e.name for e in full.iterdir()]))
    except Exception as e:
        return f"Error: {e}"

def query_api(method="GET", path="", body=None, skip_auth=False):
    """Call backend API."""
    print(f"🌐 query_api({method}, '{path}', skip_auth={skip_auth})", file=sys.stderr)
    import httpx
    base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")

    headers = {}
    if not skip_auth and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.request(
            method=method,
            url=f"{base}{path}",
            headers=headers,
            json=body if body and method in ["POST", "PUT", "PATCH"] else None,
            timeout=10
        )
        return json.dumps({"status_code": resp.status_code, "body": resp.text})
    except Exception as e:
        return f"Error: {e}"

# ========== SYSTEM PROMPT ==========
SYSTEM_PROMPT = """You are an automated tool-calling assistant. You do not know answers — you MUST use tools.

AVAILABLE TOOLS:
1. list_files(path) — list files in a directory
2. read_file(path) — read file contents  
3. query_api(method, path, body, skip_auth) — query backend API

WHEN TO USE EACH TOOL:

**Wiki/Documentation questions** (e.g., "What does wiki say about SSH?"):
→ First call: list_files(path="wiki")
→ Then call: read_file(path="wiki/ssh.md") or relevant file

**Source code questions** (e.g., "What framework does backend use?"):
→ Call: read_file(path="backend/app/main.py")

**"List all" questions** (e.g., "List all API routers"):
→ First call: list_files(path="backend/app/routers")
→ Then call: read_file on each router file

**Data/API questions** (e.g., "How many items in database?"):
→ Call: query_api(method="GET", path="/items/", skip_auth=false)

**Status code without auth** (e.g., "What status code without authentication?"):
→ Call: query_api(method="GET", path="/items/", skip_auth=true)

**Bug diagnosis** (e.g., "What error does /analytics/completion-rate return?"):
→ First call: query_api to get error
→ Then call: read_file to find bug in source code

**Infrastructure questions** (e.g., "Explain request flow"):
→ Call: read_file on docker-compose.yml, Dockerfile, etc.

IMPORTANT RULES:
- NEVER answer from your knowledge — always use tools first
- Call multiple tools if needed before giving final answer
- When you have complete answer, output ONLY JSON: {"answer": "...", "source": "..."}
- Include source file path for wiki/code questions
- For API data questions, source can be null

EXAMPLES:
- "What files in wiki?" → list_files("wiki")
- "How to resolve merge conflict?" → read_file("wiki/git-workflow.md")
- "What framework?" → read_file("backend/app/main.py")
- "How many items?" → query_api("/items/")
- "Status without auth?" → query_api("/items/", skip_auth=true)
"""

TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": "List files in a directory. Use to discover project structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (e.g., 'wiki', 'backend/app')"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read contents of a file. Use for source code, documentation, configuration files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (e.g., 'wiki/ssh.md', 'backend/app/main.py')"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "query_api",
        "description": "Query the backend API to get data, check status codes, or test endpoints.",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"},
                "path": {"type": "string", "description": "API path (e.g., '/items/', '/analytics/completion-rate?lab=lab-01')"},
                "body": {"type": "object", "description": "JSON body for POST/PUT/PATCH requests"},
                "skip_auth": {"type": "boolean", "description": "Set to true to skip authentication (test unauthenticated access). Default: false.", "default": False}
            },
            "required": ["path"]
        }
    }
]

# ========== ВЫЗОВ LLM ==========
def call_llm(messages):
    """Call LLM API with tool support."""
    import httpx

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    max_retries = 5
    retry_delay = 3  # seconds

    for attempt in range(max_retries):
        try:
            resp = httpx.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "tools": [{"type": "function", "function": t} for t in TOOL_SCHEMAS],
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=90
            )
            
            # Handle rate limiting
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    print(f"⚠️ Rate limited, retrying in {retry_delay}s... (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                    time.sleep(retry_delay)
                    retry_delay *= 2  # exponential backoff
                    continue
                else:
                    print(f"❌ Rate limited after {max_retries} attempts", file=sys.stderr)
                    return None
            
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if attempt < max_retries - 1:
                print(f"⚠️ HTTP error {e.response.status_code}, retrying in {retry_delay}s... (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"❌ LLM HTTP error: {e}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"❌ LLM error: {e}", file=sys.stderr)
            return None
    
    return None

# ========== ИЗВЛЕЧЕНИЕ ИСТОЧНИКА ==========
def extract_source(answer, tool_calls_log):
    """Extract source from answer or tool calls."""
    # Ищем wiki/файл.md в ответе
    match = re.search(r'(wiki/[\w\-/]+\.md)', answer, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Ищем backend/файл.py в ответе
    match = re.search(r'(backend/[\w\-/]+\.py)', answer, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Ищем последний прочитанный wiki-файл
    for tc in reversed(tool_calls_log):
        if tc["tool"] == "read_file":
            path = tc["args"].get("path", "")
            if "wiki" in path:
                return path.lower()
            if "backend" in path and path.endswith(".py"):
                return path.lower()
    
    return None

# ========== ОСНОВНОЙ ЦИКЛ ==========
def run_agentic_loop(question):
    """Run the agent with tools."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    tool_calls_log = []
    start_time = time.time()
    
    for iteration in range(MAX_TOOL_CALLS):
        if time.time() - start_time > TIMEOUT_SECONDS:
            print(f"⏱️ Timeout after {TIMEOUT_SECONDS}s", file=sys.stderr)
            break
        
        print(f"\n🔄 Iteration {iteration+1}", file=sys.stderr)
        
        response = call_llm(messages)
        if not response:
            break
        
        choices = response.get("choices", [])
        if not choices:
            print("❌ No choices in response", file=sys.stderr)
            break
            
        choice = choices[0]
        message = choice.get("message", {})
        
        tool_calls = message.get("tool_calls")
        
        if tool_calls:
            # Выполняем инструменты
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                name = func.get("name", "")
                args_str = func.get("arguments", "{}")
                
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
                
                print(f"🔧 Calling: {name}({args})", file=sys.stderr)
                
                if name == "read_file":
                    result = read_file(args.get("path", ""))
                elif name == "list_files":
                    result = list_files(args.get("path", ""))
                elif name == "query_api":
                    result = query_api(
                        args.get("method", "GET"),
                        args.get("path", ""),
                        args.get("body"),
                        args.get("skip_auth", False)
                    )
                else:
                    result = f"Unknown tool: {name}"
                
                tool_calls_log.append({
                    "tool": name,
                    "args": args,
                    "result": result
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": result
                })
        else:
            # Финальный ответ
            answer = message.get("content", "")
            source = extract_source(answer, tool_calls_log)
            return answer, source, tool_calls_log
    
    return "Timeout or max iterations reached", None, tool_calls_log

# ========== ТОЧКА ВХОДА ==========
def main():
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py 'question'", file=sys.stderr)
        sys.exit(1)
    
    load_env()
    question = sys.argv[1]
    
    print(f"\n🤖 Question: {question}", file=sys.stderr)
    
    answer, source, tool_calls = run_agentic_loop(question)
    
    output = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }
    
    # ТОЛЬКО JSON В STDOUT
    print(json.dumps(output))
    
    print(f"\n✅ Done. Tool calls: {len(tool_calls)}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
