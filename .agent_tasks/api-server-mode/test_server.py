#!/usr/bin/env python3
"""Test if the Henchman-AI API server can start."""

import subprocess
import time

import requests


def test_server_start():
    """Test that the server can start and respond to basic requests."""

    print("Testing Henchman-AI API server startup...")

    # Start server in background
    print("Starting server on port 8001...")
    server_process = subprocess.Popen(
        ["henchman", "serve", "--port", "8001", "--host", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give server time to start
    print("Waiting for server to start...")
    time.sleep(3)

    try:
        # Test health endpoint
        print("\nTesting health endpoint...")
        response = requests.get("http://127.0.0.1:8001/health", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
            print("✓ Health endpoint works")
        else:
            print(f"✗ Health endpoint failed: {response.text}")

        # Test root endpoint
        print("\nTesting root endpoint...")
        response = requests.get("http://127.0.0.1:8001/", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
            print("✓ Root endpoint works")
        else:
            print(f"✗ Root endpoint failed: {response.text}")

        # Test OpenAPI docs
        print("\nTesting OpenAPI documentation...")
        response = requests.get("http://127.0.0.1:8001/docs", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✓ OpenAPI docs available")
        else:
            print(f"✗ OpenAPI docs failed: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server. It may have failed to start.")
        # Try to get server output
        stdout, stderr = server_process.communicate(timeout=2)
        print(f"\nServer stdout:\n{stdout}")
        print(f"\nServer stderr:\n{stderr}")
    except Exception as e:
        print(f"✗ Error during test: {e}")
    finally:
        # Kill server
        print("\nStopping server...")
        server_process.terminate()
        server_process.wait(timeout=5)
        print("Test complete.")


if __name__ == "__main__":
    test_server_start()
