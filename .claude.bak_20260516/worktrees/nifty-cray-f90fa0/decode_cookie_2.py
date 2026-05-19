
cookie_hex = "235a575a6a61484a36626d6871646e5232613255232a5957567a4c574e6d59672a53306d787836784cd25837f56f304bbf4dca64f059a30b499b893ec0148169484b7998624c453cdd53431a16749b3379aa0adeb7ff616bd69f"
try:
    decoded = bytes.fromhex(cookie_hex)
    print(f"Decoded Bytes: {decoded}")
    # Try decoding as text if possible, though likely encrypted
    print(f"Decoded String: {decoded.decode('utf-8', errors='replace')}")
except Exception as e:
    print(f"Error: {e}")
