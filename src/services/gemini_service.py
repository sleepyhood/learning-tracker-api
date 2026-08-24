"""
services/gemini_service.py

Google Gemini REST API 직접 호출 서비스.

담당 기능:
  - 조립된 프롬프트 텍스트를 Gemini Flash 모델에 전달하여 완성된 피드백 문자를 반환.
  - 다중 모델 Fallback: gemini-3.6-flash → gemini-2.0-flash → gemini-1.5-flash
  - GEMINI_API_KEY 미설정 시 GeminiConfigError 예외를 발생시켜 호출부에서 처리.
"""

import os
import re

import requests

# ── 시도할 모델 목록 (우선순위 순) ─────────────────────────────
_MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

_API_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

_MAX_OUTPUT_TOKENS = 2048


class GeminiConfigError(Exception):
    """GEMINI_API_KEY 환경변수가 없을 때 발생."""
    pass


class GeminiAPIError(Exception):
    """Gemini API 호출 자체가 실패했을 때 발생 (네트워크 오류, 모든 모델 소진 등)."""
    pass


def _strip_leading_junk(text: str) -> str:
    """응답 첫 줄에 붙는 마크다운 인용 부호(```, ###, ---) 제거."""
    return re.sub(r"^[\s`#\-\*]+", "", text).strip()


def generate_feedback(prompt: str) -> str:
    """
    Gemini API를 호출하여 학부모 알림장 피드백 텍스트를 생성합니다.

    Args:
        prompt: 프론트엔드에서 조립한 완전한 프롬프트 문자열.

    Returns:
        Gemini가 생성한 피드백 텍스트 (선두 특수문자 정제 완료).

    Raises:
        GeminiConfigError: GEMINI_API_KEY 환경변수가 설정되지 않았을 때.
        GeminiAPIError: 모든 모델 시도가 실패했을 때.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다. "
            "src/.env 파일에 GEMINI_API_KEY=your_key_here 를 추가하세요."
        )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": _MAX_OUTPUT_TOKENS,
            "temperature": 0.7,
        },
    }

    last_error = None
    for model in _MODEL_CANDIDATES:
        url = _API_ENDPOINT.format(model=model)
        try:
            resp = requests.post(
                url,
                json=payload,
                params={"key": api_key},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates") or []
                if candidates:
                    raw_text = (
                        candidates[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    return _strip_leading_junk(raw_text)
                # 응답 자체는 200이나 content가 비어 있는 경우
                last_error = f"모델 {model}: 응답에 content가 없습니다."
            elif resp.status_code in (404, 400):
                # 이 모델을 지원하지 않음 → 다음 모델로 Fallback
                last_error = f"모델 {model}: {resp.status_code} – {resp.text[:120]}"
                continue
            else:
                last_error = f"모델 {model}: HTTP {resp.status_code} – {resp.text[:200]}"
                # 5xx 서버 오류도 다음 모델로 시도
        except requests.exceptions.Timeout:
            last_error = f"모델 {model}: 요청 타임아웃(30s)"
        except requests.exceptions.RequestException as exc:
            last_error = f"모델 {model}: 네트워크 오류 – {exc}"

    raise GeminiAPIError(
        f"모든 Gemini 모델 시도 실패. 마지막 오류: {last_error}"
    )
