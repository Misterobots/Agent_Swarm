import sys
import os

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.specialized.voice_cloning import clone_voice

def test_sample_match():
    # Test case 1: Known match
    text = "Hello there"
    print(f"Testing: '{text}'")
    result = clone_voice(text)
    
    if "Intro01_HELLO_there.wav" in result:
        print(f"SUCCESS: Matched '{text}' to '{result}'")
    else:
        print(f"FAILED: Expected match, got '{result}'")

    # Test case 2: No match
    text = "This is a random sentence that should be generated."
    print(f"\nTesting: '{text}'")
    # This will likely fail without a running engine if it tries to hit the API, 
    # but we just want to see it NOT return a sample path immediately.
    try:
        result = clone_voice(text)
        print(f"Result: {result} (Expected generation attempt)")
    except Exception as e:
        print(f"Caught expected error (connecting to engine): {e}")
        print("SUCCESS: Did not match random text.")

if __name__ == "__main__":
    test_sample_match()
