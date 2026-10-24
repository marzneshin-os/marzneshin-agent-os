"""Path-only checks for files that automation must not inspect."""
from pathlib import Path

_PRIVATE_KEY_NAMES = {"id_dsa", "id_ecdsa", "id_ed25519", "id_rsa"}
_PRIVATE_KEY_SUFFIXES = {".der", ".jks", ".key", ".p12", ".p8", ".pem", ".pfx"}
_CREDENTIAL_NAMES = {".netrc", ".npmrc", ".pypirc", "credentials", "credential"}


def is_sensitive_path(path):
    normalized = str(path).replace("\\", "/")
    parts = [part.casefold() for part in normalized.split("/") if part]
    env_example = bool(parts) and parts[-1] == ".env.example"
    for part in parts:
        if part == ".env" or (part.startswith(".env.") and not (part == ".env.example" and env_example)):
            return True
        if part in _PRIVATE_KEY_NAMES or part in _CREDENTIAL_NAMES:
            return True
        if part in {".aws", ".azure", ".gnupg", ".ssh"}:
            return True
        if "credential" in part or "secret" in part or "token" in part:
            return True
        if "private" in part and ("key" in part or part == "private"):
            return True
        if Path(part).suffix in _PRIVATE_KEY_SUFFIXES:
            return True
    return False
