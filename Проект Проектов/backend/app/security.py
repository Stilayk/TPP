from __future__ import annotations

try:
    from passlib.context import CryptContext
except Exception:  # pragma: no cover
    CryptContext = None  # type: ignore


def _pwd_context() -> "CryptContext":
    if CryptContext is None:
        raise RuntimeError("passlib is required for password hashing")
    return CryptContext(schemes=["bcrypt"], deprecated="auto")


pwd_context = _pwd_context()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)
