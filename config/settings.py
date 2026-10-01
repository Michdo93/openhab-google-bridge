import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # openHAB
    OPENHAB_URL: str = os.getenv("OPENHAB_URL", "http://192.168.0.5:8080")
    OPENHAB_TOKEN: str = os.getenv("OPENHAB_TOKEN", "")
    OPENHAB_USER: str = os.getenv("OPENHAB_USER", "openHABAdmin")
    OPENHAB_PASS: str = os.getenv("OPENHAB_PASS", "hJem2jz6")

    # Sicherheit
    BRIDGE_SECRET_KEY: str = os.getenv("BRIDGE_SECRET_KEY", "MeinGeheimerSchluessel123")

    # Timeouts & Intervalle
    SSE_TIMEOUT_SECONDS: int = int(os.getenv("SSE_TIMEOUT_SECONDS", "15"))
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    CALENDAR_POLL_INTERVAL_SECONDS: int = int(
        os.getenv("CALENDAR_POLL_INTERVAL_SECONDS", "120")
    )

    # Google OAuth2 – Pfade
    CREDENTIALS_FILE: str = os.getenv("CREDENTIALS_FILE", "credentials.json")
    TOKEN_FILE: str = os.getenv("TOKEN_FILE", "google_token.json")

    # Google API Scopes
    GOOGLE_SCOPES: list = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar",
    ]


settings = Settings()
