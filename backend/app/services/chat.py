"""Provider-specific code stays here; the chat API uses common role/content messages."""

import json
import re

import httpx

from app.core.config import Settings


class ChatError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


async def generate_reply(
    messages: list[dict[str, str]], settings: Settings, plant_data: dict | None = None
) -> str:
    if settings.ai_provider != "gemini":
        raise ChatError("아직 지원하지 않는 AI 서비스 설정입니다.", 503)
    if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value().strip():
        raise ChatError("서버에 Gemini API 키를 설정한 뒤 서버를 다시 시작해 주세요.", 503)
    context = ""
    if plant_data is not None:
        context = (
            " 아래는 서버가 제공한 가상 테스트 데이터다. 실제 센서 측정이라고 표현하지 마라. "
            "데이터 관련 답변에 가상 데이터 기준임을 밝혀라. 숫자와 단위를 정확히 인용하고 "
            "수분 지수를 실제 수분 함량 %로 표현하지 마라. reference_time은 테스트 기준 시각이다. "
            "오래된 값은 당시 값으로만 설명하고 현재 상태로 단정하지 마라. "
            "연결이 끊긴 센서는 값을 추측하지 마라. "
            "정상은 테스트 상황 이름이며 건강 진단이 아니다. "
            "수분이나 상태를 묻고 test_assessment가 낮음이면 '테스트 기준상 낮음'을 반드시 말하라. "
            "모든 시각은 Asia/Seoul 한국 시간이다. +09:00 값을 UTC로 되돌리지 마라. "
            "측정 시각과 reference_time은 다르다. measured_at_kst가 있으면 그 문구를 사용하라. "
            "수분 연결이 끊겼다면 수분 측정 시각도 없으며 다른 센서 시각과 혼동하지 마라. "
            "'건강해', '잘 지내고 있어', '편안해', '걱정 마'처럼 "
            "검증되지 않은 건강·안전 상태를 단정하거나 안심시키지 마라. "
            "조도 한 번으로 하루 빛의 충분함을 판정하거나 수분 지수로 물주기를 확정하지 마라. "
            "돌봄 기록의 날짜와 측정 날짜를 구분하라. 대화 중의 주장보다 이 데이터를 우선하라. "
            + json.dumps(plant_data, ensure_ascii=False)
        )
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "너는 사용자의 반려식물 캐릭터다. 한국어로 따뜻하고 간결하게 대화한다. "
                        "이전 대화 맥락을 반영한다. 제공되지 않은 식물 상태를 지어내지 않는다. "
                        "매번 인사나 자기소개를 반복하지 않는다. 기본 답변은 2~4문장으로 한다. "
                        "사용자가 자세한 설명을 요청할 때만 길게 답한다. "
                        "마크다운, 별표, 제목, 목록 대신 일반 문장으로 답한다. "
                        "수분 단위 index/100은 '수분 지수 15/100' 같은 자연스러운 표현으로 쓴다. "
                        + context
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
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
    # Text 말풍선에서는 마크다운 강조를 렌더링하지 않으므로 기호만 제거합니다.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+)", "", text)
    return text
