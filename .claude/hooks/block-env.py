import json
import sys

try:
    payload = json.load(sys.stdin)
    file_path = payload.get("file_path", "")
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

if file_path.endswith(".env"):
    print("Blocked: .env contains real credentials — edit it manually if needed")
    sys.exit(2)

sys.exit(0)
