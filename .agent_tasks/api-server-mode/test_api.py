#!/usr/bin/env python3
"""Test script for Henchman-AI API server."""

import asyncio
import json
import sys
from typing import Any

import httpx


async def test_api() -> None:
    """Test the API server endpoints."""
    
    # Base URL for the API
    base_url = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Testing Henchman-AI API server...")
        
        # Test 1: Health endpoint
        print("\n1. Testing health endpoint...")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                print("   ✓ Health endpoint works")
            else:
                print(f"   ✗ Health endpoint failed: {response.text}")
        except Exception as e:
            print(f"   ✗ Health endpoint error: {e}")
        
        # Test 2: Root endpoint
        print("\n2. Testing root endpoint...")
        try:
            response = await client.get(f"{base_url}/")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                print("   ✓ Root endpoint works")
            else:
                print(f"   ✗ Root endpoint failed: {response.text}")
        except Exception as e:
            print(f"   ✗ Root endpoint error: {e}")
        
        # Test 3: OpenAPI docs
        print("\n3. Testing OpenAPI documentation...")
        try:
            response = await client.get(f"{base_url}/docs")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ OpenAPI docs available")
            else:
                print(f"   ✗ OpenAPI docs failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ OpenAPI docs error: {e}")
        
        # Test 4: Chat completion endpoint (without auth)
        print("\n4. Testing chat completion endpoint (without auth)...")
        try:
            payload = {
                "messages": [
                    {"role": "user", "content": "Hello, world!"}
                ],
                "stream": False
            }
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"   Status: {response.status_code}")
            if response.status_code in [200, 401, 403]:
                # Either success or auth error (expected if auth is enabled)
                print(f"   Response status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                    print("   ✓ Chat completion works")
                else:
                    print(f"   Note: Auth required (expected): {response.text}")
            else:
                print(f"   ✗ Chat completion failed: {response.text}")
        except Exception as e:
            print(f"   ✗ Chat completion error: {e}")
        
        print("\n" + "="*50)
        print("API test completed!")
        print("="*50)


if __name__ == "__main__":
    # Check if server is running
    print("Note: Make sure the API server is running before executing this test.")
    print("Start the server with: henchman serve")
    print()
    
    response = input("Is the server running? (y/n): ")
    if response.lower() != 'y':
        print("Please start the server first with: henchman serve")
        sys.exit(1)
    
    # Run tests
    asyncio.run(test_api())