#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List available Gemini models."""
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env manually
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY not found in .env")
    sys.exit(1)

print("Listing available Gemini models...")
print()

try:
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)

    # List all models
    models = client.models.list()

    print("Available models:")
    print("=" * 80)

    for model in models:
        print(f"Model: {model.name}")
        if hasattr(model, 'display_name'):
            print(f"  Display Name: {model.display_name}")
        if hasattr(model, 'description'):
            print(f"  Description: {model.description[:100] if model.description else 'N/A'}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"  Methods: {model.supported_generation_methods}")
        print()

except Exception as e:
    print(f"[ERROR] Failed to list models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
