from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.schemas.persona import PlantContext
from app.services.auth import AuthenticatedUser, AuthError, authenticate
from app.services.chat import ChatError, generate_reply
from app.services.conversation_memory import prepare_chat_context, remember_conversation

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
    messages: list[Message] = Field(min_length=1, max_length=21)
    plant: PlantContext | None = None


class ChatResponse(BaseModel):
    reply: str


async def require_user(authorization: Annotated[str | None, Header()] = None) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "로그인이 필요합니다.")
    try:
        return await authenticate(token, get_settings())
    except AuthError as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str | None, Header()] = None,
) -> ChatResponse:
    user = await require_user(authorization)
    access_token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    roles = [m.role for m in request.messages]
    if any(role != ("user" if i % 2 == 0 else "assistant") for i, role in enumerate(roles)):
        raise HTTPException(422, "대화 순서가 올바르지 않습니다.")
    if roles[-1] != "user":
        raise HTTPException(422, "마지막 메시지는 사용자 메시지여야 합니다.")
    settings = get_settings()
    plant, plant_id, stored_memories = await prepare_chat_context(
        user.id,
        access_token,
        request.plant,
        settings,
    )
    try:
        reply = await generate_reply(
            [m.model_dump() for m in request.messages],
            settings,
            plant=plant,
        )
    except ChatError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    if plant_id:
        background_tasks.add_task(
            remember_conversation,
            plant_id,
            request.messages[-1].content,
            reply,
            stored_memories,
            access_token,
            settings,
        )
    return ChatResponse(reply=reply)
