from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.routes.chat import require_user
from app.core.config import get_settings
from app.schemas.species_reference import SpeciesReferenceResponse
from app.services.auth import AuthenticatedUser
from app.services.species_reference import SpeciesReferenceError, fetch_plant_species_reference

router = APIRouter(tags=["species-reference"])


@router.get("/species-reference", response_model=SpeciesReferenceResponse)
async def species_reference(
    q: Annotated[str, Query(min_length=1, max_length=120)],
    _user: Annotated[AuthenticatedUser, Depends(require_user)],
    plant_id: str | None = None,
    refresh: bool = False,
    authorization: Annotated[str | None, Header()] = None,
) -> SpeciesReferenceResponse:
    access_token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    try:
        reference = await fetch_plant_species_reference(
            q,
            get_settings(),
            plant_id=plant_id,
            access_token=access_token,
            force_refresh=refresh,
        )
    except SpeciesReferenceError as exc:
        raise HTTPException(404, str(exc)) from None
    return SpeciesReferenceResponse(reference=reference)
