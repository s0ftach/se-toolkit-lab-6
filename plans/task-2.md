# Task 2 Plan: The Documentation Agent

## Overview

Extend the agent from Task 1 with tools (`read_file`, `list_files`) and an agentic loop. The agent will navigate the project wiki to answer questions.

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** qwen3-coder-plus
- **API Compatibility:** OpenAI-compatible function calling API

## Tool Definitions

### 1. `read_file`

**Purpose:** Read a file from the project repository.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root"
      }
    },
    "required": ["path"]
  }
}
```

**Security:** Validate path doesn't contain `..` traversal.

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories at a given path",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root"
      }
    },
    "required": ["path"]
  }
}
```

**Security:** Validate path doesn't contain `..` traversal.

## Agentic Loop

```
1. Send user question + tool schemas to LLM
2. Parse response:
   - If tool_calls: execute each tool, append results, go to step 1
   - If text answer: extract answer + source, output JSON, exit
3. Max 10 iterations (prevent infinite loops)
```

### Message Flow

```
User: "How do you resolve a merge conflict?"

→ Send to LLM: [system prompt] + [user question] + [tool schemas]

← LLM: {"tool_calls": [{"name": "list_files", "arguments": {"path": "wiki"}}]}

→ Execute list_files("wiki")
→ Send results back: [{"role": "tool", "content": "...", "tool_call_id": "..."}]

← LLM: {"tool_calls": [{"name": "read_file", "arguments": {"path": "wiki/git-workflow.md"}}]}

→ Execute read_file("wiki/git-workflow.md")
→ Send results back

← LLM: {"content": "To resolve... (see wiki/git-workflow.md#resolving-merge-conflicts)"}

→ Output JSON: {"answer": "...", "source": "wiki/git-workflow.md#resolving-merge-conflicts", "tool_calls": [...]}
```

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to find specific information
3. Include source references (file path + section anchor) in the answer
4. Call tools step by step (don't parallelize unnecessarily)

## Path Security

- Resolve all paths against project root
- Reject paths containing `..` (directory traversal)
- Reject absolute paths
- Use `pathlib.Path.resolve()` to canonicalize paths

## Implementation Steps

1. ✅ Create `plans/task-2.md` (this file)
2. ⬜ Update `agent.py`:
   - Add tool schemas
   - Implement `read_file` and `list_files` functions
   - Implement agentic loop (max 10 iterations)
   - Update output format (add `source` field)
3. ⬜ Update `AGENT.md` documentation
4. ⬜ Add 2 regression tests

## Testing

Test questions:
1. "How do you resolve a merge conflict?" → expects `read_file`, source contains `wiki/git-workflow.md`
2. "What files are in the wiki?" → expects `list_files`

Run with:
```bash
uv run pytest tests/test_agent.py -v
```
