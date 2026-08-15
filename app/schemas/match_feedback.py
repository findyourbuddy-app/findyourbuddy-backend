from pydantic import BaseModel


class MatchFeedbackCreate(BaseModel):
    met_in_person: bool | None = None
