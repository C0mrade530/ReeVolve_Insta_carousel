"""Test Instagram upload directly with proxy + session."""
import json
import logging
import traceback
from pathlib import Path
from instagrapi import Client

logging.basicConfig(level=logging.DEBUG)

PROXY = "socks5h://MuCyk1:zYp3yg6ETfaY@aag.mobileproxy.space:64030"

# Load session from the app's encryption
from app.config import get_settings
from app.utils.encryption import decrypt_data
from supabase import create_client

settings = get_settings()
db = create_client(settings.supabase_url, settings.supabase_service_role_key)

# Get latest account
accounts = db.table("instagram_accounts").select("*").order("created_at", desc=True).limit(1).execute()
if not accounts.data:
    print("No accounts found!")
    exit(1)

account = accounts.data[0]
print(f"Account: @{account['username']}, id={account['id']}")

# Decrypt session
session_settings = decrypt_data(account["session_data"])
print(f"Session keys: {list(session_settings.keys())[:5]}")

# Create client with modern device + proxy
cl = Client()
cl.set_device({
    "app_version": "357.0.0.25.101",
    "android_version": 34,
    "android_release": "14",
    "dpi": "420dpi",
    "resolution": "1080x2400",
    "manufacturer": "Google",
    "device": "shiba",
    "model": "Pixel 8",
    "cpu": "qcom",
    "version_code": "604247854",
})
cl.set_user_agent(
    "Instagram 357.0.0.25.101 Android "
    "(34/14; 420dpi; 1080x2400; Google/google; Pixel 8; shiba; qcom; en_US; 604247854)"
)
cl.set_proxy(PROXY)
cl.set_settings(session_settings)
# Re-apply proxy + device after set_settings
cl.set_proxy(PROXY)
cl.set_device({
    "app_version": "357.0.0.25.101",
    "android_version": 34,
    "android_release": "14",
    "dpi": "420dpi",
    "resolution": "1080x2400",
    "manufacturer": "Google",
    "device": "shiba",
    "model": "Pixel 8",
    "cpu": "qcom",
    "version_code": "604247854",
})
cl.set_user_agent(
    "Instagram 357.0.0.25.101 Android "
    "(34/14; 420dpi; 1080x2400; Google/google; Pixel 8; shiba; qcom; en_US; 604247854)"
)

print(f"user_id: {cl.user_id}")
print(f"proxies: {cl.private.proxies}")

# Test 1: Try account_info
print("\n--- Test 1: account_info ---")
try:
    info = cl.account_info()
    print(f"OK! username={info.username}, pk={info.pk}")
except Exception as e:
    print(f"FAIL: {e}")
    traceback.print_exc()

# Convert PNG to JPEG (instagrapi only supports .jpg/.jpeg/.webp for albums!)
from PIL import Image as PILImage

def png_to_jpg(png_path: Path) -> Path:
    """Convert PNG to JPEG for instagrapi compatibility."""
    if png_path.suffix.lower() != ".png":
        return png_path
    jpg_path = png_path.with_suffix(".jpg")
    if not jpg_path.exists():
        img = PILImage.open(png_path)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img.save(jpg_path, "JPEG", quality=95)
        print(f"  Converted: {png_path.name} → {jpg_path.name}")
    return jpg_path

# Test 2: Try single photo upload (convert PNG→JPG first)
print("\n--- Test 2: single photo upload ---")
test_image = Path("/Users/mak/realtor_saas/backend/media/carousels/0c9a13e2-af59-4e04-b7d8-25d96e43fbac/slide_1.png")
if test_image.exists():
    test_jpg = png_to_jpg(test_image)
    try:
        media = cl.photo_upload(test_jpg, "Test upload - delete me")
        print(f"OK! media_pk={media.pk}, code={media.code}")
        # Delete the test post
        try:
            cl.media_delete(media.pk)
            print("Deleted test post")
        except:
            print("Could not delete test post - delete manually!")
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc()
        print(f"\nlast_json: {cl.last_json}")
        print(f"last_response status: {getattr(cl, 'last_response', {})}")
else:
    print(f"Image not found: {test_image}")

# Test 3: Try album upload (2 slides, convert PNG→JPG)
print("\n--- Test 3: album upload (2 slides) ---")
slide1 = png_to_jpg(Path("/Users/mak/realtor_saas/backend/media/carousels/0c9a13e2-af59-4e04-b7d8-25d96e43fbac/slide_1.png"))
slide2 = png_to_jpg(Path("/Users/mak/realtor_saas/backend/media/carousels/0c9a13e2-af59-4e04-b7d8-25d96e43fbac/slide_2.png"))
if slide1.exists() and slide2.exists():
    try:
        media = cl.album_upload([slide1, slide2], "Test album - delete me")
        print(f"OK! media_pk={media.pk}, code={media.code}")
        try:
            cl.media_delete(media.pk)
            print("Deleted test album")
        except:
            print("Could not delete test album - delete manually!")
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc()
        print(f"\nlast_json: {cl.last_json}")
else:
    print(f"Slides not found")
