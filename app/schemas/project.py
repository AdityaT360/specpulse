from datetime import datetime

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    base_url: AnyUrl | None = None


class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None
    base_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
