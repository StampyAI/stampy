import requests
import json

STAMPY_PORT = 2300
KEY = "$bF*-6KJ2-K6aR-KB%F"

try:
    modules = []
    while True:
        data = input("> ")
        if data == ":list_modules":
            r = requests.get("http://127.0.0.1:2300/list_modules")
            print(f"{r.text}")
            continue
        if data == ":select_modules":
            print("Please  enter a JSON list of modules:")
            try:
                modules = json.loads(input("> "))
            except json.decoder.JSONDecodeError:
                print("Invalid JSON!")
            print(f"Selected: {modules}")
            continue
        r = requests.post(
            "http://127.0.0.1:2300", data={"content": data, "key": KEY, "modules": json.dumps(modules)}
        )
        print(f"{r.text}")
except KeyboardInterrupt:
    print("\nGoodbye!")
except Exception:
    print("Error: Is stampy on?")
