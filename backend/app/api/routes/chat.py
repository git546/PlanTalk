from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.services.chat import ChatError, generate_reply
from app.services.plant_data import SCENARIOS

router = APIRouter(tags=["chat"])


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value.strip()


class ChatRequest(BaseModel):
    scenario: Literal["normal", "dry", "stale", "error"] = "normal"
    messages: list[Message] = Field(min_length=1, max_length=21)


class ChatResponse(BaseModel):
    reply: str


@router.get("/plant/scenarios")
def scenarios():
    return list(SCENARIOS.values())


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    roles = [m.role for m in request.messages]
    if any(role != ("user" if i % 2 == 0 else "assistant") for i, role in enumerate(roles)):
        raise HTTPException(422, "대화 순서가 올바르지 않습니다.")
    if roles[-1] != "user":
        raise HTTPException(422, "마지막 메시지는 사용자 메시지여야 합니다.")
    try:
        reply = await generate_reply(
            [m.model_dump() for m in request.messages], get_settings(), SCENARIOS[request.scenario]
        )
    except ChatError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    return ChatResponse(reply=reply)
