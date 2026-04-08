"""
Bot Authentication — Simple user management with JWT tokens.
Admin adds users manually in the USERS dict below.
"""
import os
import hashlib
import hmac
import json
import time
import base64
from typing import Optional, Dict
from datetime import datetime, timezone

# ============================================
# USER MANAGEMENT — Admin adds users here
# ============================================
# Format: "username": "password"
# To add a new user, simply add a new entry below.
USERS = {
    "admin": "FundingArb2026!",
    "erwan": "PPE_Upgrade!",
}

# JWT secret — change this in production
JWT_SECRET = os.getenv("BOT_JWT_SECRET", "funding-arb-secret-key-change-me")
TOKEN_EXPIRY_SECONDS = 86400  # 24 hours


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash for password verification."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_user(username: str, password: str) -> bool:
    """Check if username/password match."""
    stored = USERS.get(username)
    if stored is None:
        return False
    return stored == password


def create_token(username: str) -> str:
    """Create a simple JWT-like token (base64 encoded JSON with HMAC signature)."""
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[str]:
    """Verify token and return username if valid, None otherwise."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts

        # Verify signature
        expected_sig = hmac.new(JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Decode payload
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload.get("sub")
    except Exception:
        return None


# ============================================
# CREDENTIALS STORAGE
# ============================================
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "bot_credentials.json")


def save_credentials(username: str, credentials: Dict) -> bool:
    """Save API keys and wallet addresses for a user."""
    try:
        all_creds = {}
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, "r") as f:
                all_creds = json.load(f)

        all_creds[username] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **credentials
        }

        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(all_creds, f, indent=2)

        return True
    except Exception:
        return False


def get_credentials(username: str) -> Optional[Dict]:
    """Retrieve stored credentials for a user (keys are masked)."""
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return None
        with open(CREDENTIALS_FILE, "r") as f:
            all_creds = json.load(f)
        creds = all_creds.get(username)
        if creds is None:
            return None

        # Mask sensitive values
        masked = {}
        for key, value in creds.items():
            if key == "updated_at":
                masked[key] = value
            elif isinstance(value, str) and len(value) > 6:
                masked[key] = value[:4] + "***" + value[-3:]
            else:
                masked[key] = "***"
        return masked
    except Exception:
        return None


def get_raw_credentials(username: str) -> Optional[Dict]:
    """Retrieve raw (unmasked) credentials — for bot execution only."""
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return None
        with open(CREDENTIALS_FILE, "r") as f:
            all_creds = json.load(f)
        return all_creds.get(username)
    except Exception:
        return None
