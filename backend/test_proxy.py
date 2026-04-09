"""Quick proxy connectivity test."""
import requests
import sys

PROXY_HTTP = "http://MuCyk1:zYp3yg6ETfaY@aag.mobileproxy.space:64029"
PROXY_SOCKS5 = "socks5h://MuCyk1:zYp3yg6ETfaY@aag.mobileproxy.space:64030"

TEST_URL = "https://httpbin.org/ip"
IG_URL = "https://i.instagram.com/api/v1/accounts/current_user/"


def test_proxy(label, proxy_url):
    print(f"\n{'='*50}")
    print(f"Testing: {label}")
    print(f"Proxy:   {proxy_url}")
    print(f"{'='*50}")

    # Test 1: basic connectivity via httpbin
    try:
        r = requests.get(
            TEST_URL,
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=15,
        )
        print(f"[OK] httpbin.org/ip → {r.status_code}: {r.text.strip()}")
    except Exception as e:
        print(f"[FAIL] httpbin.org/ip → {type(e).__name__}: {e}")

    # Test 2: can we reach Instagram?
    try:
        r = requests.get(
            IG_URL,
            proxies={"http": proxy_url, "https": proxy_url},
            headers={"User-Agent": "Instagram 269.0.0.18.75 Android"},
            timeout=15,
        )
        print(f"[OK] Instagram API → {r.status_code}")
    except Exception as e:
        print(f"[FAIL] Instagram API → {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Test without proxy first
    print("\n--- Direct (no proxy) ---")
    try:
        r = requests.get(TEST_URL, timeout=10)
        print(f"Your IP: {r.text.strip()}")
    except Exception as e:
        print(f"Direct failed: {e}")

    test_proxy("HTTP proxy", PROXY_HTTP)
    test_proxy("SOCKS5h proxy", PROXY_SOCKS5)
