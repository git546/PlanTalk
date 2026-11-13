from pydantic import BaseModel, Field


class SpeciesTaxonomy(BaseModel):
    scientific_name: str | None = None
    canonical_name: str | None = None
    family: str | None = None
    genus: str | None = None
    rank: str | None = None
    status: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)


class SpeciesCareReference(BaseModel):
    query: str
    normalized_query: str
    common_name: str | None = None
    scientific_names: list[str] = Field(default_factory=list)
    watering: str | None = None
    sunlight: list[str] = Field(default_factory=list)
    care_level: str | None = None
    indoor: bool | None = None
    cycle: str | None = None
    taxonomy: SpeciesTaxonomy | None = None
    sources: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SpeciesReferenceResponse(BaseModel):
    reference: SpeciesCareReference
    usage: str = (
        "종별 일반 참고값입니다. 실제 급수 판단은 화분 무게, 센서, 배수량과 "
        "개별 식물의 관찰·보정값을 우선합니다."
    )
