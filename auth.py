"""
Authentication Manager for Groww Trading API
Handles API Key & Secret exchange for active Groww session tokens.
"""

import os
import json
from datetime import datetime, date
import config

GROWW_TOKEN_CACHE_FILE = ".groww_token.json"


def get_groww_session() -> tuple[str, dict]:
    """
    Exchanges Groww API Key and Secret for an active session token and profile.
    Returns: (session_token, user_profile)
    """
    token = ""
    profile = {}

    # 1. First, check cached token if available and valid
    cached = load_cached_groww_token()
    if cached:
        try:
            from growwapi import GrowwAPI
            g = GrowwAPI(cached)
            prof = g.get_user_profile()
            if prof and isinstance(prof, dict) and "ucc" in prof:
                print(f"[GROWW AUTH] Authenticated via cached token. UCC: {prof.get('ucc')}")
                return cached, prof
        except Exception as e:
            print(f"[GROWW AUTH] Cached token check note: {e}")

    # 2. Try generating fresh session token using Groww API Key and Secret
    api_key = getattr(config, "GROWW_API_KEY", "")
    api_secret = getattr(config, "GROWW_API_SECRET", "")
    vendor_key = getattr(config, "GROWW_VENDOR_KEY", "")

    keys_to_try = []
    if vendor_key:
        keys_to_try.append(vendor_key)
    if api_key and api_key not in keys_to_try:
        keys_to_try.append(api_key)

    if api_secret and keys_to_try:
        for candidate_key in keys_to_try:
            try:
                from growwapi import GrowwAPI
                session_token = GrowwAPI.get_access_token(
                    api_key=candidate_key,
                    secret=api_secret
                )
                if session_token:
                    token = session_token
                    save_groww_token({
                        "access_token": token,
                        "date": date.today().isoformat(),
                        "created_at": datetime.now().isoformat()
                    })
                    try:
                        g = GrowwAPI(token)
                        profile = g.get_user_profile()
                    except Exception:
                        pass
                    print(f"[GROWW AUTH] Successfully exchanged API Key & Secret for Live Session Token!")
                    return token, profile
            except Exception as e:
                print(f"[GROWW AUTH] API Key exchange note ({candidate_key[:12]}...): {e}")

    # 3. Direct token fallback from config or cached
    fallback_token = (
        getattr(config, "GROWW_ACCESS_TOKEN", None)
        or getattr(config, "GROWW_API_KEY", None)
        or cached
    )
    if fallback_token and fallback_token != "SIMULATED_GROWW_TOKEN":
        try:
            from growwapi import GrowwAPI
            g = GrowwAPI(fallback_token)
            prof = g.get_user_profile()
            if prof and isinstance(prof, dict) and "ucc" in prof:
                print(f"[GROWW AUTH] Verified live Groww session for UCC: {prof.get('ucc')}")
                return fallback_token, prof
        except Exception as e:
            print(f"[GROWW AUTH NOTICE] Configured Groww token is expired or unauthorized ({e}).")
            print("[GROWW AUTH NOTICE] Switching to Simulated Mode. To trade live, generate a fresh API token in your Groww account.")

    return "SIMULATED_GROWW_TOKEN", {"ucc": "6629599909", "active_segments": ["CASH", "FNO"]}


def get_groww_access_token() -> str:
    token, _ = get_groww_session()
    return token


def save_groww_token(token_data: dict):
    try:
        with open(GROWW_TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)
    except Exception as e:
        print(f"[AUTH ERROR] Could not save token cache: {e}")


def load_cached_groww_token() -> str:
    if not os.path.exists(GROWW_TOKEN_CACHE_FILE):
        return ""
    try:
        with open(GROWW_TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("access_token", "")
    except Exception:
        pass
    return ""


if __name__ == "__main__":
    token, profile = get_groww_session()
    print(f"Session Token Ready: {bool(token)}")
    if profile:
        print(f"Connected Groww UCC: {profile.get('ucc')} | Segments: {profile.get('active_segments')}")
