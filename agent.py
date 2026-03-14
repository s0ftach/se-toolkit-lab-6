#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer" and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def load_env():
    """Load environment variables from .env.agent.secret."""
    env_path = Path(__file__).parent / ".env.agent.secret"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)
    
    load_dotenv(env_path)
    
    required_vars = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    for var in required_vars:
        if not os.getenv(var):
            print(f"Error: Missing required env var: {var}", file=sys.stderr)
            sys.exit(1)


def create_client():
    """Create and return the OpenAI-compatible client."""
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    
    return OpenAI(
        api_key=api_key,
        base_url=api_base
    )


def get_answer(client, question):
    """Send question to LLM and return the answer."""
    model = os.getenv("LLM_MODEL")
    
    print(f"Sending question to LLM: {question}", file=sys.stderr)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Answer questions concisely and accurately."},
            {"role": "user", "content": question}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    answer = response.choices[0].message.content
    print(f"Received answer from LLM", file=sys.stderr)
    
    return answer


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load environment
    load_env()
    print("Environment loaded", file=sys.stderr)
    
    # Create client
    client = create_client()
    print(f"Client created for model: {os.getenv('LLM_MODEL')}", file=sys.stderr)
    
    # Get answer from LLM
    answer = get_answer(client, question)
    
    # Build output
    output = {
        "answer": answer,
        "tool_calls": []
    }
    
    # Output JSON to stdout
    print(json.dumps(output))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
