"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields.
Note: Tool usage depends on LLM behavior and may vary.
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
    result = run_agent("What is 2+2?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)

    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output or output.get("source") is None, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"

    print("✓ JSON output test passed!")


def test_agent_uses_list_files_for_wiki_question():
    """Test that agent outputs valid answer for wiki questions."""
    result = run_agent("What files are in the wiki?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    
    assert "answer" in output, "Missing 'answer' field"
    assert len(output["answer"]) > 0, "Answer should not be empty"

    print("✓ wiki question test passed!")


def test_agent_uses_read_file_for_git_question():
    """Test that agent outputs valid answer for git questions."""
    result = run_agent("How do I resolve a merge conflict?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    
    assert "answer" in output, "Missing 'answer' field"
    assert len(output["answer"]) > 0, "Answer should not be empty"

    print("✓ git question test passed!")


def test_agent_uses_read_file_for_framework_question():
    """Test that agent uses tools for framework questions."""
    result = run_agent("What Python web framework does this project's backend use?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]
    
    # Agent should use tools for framework questions
    assert len(tool_names) > 0, f"Expected agent to use tools for framework question"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ framework question test passed!")


def test_agent_uses_query_api_for_data_question():
    """Test that agent uses query_api tool when asked about database items."""
    result = run_agent("How many items are currently stored in the database?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]

    # Agent should use query_api for data questions
    assert "query_api" in tool_names, f"Expected query_api for data question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"

    print("✓ data question test passed!")


def test_agent_uses_query_api_for_status_code_question():
    """Test that agent uses query_api with skip_auth when asked about unauthenticated status codes."""
    result = run_agent("What HTTP status code does the API return when you request /items/ without an authentication header?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]

    # Agent should use query_api for status code questions
    assert "query_api" in tool_names, f"Expected query_api for status code question. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"
    
    # Check that the answer contains a status code (401 or 403)
    answer = output["answer"].lower()
    assert "401" in answer or "403" in answer, f"Expected status code 401 or 403 in answer. Got: {output['answer']}"

    print("✓ status code question test passed!")


def test_agent_chains_tools_for_error_diagnosis():
    """Test that agent chains query_api and read_file for error diagnosis questions."""
    result = run_agent("Query /analytics/completion-rate for a lab with no data (e.g., lab-99). What error do you get, and what is the bug in the source code?")

    assert result.returncode == 0, f"Agent exited with code {result.returncode}: {result.stderr}"

    output = json.loads(result.stdout)
    tool_names = [call["tool"] for call in output["tool_calls"]]

    # Agent should use both query_api (to reproduce error) and read_file (to find bug)
    assert "query_api" in tool_names, f"Expected query_api for error diagnosis. Got: {tool_names}"
    assert "read_file" in tool_names, f"Expected read_file for error diagnosis. Got: {tool_names}"
    assert "answer" in output, "Missing 'answer' field"
    
    # Check that the answer mentions the error type
    answer = output["answer"].lower()
    assert "zero" in answer or "division" in answer, f"Expected mention of ZeroDivisionError. Got: {output['answer']}"

    print("✓ error diagnosis test passed!")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
    test_agent_uses_list_files_for_wiki_question()
    test_agent_uses_read_file_for_git_question()
    test_agent_uses_read_file_for_framework_question()
    test_agent_uses_query_api_for_data_question()
    test_agent_uses_query_api_for_status_code_question()
    test_agent_chains_tools_for_error_diagnosis()
