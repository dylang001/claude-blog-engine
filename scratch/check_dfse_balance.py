import urllib.request
import json
import base64

def check_balance():
    url = "https://api.dataforseo.com/v3/appendix/user_data"
    # Basic Auth
    auth_str = "contact@meetlyra.app:d4098608ce95cfab"
    auth_bytes = auth_str.encode('ascii')
    base64_bytes = base64.b64encode(auth_bytes)
    base64_str = base64_bytes.decode('ascii')
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {base64_str}")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            data = json.loads(res_body)
            tasks = data.get("tasks", [])
            if tasks:
                res_obj = tasks[0].get("result", [{}])[0]
                # Write full response to scratch file
                with open("scratch/dfse_balance_response.json", "w") as f:
                    json.dump(res_obj, f, indent=2)
                print("Login:", res_obj.get("login"))
                money = res_obj.get("money") or {}
                print("Money Keys:", list(money.keys()))
                if isinstance(money, dict):
                    # Check for fields like 'balance', 'spent', 'limit', 'value'
                    for k in ["balance", "spent", "limit", "value", "total"]:
                        if k in money:
                            print(f"Money - {k}:", money[k])
                        elif k in res_obj:
                            print(f"res_obj - {k}:", res_obj[k])
            else:
                print("No tasks returned")
    except Exception as e:
        print("Error checking balance:", e)

if __name__ == "__main__":
    check_balance()
