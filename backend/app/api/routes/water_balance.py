from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.routes.chat import require_user
from app.schemas.water_balance import (
    WaterBalanceEvaluationRequest,
    WaterBalanceRequest,
    WaterBalanceResponse,
)
from app.services.auth import AuthenticatedUser
from app.services.water_balance import (
    calculate_measurement_window,
    calculate_water_balance,
)

router = APIRouter(tags=["water-balance"])


@router.post("/water-balance", response_model=WaterBalanceResponse)
async def water_balance(
    request: WaterBalanceRequest,
    _user: Annotated[AuthenticatedUser, Depends(require_user)],
) -> WaterBalanceResponse:
    return calculate_water_balance(request)


@router.post("/water-balance/evaluate", response_model=WaterBalanceResponse)
async def evaluate_water_balance(
    request: WaterBalanceEvaluationRequest,
    _user: Annotated[AuthenticatedUser, Depends(require_user)],
) -> WaterBalanceResponse:
    return calculate_measurement_window(request)
