#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test Gemini API connectivity and configuration."""
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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash").strip()

print("=" * 60)
print("GEMINI API CONFIGURATION TEST")
print("=" * 60)

# Check API key presence
if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY is not set in .env file")
    sys.exit(1)

print(f"[OK] GEMINI_API_KEY found: {GEMINI_API_KEY[:8]}...{GEMINI_API_KEY[-8:]}")
print(f"[OK] GEMINI_MODEL: {GEMINI_MODEL}")
print(f"[OK] API key length: {len(GEMINI_API_KEY)} characters")
print()
print("Testing API connection...")

try:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Try a simple test request
    config = types.GenerateContentConfig(
        system_instruction="You are a test assistant.",
        temperature=0.3,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents="Say 'API connection successful' in 3 words.",
        config=config
    )

    print("[OK] API connection successful!")
    print(f"[OK] Model '{GEMINI_MODEL}' is accessible")
    print(f"[OK] Response: {response.text}")
    print()
    print("=" * 60)
    print("[SUCCESS] ALL TESTS PASSED - Your Gemini configuration is working!")
    print("=" * 60)

except Exception as e:
    print(f"[ERROR] API connection failed!")
    print(f"   Error: {e}")
    print()

    if "401" in str(e) or "UNAUTHENTICATED" in str(e):
        print("DIAGNOSIS: Invalid API key")
        print("   Your API key is not recognized by Google.")
        print()
        print("SOLUTION:")
        print("   1. Go to: https://aistudio.google.com/apikey")
        print("   2. Create a new API key")
        print("   3. Update GEMINI_API_KEY in .env file")
        print("   4. Restart backend server")
    elif "404" in str(e):
        print(f"DIAGNOSIS: Model '{GEMINI_MODEL}' not found")
        print()
        print("SOLUTION:")
        print("   Try one of these models in .env:")
        print("   - gemini-1.5-flash (recommended)")
        print("   - gemini-1.5-flash-8b")
        print("   - gemini-1.5-pro")
        print("   - gemini-2.0-flash-exp")
    elif "403" in str(e) or "PERMISSION_DENIED" in str(e):
        print("DIAGNOSIS: API key lacks permissions")
        print("   The key might be restricted or disabled.")
        print()
        print("SOLUTION:")
        print("   1. Check API key restrictions at https://aistudio.google.com/apikey")
        print("   2. Ensure 'Generative Language API' is enabled")
        print("   3. Create a new unrestricted key if needed")
    else:
        print("DIAGNOSIS: Unknown error")
        print()
        print("Try:")
        print("   1. Verify internet connection")
        print("   2. Check if Google AI Studio is accessible")
        print("   3. Create a fresh API key")

    print()
    print("=" * 60)
    sys.exit(1)
