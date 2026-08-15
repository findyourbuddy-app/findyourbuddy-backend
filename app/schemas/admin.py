from pydantic import BaseModel


class UserActiveStatusUpdate(BaseModel):
    is_active: bool
