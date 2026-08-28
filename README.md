# 📊 DoingCoding 학습 진도 및 숙제 관리 시스템 (Learning Tracker API)

DoingCoding(edu.doingcoding.com) 채점 서버 및 학원 포탈 데이터와 연동하여 수강생의 **실시간 문제 풀이 이력/진도율**을 수집·정제하고, 일자별 수업 스케줄링, 맞춤형 숙제 출제/관리, 학부모 알림장 서식 조립 및 외부 학원 관리 도구 연동을 지원하는 **Flask 기반 통합 학원 관리 백엔드 시스템**입니다.

> **Note:** 본 프로젝트는 **RDB(SQLite WAL 모드 / PostgreSQL 호환) 데이터 스토어**와 **Dual-Lookup Adapter (`internal_user_id`)**를 기반으로 백그라운드 비동기 동기화 큐를 지원하여, 디스크 I/O 및 외부 API 병목을 전면 제거하고 숙제 카드 조회 속도를 **1~2ms 대 (기존 대비 ~1,000배 이상)**로 획기적으로 단축하여 초고속으로 동작합니다.

---

## 📖 Project Story: 교육 현장의 비효율을 기술로 해결하다

> *"강사의 에너지는 행정이 아니라 교육에 집중되어야 합니다."*

매일 수십 명의 학생들의 진도를 여러 웹 페이지에서 일일이 확인하고 알림장을 적어 보내는 수동 행정 업무의 비효율을 해소하기 위해 직접 **인하우스 자동화 툴**을 설계하였습니다. 
진도 현황 자동 시각화, 지능형 숙제 제안, 클릭 한 번으로 가공되는 알림장 문구 작성 및 3종 클립보드 복사(학부모용/학생용/엑셀1줄)를 도입하여 강사진의 수강생 관리 소요 시간을 **획기적으로 단축**시켰습니다.

---

## ✨ 핵심 기능 (Key Features)

### 1. 📋 강사 피드백 & 카카오톡 알림장 모달 (`/templates/_feedback_modal.html`)
- **데스크톱 최적화 820px 2-Column Grid Layout**: 모달 너비를 820px로 확장하고 라디오 버튼을 1줄로 단정하게 배치하여 UI 가독성 대폭 향상.
- **학생 실제 소스코드 & 타임스탬프 비동기 연동**:
  - `/api/streak` 및 `/api/submission_code` 연동을 통해 학생이 실제 제출한 C/Python 소스코드와 풀이 시간(`[오늘 10:03:49]`)을 알림장 생성 데이터에 자동 연동.
- **1단계 관찰 메모 9종 퀵 태그 버튼 & Visual Highlight UX**:
  - `집중도`, `질문`, `오답`, `속도`, `개념재설명`, `문법실수`, `복습완료`, `심화도전`, `피곤함` 9종 프리셋 버튼 및 보라색 배경 Visual Active Highlight 동기화.
- **👀 완성될 카카오톡 알림장 실시간 미리보기 전용 카드**:
  - 좌측 컬럼 하단에 틴트 카드(`modalKakaoPreview`)를 배치하고 카톡 문구 실시간 렌더링 동기화.
- **🔄 복습 안내 모드 문구 및 목록 제어**:
  - `복습 세부 목록 표시` 체크 해제 시 소단원 링크 및 문제 목록 일체 스킵(피드백 코멘트 전용).
  - 체크 시 소단원 URL 링크(`🔗`)를 제외하고 `📘 소단원 제목`과 `  문제명`만 깔끔히 나열.
- **풀이 결과 3종 세분화 (🟢 정답 / 🟡 부분점수 / 🔴 오답)**:
  - 3개 테스트케이스 등 99점/Score >= 90점 항목을 `🟢 정답`으로 정상 분류하며, 1~89점 **부분점수(Partial)** 항목을 독립 표출.
- **단일 메인 버튼 UX 단순화**:
  - `📋 카카오톡 알림장 복사 & 숙제/피드백 저장` 단일 메인 버튼으로 정돈하여 클릭 시 초록색 `✅ 복사 & 저장 완료!` 변환 후 2.5초 모달 자동 닫기 적용.

---

### 2. 📊 메인 대시보드 카드 & 🔒 강사 피드백 보안 보호 (`index_view.js`)
- **숙제 풀이 상태 100% 실시간 동기화 & 6중 교차 대조**:
  - `legacy_code`, `server_problem_id`, 소문자, 정규화 문자열, `legacy_to_server` / `server_to_legacy` 역방향 매핑을 통한 **6중 교차 대조 알고리즘**을 적용하여 🟢정답(100점)/🟡부분점수/🔴오답/⚪미시도 상태 및 점수(`score`)를 정확하게 렌더링.
