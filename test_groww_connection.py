import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROWW_API_KEY", "")
api_secret = os.getenv("GROWW_API_SECRET", "")
vendor_key = os.getenv("GROWW_VENDOR_KEY", "")

print("=" * 65)
print(" GROWW API CREDENTIALS DIAGNOSTIC TEST")
print("=" * 65)
print(f"API Key (Length: {len(api_key)}): {api_key[:25]}...{api_key[-15:] if len(api_key) > 40 else ''}")
print(f"API Secret: {api_secret}")
print(f"Vendor Key: {vendor_key}")
print("-" * 65)

# Test 1: Direct Bearer Token with growwapi
print("\n[TEST 1] Testing Bearer Token with growwapi SDK...")
try:
    from growwapi import GrowwAPI
    g = GrowwAPI(api_key)
    try:
        prof = g.get_user_profile()
        print(" -> User Profile SUCCESS:", prof)
    except Exception as e:
        print(" -> User Profile Error:", e)

    try:
        margin = g.get_available_margin_details()
        print(" -> Margin Details SUCCESS:", margin)
    except Exception as e:
        print(" -> Margin Details Error:", e)
except Exception as e:
    print(" -> growwapi Import/Init Error:", e)

# Test 2: Direct REST request with Bearer header
print("\n[TEST 2] Testing Direct REST API Calls to api.groww.in...")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json",
    "X-API-VERSION": "1.0"
}
endpoints = [
    "https://api.groww.in/v1/user/profile",
    "https://api.groww.in/v1/margins/user",
    "https://api.groww.in/v1/holdings/user",
    "https://api.groww.in/v1/positions/user",
]
for ep in endpoints:
    try:
        r = requests.get(ep, headers=headers, timeout=10)
        print(f" -> GET {ep}: Status {r.status_code} | Body: {r.text[:120]}")
    except Exception as e:
        print(f" -> GET {ep}: Network Error: {e}")

# Test 3: API Key & Secret Exchange
print("\n[TEST 3] Testing get_access_token exchange...")
try:
    from growwapi import GrowwAPI
    for k_name, k_val in [("GROWW_API_KEY", api_key), ("GROWW_VENDOR_KEY", vendor_key)]:
        if not k_val:
            continue
        try:
            tok = GrowwAPI.get_access_token(api_key=k_val, secret=api_secret)
            print(f" -> get_access_token with {k_name}: SUCCESS! Token: {tok[:30]}...")
        except Exception as e:
            print(f" -> get_access_token with {k_name}: Failed -> {e}")
except Exception as e:
    print(" -> Test 3 Error:", e)

print("\n" + "=" * 65)
print(" DIAGNOSTIC COMPLETE")
print("=" * 65)
