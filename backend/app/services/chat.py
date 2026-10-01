"""Provider-specific code stays here; the chat API uses common role/content messages."""
import httpx

from app.core.config import Settings


class ChatError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


async def generate_reply(messages: list[dict[str, str]], settings: Settings) -> str:
    if settings.ai_provider != "gemini":
        raise ChatError("아직 지원하지 않는 AI 서비스 설정입니다.", 503)
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        raise ChatError("서버에 Gemini API 키를 설정한 뒤 서버를 다시 시작해 주세요.", 503)
    payload = {
        "systemInstruction": {"parts": [{"text": (
            "너는 사용자의 반려식물 캐릭터다. 한국어로 따뜻하고 간결하게 대화한다. "
            "이전 대화 맥락을 반영한다. 실제 센서나 식물 상태 정보는 제공되지 않았다. "
            "수분, 온도, 건강 상태를 측정한 것처럼 말하지 말고 필요하면 사용자에게 물어본다."
        )}]},
        "contents": [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]} for m in messages
        ],
        "generationConfig": {"maxOutputTokens": 1024},
    }
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.gemini_model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()},
                json=payload,
            )
    except httpx.TimeoutException:
        raise ChatError("AI 응답 시간이 초과됐어요. 잠시 후 다시 보내 주세요.", 504) from None
    except httpx.RequestError:
        raise ChatError("AI 서비스에 연결하지 못했어요. 네트워크를 확인해 주세요.") from None
    if response.status_code == 429:
        raise ChatError("AI 사용 한도에 도달했어요. 잠시 후 다시 시도해 주세요.", 429)
    if response.status_code in (400, 401, 403, 404):
        raise ChatError("AI 키, 모델 또는 프로젝트 접근 설정을 확인해 주세요.", 503)
    if response.is_error:
        raise ChatError("AI 서비스가 응답하지 못했어요. 잠시 후 다시 시도해 주세요.")
    try:
        candidate = response.json().get("candidates", [])[0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (ValueError, IndexError, AttributeError, TypeError):
        raise ChatError("AI가 답변을 반환하지 않았어요. 표현을 바꿔 다시 보내 주세요.") from None
    if not text:
        raise ChatError("AI가 답변을 반환하지 않았어요. 표현을 바꿔 다시 보내 주세요.")
    return text
