"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields
and uses tools correctly.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with answer, source, and tool_calls fields."""
    # Get project root directory
    project_root = Path(__file__).parent.parent

    # Run agent with a simple question
    result = subprocess.run(
        ["uv", "run", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Verify answer is non-empty string
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Verify source is a string
    assert isinstance(output["source"], str), "'source' must be a string"

    # Verify tool_calls is a list
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    print("✓ All checks passed!")


def test_agent_uses_list_files_for_wiki_question():
    """Test that agent uses list_files tool when asked about wiki files."""
    project_root = Path(__file__).parent.parent

    # Run agent with a question about wiki
    result = subprocess.run(
        ["uv", "run", "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify tool_calls contains list_files
    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"

    # Verify answer and source exist
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"

    print("✓ list_files test passed!")


def test_agent_uses_read_file_for_git_question():
    """Test that agent uses read_file tool when asked about git workflow."""
    project_root = Path(__file__).parent.parent

    # Run agent with a question about git
    result = subprocess.run(
        ["uv", "run", "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root
    )

    # Check exit code
    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify tool_calls contains read_file
    tool_names = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Verify source contains wiki path
    assert "wiki/" in output["source"].lower() or "unknown" in output["source"].lower(), \
        f"Expected source to contain 'wiki/', got: {output['source']}"

    # Verify answer exists
    assert "answer" in output, "Missing 'answer' field"

    print("✓ read_file test passed!")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    test_agent_uses_list_files_for_wiki_question()
    test_agent_uses_read_file_for_git_question()
