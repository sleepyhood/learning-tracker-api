"""
services/ai_prompt_service.py

AI 프롬프트 생성 서비스 계층.

담당 기능:
  - 학생의 최근 숙제 이력을 기반으로 학부모 문자 초안 프롬프트 생성
"""

from core.storage import _load_workspace_students
from services.problem_catalog_service import load_problem_custom_metadata
from utils.utils_user_doc import load_doc_by_any


def generate_ai_prompt(display_id: str) -> str:
    """
    학생 display_id를 기반으로 학부모 문자 AI 프롬프트를 생성합니다.

    Args:
        display_id: 학생 고유 display_id

    Returns:
        생성된 프롬프트 문자열

    Raises:
        KeyError: 학생을 찾을 수 없을 때
    """
    workspace_data = _load_workspace_students()
    student = workspace_data.get(display_id)
    if not student:
        raise KeyError("Student not found")

    u = student.get("user_uuid") or display_id
    doc = load_doc_by_any(u)
    name = student.get("name", display_id)

    custom_meta = load_problem_custom_metadata()

    logs = doc.get("homework_logs", [])
    recent_hw = logs[-1] if logs else {}
    hw_list = recent_hw.get("problems", [])

    hw_details = []
    for p in hw_list:
        code = p.get("legacy_code") or ""
        title = p.get("title") or ""
        c_entry = custom_meta.get(code, {})
        l_goal = c_entry.get("learning_goal") or p.get("learning_goal") or ""
        goal_str = f" (학습목표: {l_goal})" if l_goal else ""
        hw_details.append(f"- [{code}] {title}{goal_str}")

    hw_text = "\n".join(hw_details) if hw_details else "지정된 숙제 없음"

    prompt = f"""다음은 {name} 학생의 오늘 학습 내용 및 부여된 숙제입니다. 학부모님께 보낼 수업 피드백 문자를 친절하고 전문적인 어조로 작성해주세요.

[학생 이름] {name}
[오늘 부여된 숙제 및 학습목표]
{hw_text}

[작성 가이드라인]
- 학생이 오늘 배운 핵심 학습목표와 문제해결 과정을 자연스럽게 칭찬하고 격려하는 멘트를 포함해주세요.
- 수업 중 겪은 어려움이나 실수를 언급할 때는 단순한 '오답'이라는 단정적 표현 대신 '오류를 수정하고 해결한 디버깅 과정'으로 전문성 있고 긍정적으로 프레이밍해주세요.
- 학부모님이 직관적으로 이해하기 쉽도록 2~3문장으로 간결하고 명확하게 작성해주세요.
"""
    return prompt
