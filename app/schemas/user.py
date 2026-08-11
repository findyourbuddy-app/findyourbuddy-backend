from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    is_active: bool
    age: int | None = None
    bio: str | None = None
    interests: list[str] = []
    latitude: float | None = None
    longitude: float | None = None
    photo_url: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    age: int | None = None
    bio: str | None = None
    interests: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None
