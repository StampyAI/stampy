import requests
import json

STAMPY_PORT = 2300
KEY = "$bF*-6KJ2-K6aR-KB%F"

try:
    modules = []
    json_mode = False
    while True:
        data = input("> ")
        if data == ":help":
            print(":list_modules")
            print(":select_modules")
            print(":toggle_json")
            print(":help")
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
        if data == ":toggle_json":
            json_mode = not json_mode
            print(f"JSON Mode: {json_mode}")
            continue

        # Send Message
        message = {"content": data, "key": KEY, "modules": json.dumps(modules)}
        if json_mode:
            headers = {"Content-type": "application/json", "Accept": "text/plain"}
            r = requests.post("http://127.0.0.1:2300", data=json.dumps(message), headers=headers)
        r = requests.post("http://127.0.0.1:2300", data=message)
        print(f"{r.text}")
except KeyboardInterrupt:
    print("\nGoodbye!")
except Exception:
    print("Error: Is stampy on?")
