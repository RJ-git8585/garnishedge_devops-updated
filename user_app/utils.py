import hashlib

class HashValue:
    """Utility class for hashing values."""

    @staticmethod
    def hash_value(value: str) -> str:
        """Return a SHA-256 hash for the given value."""
        if value:
            return hashlib.sha256(value.encode('utf-8')).hexdigest()
        return None
