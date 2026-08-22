import re

_MIN_PASSWORD_LENGTH = 8
_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$")


def validate_password_strength(value: str) -> str:
    if len(value) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"Şifre en az {_MIN_PASSWORD_LENGTH} karakter olmalıdır.")
    if not _PASSWORD_PATTERN.match(value):
        raise ValueError("Şifre en az bir büyük harf, bir küçük harf ve bir rakam içermelidir.")
    return value
