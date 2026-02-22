# Chapter Workspace Plan Artifacts

## 1) 기능 유지 체크리스트 (/chapter, /group)
- [x] 챕터별 소챕터 목록 확인 가능
- [x] 소챕터별 진행률(완료/부분/오답/미해결) 확인 가능
- [x] 문제 본문 링크 이동 가능
- [x] 소챕터 전환 시 페이지 라우팅 없이 목록 교체 가능 (workspace)
- [x] 숙제 문제 다중 선택 가능
- [x] 선택 문제 복사 가능
- [x] 숙제 로그 저장 가능 (`POST /api/students/<uuid>/homework_logs`)
- [x] 기존 그룹 화면 deep-link 유지 (`/group/<id>?legacy=1`)

완료 기준:
- 페이지 이동 없이 숙제 지정 완료 (문제 선택 + 메시지 작성 + 저장)

## 2) chapter_workspace 데이터 계약 (초기 응답)

`GET /api/chapter_workspace?user=<username>&chapter=<chapter>[&group=<group_id>]`

```json
{
  "ok": true,
  "user": "string",
  "user_uuid": "uuid",
  "chapter": "string",
  "subchapters": [
    {
      "group_id": "string",
      "title": "string",
      "counts": {
        "total": 0,
        "solved": 0,
        "partial": 0,
        "wrong": 0,
        "unsolved": 0
      },
      "chapter_url": "string",
      "legacy_group_url": "string"
    }
  ],
  "selected_group": "string",
  "problems": [
    {
      "problem_id": "string",
      "legacy_code": "string",
      "title": "string",
      "status": "solved|partial|wrong|unsolved",
      "link": "string"
    }
  ],
  "status_map": {
    "<problem_id>": "solved|partial|wrong|unsolved"
  },
  "latest_homework": {}
}
```

소챕터 상세:
- `GET /api/chapter_workspace/group/<group_id>?user=<username>&chapter=<chapter>`
- 반환 필드: `selected_group`, `problems`, `status_map`, `latest_homework`

## 11) 검증/병행 운영 반영
- 이벤트 로깅 API 추가: `POST /api/chapter_workspace/events`
- 이벤트 요약 API 추가: `GET /api/chapter_workspace/events_summary?days=14`
- 로그 저장 위치: `meta/chapter_workspace_events.jsonl`
- 권장 이벤트:
  - `workspace_load_succeeded`, `workspace_load_failed`
  - `group_switch`
  - `workspace_copy_selected`
  - `workspace_save_succeeded`, `workspace_save_failed`
  - `workspace_leave`

요약 API 응답 핵심:
- `daily[].save_failure_rate`: 일자별 저장 실패율(%)
- `funnel.group_switch_to_save_conversion_rate`: 그룹 전환 세션 중 저장 성공 세션 비율(%)
- `groups[].save_per_switch`: 그룹별 전환 대비 저장 성공 비율(%)

## 12) 전환/정리 반영
- 기본 진입 전환 플래그:
  - `CHAPTER_WORKSPACE_DEFAULT_ENABLED=1`
  - 또는 `CHAPTER_WORKSPACE_DEFAULT_USERS=user1,user2`
- 베타 플래그(기존):
  - `CHAPTER_WORKSPACE_BETA_ENABLED=1`
  - 또는 `CHAPTER_WORKSPACE_BETA_USERS=user1,user2`
- fallback:
  - 챕터 fallback: `/user/<username>/chapter/<chapter>?legacy=1`
  - 그룹 fallback: `/user/<username>/chapter/<chapter>/group/<group_id>?legacy=1`