- **모드별 카드 UI 분기**:
  - `📘 숙제 출제`: 🟢정답/🟡부분점수/🔴오답/⚪미시도 실시간 문제별 뱃지 + 진행률 프로그레스 바 + 마감일.
  - `🔄 복습 안내` & `📝 수업 피드백`: 복습/피드백 요약 뱃지 표출.
- **🔒 강사 피드백 보안 토글 (Student Privacy Protection)**:
  - 카드 표면에 학생 시선에 노출될 위험이 있는 코멘트를 직접 노출하지 않고 `🔒 강사 피드백 보기` 클릭 아코디언 토글로 감싸 강사만 안전하게 확인.
- **`📋 카톡 알림장 재복사` 버튼**: 모달을 열지 않고 대시보드 카드에서 1초 만에 학부모용 카톡 전문 클립보드 재복사 지원.

---

### 3. 🌐 학원 연동 오픈 REST API (`feedback_routes.py`, `workspace_student_service.py`)
외부 출석부 및 대시보드 연동을 위한 경량 공개 API 엔드포인트를 제공합니다.

* **`GET /api/public/student-today-summary`**:
  - 포탈 ID(`portal_id`), 고유 식별자(`user_uuid`), 계정명(`display_id`), 또는 학생 실명(`name`) 중 하나로 학생을 자동 조회.
  - 당일 실시간 DoingCoding OJ 제출 이력(정답/오답 목록, 소스 코드 스니펫) 및 지정 숙제 문항(챕터명, 두잉코딩 바로가기 URL 포함)을 단일 JSON으로 반환.
* **`GET /api/public/search-accounts`**:
  - 1,040명 전체 수강생 목록에서 아이디, 이름, 부계정을 실시간으로 자동완성 검색.
* **`POST /api/public/update-student-mapping`**:
  - 학생 포탈 번호와 실제 OJ 계정명 간의 매핑을 영구 테이블(`meta/portal_mapping.json`)에 등록 및 갱신.

---

### 4. 📚 챕터별 학습 진행도 & 🎯 위치 찾기 (Drilldown Panel)
- **`🎯 위치 찾기` 원클릭 단원 탐색**:
  - `오늘 마지막 풀이` 카드에서 버튼 클릭 1번으로 해당 문제가 속한 **대단원 ➔ 소단원 ➔ 문제 위치**로 3단 목차가 자동 켜지며 연한 노란색 포커스 하이라이트 및 부드러운 스크롤(`smooth scroll`) 이동.
- **대단원 선택 시 1번째 소단원 자동 포커스**:
  - 대단원(1열) 선택 시 1번째 소단원이 자동으로 선택되어 3열 문제 목록이 추가 클릭 없이 즉시 표출.
- **`프로그래밍 II (심화)` 10개 대단원 완제 수집**:
  - `AL100`(알고리즘 기초)부터 `AL302`(알고리즘 골드2)까지 10개 단원 총 100개 핵심 문항 수집 및 계층형 드릴다운 표출.

---

### 5. 요일별 수업 스케줄 및 학생 관리 (`/schedule`)
* **요일별 시간표 슬롯(Slot) 생성 및 삭제**: 학원 수업 일정에 맞춘 실시간 시간표 배치 관리.
* **학생 식별자 표준화 (UUID & Display ID)**: 유저 고유 UUID 기반 JSON 저장 및 계정명/이름 3단계 자동 추정(Fallback Resolution) 구조.
* **출석부 및 상태 연동**: 당일 등원한 학생들의 목록과 학습 여부 한눈에 점검.

---

### 6. ⚡ 유저 식별자 통합 & RDB (SQLite WAL / PostgreSQL) 고성능 아키텍처
- **단일 표준 유저 식별자 (`internal_user_id`) 통합**:
  - `u_<UUID4_HEX>` 형태의 고유 식별자로 유저 테이블을 일원화하고, Dual-Lookup Adapter (`resolve_user_any`)를 구비하여 기존 UUID, username, 핸들 어느 것이 입력되어도 100% 매핑 처리.
- **SQLite WAL 모드 (`PRAGMA journal_mode=WAL`) & PostgreSQL 호환 ORM**:
  - `User`, `ExternalAccount`, `Chapter`, `Group`, `Problem`, `Submission`, `Assignment`, `AssignmentSubmission` 8개 정규화 테이블 구축.
  - WAL 모드로 동시성 읽기/쓰기 락을 방지하고 `USE_RDB_STORE` 듀얼 스토어 스위치를 도입하여 긴급 시 1초 만에 JSON 스토어로 즉시 원복 가능.
