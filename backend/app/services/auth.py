from dataclasses import dataclass

import httpx

from app.core.config import Settings


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None


async def authenticate(access_token: str, settings: Settings) -> AuthenticatedUser:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise AuthError("서버의 로그인 설정이 완료되지 않았습니다.", 503)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_anon_key.get_secret_value(),
                    "Authorization": f"Bearer {access_token}",
                },
            )
    except httpx.RequestError:
        raise AuthError("로그인 정보를 확인하지 못했습니다.", 503) from None

    if response.status_code in (401, 403):
        raise AuthError("로그인이 만료되었습니다. 다시 로그인해 주세요.")
    if response.is_error:
        raise AuthError("로그인 정보를 확인하지 못했습니다.", 503)

    try:
        body = response.json()
        user_id = body["id"]
    except (ValueError, KeyError, TypeError):
        raise AuthError("로그인 정보를 확인하지 못했습니다.", 503) from None
    return AuthenticatedUser(id=user_id, email=body.get("email"))
