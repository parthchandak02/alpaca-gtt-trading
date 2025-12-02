import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def check_health():
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        elapsed = time.time() - start
        print(f"Health Check: {response.status_code} in {elapsed:.2f}s")
        if response.status_code == 200:
            return True
        return False
    except Exception as e:
        print(f"Health Check Failed: {e}")
        return False

def check_account():
    try:
        start = time.time()
        # Assuming no auth needed for basic check or handled elsewhere? 
        # Wait, the backend might require auth. 
        # Let's check if the endpoints are protected.
        # Based on main.py, auth router is included.
        # But let's try to hit an endpoint that might be protected to see if we get 401 vs Timeout.
        response = requests.get(f"{BASE_URL}/api/account", timeout=30)
        elapsed = time.time() - start
        print(f"Account Check: {response.status_code} in {elapsed:.2f}s")
        return True
    except Exception as e:
        print(f"Account Check Failed: {e}")
        return False

if __name__ == "__main__":
    print("Checking Backend Health...")
    if check_health():
        print("Backend is UP.")
        # check_account() # This might fail if auth is needed, but good to test responsiveness
    else:
        print("Backend is DOWN or Slow.")
        sys.exit(1)

