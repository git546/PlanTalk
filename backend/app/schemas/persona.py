from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
MemoryText = Annotated[str, Field(min_length=1, max_length=500)]


class PersonalityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: ShortText | None = None
    energy: int | None = Field(default=None, ge=1, le=5)
    affection: int | None = Field(default=None, ge=1, le=5)
    humor: int | None = Field(default=None, ge=1, le=5)
    talk_length: Literal["짧게", "보통", "길게"] | None = None
    traits: list[ShortText] = Field(default_factory=list, max_length=8)
    habits: list[ShortText] = Field(default_factory=list, max_length=8)
    favorite_topics: list[ShortText] = Field(default_factory=list, max_length=8)
    calling_user: ShortText | None = None


class PlantContext(BaseModel):
    """Plant data used to compose a prompt; later this comes from Supabase."""

    model_config = ConfigDict(extra="forbid")

    name: ShortText
    species: ShortText | None = None
    personality: PersonalityProfile = Field(default_factory=PersonalityProfile)
    memories: list[MemoryText] = Field(default_factory=list, max_length=20)
