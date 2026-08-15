from typing import Annotated
from pydantic import AfterValidator
import re

def validate_email_format(email: str) -> str:
    email = email.strip().lower()
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        raise ValueError("value is not a valid email address: The email address is not valid.")
    return email

SafeEmail = Annotated[str, AfterValidator(validate_email_format)]
