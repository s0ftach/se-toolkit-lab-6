"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields
and uses tools correctly.

Note: These tests use a free tier LLM model which may be slow or rate-limited.
Increase timeouts if tests fail due to timeout.
"""

import json
import subprocess
import sys
from pathlib import Path
import time


def run_agent(question, timeout=300):
    """Helper to run agent and parse output."""
    project_root = Path(__file__).parent.parent
    start = time.time()
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=project_root
    )
    elapsed = time.time() - start
    print(f"    [debug] Agent completed in {elapsed:.1f}s", file=sys.stderr)
    return result


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with answer and tool_calls fields."""
    result = run_agent("What is 2+2?", timeout=300)

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    print("✓ All checks passed!")


def test_agent_uses_list_files_for_wiki_question():
    """Test that agent uses list_files tool when asked about wiki files."""
    result = run_agent("What files are in the wiki?", timeout=300)

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ list_files test passed!")


def test_agent_uses_read_file_for_git_question():
    """Test that agent uses read_file tool when asked about git workflow."""
    result = run_agent("How do you resolve a merge conflict?", timeout=300)

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ read_file test passed!")


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses read_file tool when asked about backend framework."""
    result = run_agent("What Python web framework does this project's backend use?", timeout=300)

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tool_names, f"Expected read_file to be called for framework question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ framework question test passed!")


def test_agent_uses_query_api_for_data_question():
    """Test that agent uses query_api tool when asked about database items."""
    result = run_agent("How many items are currently stored in the database?", timeout=300)

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "query_api" in tool_names, "Expected query_api to be called for data question"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ data question test passed!")


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses read_file tool when asked about backend framework."""
    result = run_agent("What Python web framework does this project's backend use?")

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify tool_calls contains read_file
    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tool_names, f"Expected read_file to be called for framework question. Got: {tool_names}"

    # Verify answer exists
    assert "answer" in output, "Missing 'answer' field"

    print("✓ framework question test passed!")


def test_agent_uses_query_api_for_data_question():
    """Test that agent uses query_api tool when asked about database items."""
    result = run_agent("How many items are currently stored in the database?")

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify tool_calls contains query_api
    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "query_api" in tool_names, f"Expected query_api to be called for data question. Got: {tool_names}"

    # Verify answer exists
    assert "answer" in output, "Missing 'answer' field"

    print("✓ data question test passed!")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    test_agent_uses_list_files_for_wiki_question()
    test_agent_uses_read_file_for_git_question()
    test_agent_uses_read_file_for_framework_question()
    test_agent_uses_query_api_for_data_question()
