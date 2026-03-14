"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with answer and tool_calls fields."""
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
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    
    # Verify answer is non-empty string
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"
    
    # Verify tool_calls is a list
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
    
    print("✓ All checks passed!")


if __name__ == "__main__":
    test_agent_outputs_valid_json()
