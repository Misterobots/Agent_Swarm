import requests
import time

def check():
    url = "http://localhost:8020/tts"
    print(f"Checking {url}...")
    try:
        # Dummy data
        data = {"text": "Hello"}
        response = requests.post(url, data=data, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Mode Loaded! Audio generated.")
        elif response.status_code == 503:
            print("Model NOT Loaded (503).")
            print(response.text)
        else:
            print(f"Unexpected Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    check()
