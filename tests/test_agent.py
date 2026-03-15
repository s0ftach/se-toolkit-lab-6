"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields
and uses tools correctly.

Note: Tests use cached questions to avoid LLM rate limits on free tier models.
"""

import json
import subprocess
from pathlib import Path
import time


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
    elapsed = time.time() - start
    print(f"    [debug] Agent completed in {elapsed:.1f}s", file=sys.stderr)
    return result


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with answer and tool_calls fields."""
    result = run_agent("What is 2+2?", timeout=300)


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
    """Test that agent uses list_files tool for wiki questions."""
    # Use cached question
    result = run_agent("According to the project wiki, what steps are needed to protect a branch on GitHub?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    assert "list_files" in tool_names, "Expected list_files to be called"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ list_files test passed!")


def test_agent_uses_read_file_for_git_question():
    """Test that agent uses read_file tool for SSH/wiki questions."""
    # Use cached question
    result = run_agent("What does the project wiki say about connecting to your VM via SSH?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    assert "read_file" in tool_names, "Expected read_file to be called"
    assert "wiki/" in output["source"].lower(), f"Expected source to contain 'wiki/', got: {output['source']}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ read_file test passed!")


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses read_file tool when asked about backend framework."""
    # Use cached question
    result = run_agent("What Python web framework does this project's backend use?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    assert "read_file" in tool_names, f"Expected read_file for framework question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ framework question test passed!")


def test_agent_uses_query_api_for_data_question():
    """Test that agent uses query_api tool when asked about database items."""
    # Use cached question
    result = run_agent("How many items are currently stored in the database?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    assert "query_api" in tool_names, f"Expected query_api for data question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ data question test passed!")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    test_agent_uses_list_files_for_wiki_question()
    test_agent_uses_read_file_for_git_question()
    test_agent_uses_read_file_for_framework_question()
    test_agent_uses_query_api_for_data_question()
