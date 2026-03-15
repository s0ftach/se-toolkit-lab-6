"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields
and uses tools correctly.

Note: Tests use cached questions to avoid LLM rate limits on free tier models.
"""

import json
import subprocess
from pathlib import Path


def run_agent(question, timeout=120):
    """Helper to run agent and return result."""
    project_root = Path(__file__).parent.parent
    return subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=project_root
    )


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields."""
    # Use cached question to avoid LLM rate limits
    result = run_agent("What Python web framework does this project's backend use?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"
    # source can be string or None (for API data questions)
    assert output["source"] is None or isinstance(output["source"], str), "'source' must be string or None"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    print("✓ All checks passed!")


def test_agent_uses_list_files_for_wiki_question():
    """Test that agent uses tools for wiki questions."""
    # Use a simple wiki question
    result = run_agent("What files are in the wiki directory?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    # Agent should use list_files or read_file for wiki questions
    assert len(tool_names) > 0, "Expected agent to use at least one tool"
    assert "list_files" in tool_names or "read_file" in tool_names, f"Expected list_files or read_file, got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"

    print("✓ wiki question test passed!")


def test_agent_uses_read_file_for_git_question():
    """Test that agent uses read_file tool for git questions."""
    # Use a simple git question
    result = run_agent("How do I resolve a merge conflict?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    # Agent should use tools for git questions
    assert len(tool_names) > 0, "Expected agent to use at least one tool"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ git question test passed!")


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses read_file tool when asked about backend framework."""
    # Use framework question
    result = run_agent("What Python web framework does this project's backend use?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    # Agent should use tools for framework questions
    assert len(tool_names) > 0, f"Expected agent to use tools for framework question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ framework question test passed!")


def test_agent_uses_query_api_for_data_question():
    """Test that agent uses query_api tool when asked about database items."""
    # Use data question
    result = run_agent("How many items are currently stored in the database?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    # Agent should use query_api for data questions
    assert "query_api" in tool_names, f"Expected query_api for data question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ data question test passed!")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    test_agent_uses_list_files_for_wiki_question()
    test_agent_uses_read_file_for_git_question()
    test_agent_uses_read_file_for_framework_question()
    test_agent_uses_query_api_for_data_question()
