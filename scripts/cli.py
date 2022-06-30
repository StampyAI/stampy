import requests

STAMPY_PORT = 2300
KEY = "$bF*-6KJ2-K6aR-KB%F"

try:
    while True:
        data = input("> ")
        r = requests.post("http://127.0.0.1:2300", data={"content": data, "key": KEY})
        print(f"\n{r.text}")
except KeyboardInterrupt:
    print("\nGoodbye!")
except Exception:
    print("Error: Is stampy on?")