- **백그라운드 비동기 동기화 워커 (`src/workers/background_sync.py`)**:
  - 외부 DoingCoding 채점 서버 크롤링을 웹 요청 경로에서 전면 격리하여 데몬 스레드가 백그라운드에서 5분 간격 및 비동기 큐로 동기화.
- **프론트엔드 비동기 전환 & 1,000배 속도 개선**:
  - 메인 페이지 숙제 카드 로딩 속도 **3,000~10,000ms ➔ 1.3ms (약 1,200배 향상)** 달성.

---

## 🧱 디렉터리 구조

```
.
├── README.md
├── requirements.txt
├── backup/              # 마이그레이션 원본 자동 백업 디렉터리
├── meta/
│   ├── tracker.db       # SQLite RDB (WAL 모드 활성화)
│   ├── uuids.json       # legacy UUID 매핑 테이블
│   ├── portal_mapping.json # 포탈 번호 - OJ 계정 매핑 테이블
│   └── workspace_students.json # 전체 수강생 레지스트리
└── src/
    ├── app.py           # Flask 애플리케이션 엔트리, DB 및 백그라운드 워커 초기화
    ├── login.py         # DoingCoding 로그인 세션 핸들러
    ├── config.py        # 로컬 환경 설정 변수 (DATABASE_URL, USE_RDB_STORE)
    ├── db/              # SQLAlchemy RDB 레이어
    │   ├── base.py      # Declarative Base
    │   ├── session.py   # Engine / SessionFactory (SQLite WAL 모드 & 듀얼 스토어)
    │   ├── models.py    # 8개 ORM 모델 (User, Problem, Submission, Assignment 등)
    │   ├── repo.py      # Repository 레이어 (Dual-Lookup Adapter, Fast-path 조회)
    │   └── dual_store.py# USE_RDB_STORE 롤백 스위치
    ├── routes/          # Flask 블루프린트 라우트 디렉터리
    │   ├── workspace/   # 워크스페이스 및 공개 연동 API
    │   │   ├── feedback_routes.py # 학생 요약 및 계정 검색 공개 API
    │   │   └── student_routes.py
    ├── services/        # 서비스 레이어
    │   ├── workspace_student_service.py # 학생 요약, 매핑, 계정 검색 서비스
    │   └── problem_catalog_service.py   # 문제 카탈로그 메타데이터 서비스
    ├── workers/         # 백그라운드 동기화 워커
    │   └── background_sync.py # 비동기 큐 & 데몬 스레드
    ├── static/
    │   ├── css/         # unified.css, index_view.css 등
    │   └── js/
    │       ├── index_view.js      # 메인 대시보드 및 3단 드릴다운 제어
    │       ├── streak.js          # 학습 스트릭 및 오늘 마지막 풀이 카드 관리
    │       └── modules/           # 대시보드 마이크로 모듈
    │           ├── latest_homework_card.js
    │           ├── quick_basket.js
    │           └── feedback_modal.js
    ├── templates/       # HTML 템플릿 파일 디렉터리
    ├── problems_data/   # 문제 메타데이터 (all_problems.json)
    ├── users_data/      # 유저 JSON 스토어
    └── utils/           # 유틸리티 모듈
```

---

## ⚙️ 빠른 시작 (Quick Start)

### 1) 의존성 설치 (Python 3.10+ 권장)
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2) 환경변수 설정
`src/.env` 파일 설정:
```ini
API_BASE_URL=http://edu.doingcoding.com
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=1
USE_RDB_STORE=true
```

### 3) Flask 애플리케이션 실행
```bash
python src/app.py
```
브라우저를 열고 `http://127.0.0.1:5000/` 접속.

---

## 🔒 보안 및 데이터 무결성 주의 사항

* `cookies/` 디렉터리에 생성되는 DoingCoding 세션 쿠키 데이터와 `src/users_data/` 하위의 개인별 문제 제출 이력 JSON 파일은 **절대로 Git 저장소에 커밋하거나 공유하지 마십시오**. (`.gitignore` 설정 확인 권장)
* 수강생 고유 식별자는 `user_uuid` 및 `internal_user_id`로 안전하게 관리되며 로컬 데이터 무결성을 위해 주기적으로 `src/users_data/` 백업을 권장합니다.
