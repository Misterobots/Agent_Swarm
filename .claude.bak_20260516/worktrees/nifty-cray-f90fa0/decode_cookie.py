
cookie_hex = "2359325a6a5a47397664545a6e61486c69613259232a5957567a4c574e6d59672a524c725962717676b29e05adf959ff72434d1a8d645954e6916f9271c5e8ad48688a3ec5e72074e864df6d890261f55ed82d29641a254cbda2"
try:
    decoded = bytes.fromhex(cookie_hex)
    print(f"Decoded Bytes: {decoded}")
    print(f"Decoded String: {decoded.decode('utf-8', errors='replace')}")
except Exception as e:
    print(f"Error: {e}")
