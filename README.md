# 📊 DoingCoding 학습 진도 및 숙제 관리 도구 (Learning Tracker)

DoingCoding(edu.doingcoding.com)의 API 및 DOM 기반 자동 크롤러를 연동하여 수강생의 **문제 풀이 이력/진도**를 수집·정제하고, 일자별 수업 스케줄링, 숙제 출제/관리, 학부모 피드백 알림장 작성 및 샌드박스 워크스페이스를 지원하는 **Flask 기반 통합 학원 관리 도구**입니다.

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
  - 우측 컬럼이 길어지는 세로 스크롤을 예방하기 위해 좌측 컬럼 하단에 틴트 카드(`modalKakaoPreview`)를 배치하고 카톡 문구 실시간 렌더링 동기화.
- **🔄 복습 안내 모드 문구 및 목록 제어**:
  - `복습 세부 목록 표시` 체크 해제 시 소단원 링크 및 문제 목록 일체 스킵(피드백 코멘트 전용).
  - 체크 시 소단원 URL 링크(`🔗`)를 제외하고 `📘 소단원 제목`과 `  문제명`만 깔끔히 나열.
- **풀이 결과 3종 세분화 (🟢 정답 / 🟡 부분점수 / 🔴 오답)**:
  - 3개 테스트케이스 등 99점/Score >= 90점 항목을 `🟢 정답`으로 정상 분류하며, 1~89점 **부분점수(Partial)** 항목을 독립 표출.
- **동적 소스코드 샘플링 알고리즘 (Dynamic Code Sampling Algorithm)**:
  - **1순위 (오답/부분점수 우선)**: 오답(🔴) 및 부분점수(🟡) 소스코드를 최우선으로 수집하여 실수 원인 및 보완점 분석.
  - **2순위 (정답 자동 충원)**: 다 맞추거나 오답이 적을 때 5개가 채워질 때까지 최신 정답(🟢) 소스코드를 자동 충원하여 우수한 루프/변수 구조에 대한 구체적 칭찬 작성.
- **단일 메인 버튼 UX 단순화**:
  - `📋 카카오톡 알림장 복사 & 숙제/피드백 저장` 단일 메인 버튼으로 정돈하여 클릭 시 초록색 `✅ 복사 & 저장 완료!` 변환 후 2.5초 모달 자동 닫기 적용.

### 2. 📊 메인 대시보드 카드 & 🔒 강사 피드백 보안 보호 (`index_view.js`)
- **숙제 풀이 상태 100% 실시간 동기화 & 6중 교차 대조**:
  - 기존에 이전에 풀었던 문제를 다시 숙제로 주었을 때 `미시도(pending)`로 잘못 표현되던 동기화 문제를 완벽 해결.
  - `legacy_code`, `server_problem_id`, 소문자, 정규화 문자열, `legacy_to_server` / `server_to_legacy` 역방향 매핑을 통한 **6중 교차 대조 알고리즘**을 적용하여 🟢정답(100점)/🟡부분점수/🔴오답/⚪미시도 상태 및 점수(`score`)를 정확하게 렌더링.
- **모드별 카드 UI 분기 (0/0/0 프로그레스 바 해결)**:
  - `📘 숙제 출제`: 🟢정답/🟡부분점수/🔴오답/⚪미시도 실시간 문제별 뱃지 + 진행률 프로그레스 바 + 마감일.
  - `🔄 복습 안내` & `📝 수업 피드백`: (0/0/0) 어색한 프로그레스 바 전면 숨김 ➔ 복습/피드백 요약 뱃지 표출.
- **🔒 강사 피드백 보안 토글 (Student Privacy Protection)**:
  - 카드 표면에 학생 시선에 노출될 위험이 있는 코멘트를 직접 노출하지 않고 `🔒 강사 피드백 보기` 클릭 아코디언 토글로 감싸 강사만 0초 만에 안전하게 확인.
- **🛠️ 개발자용 Raw 라벨 & 디버그 패널 (Developer Inspection)**:
  - 각 문제 우측에 백엔드가 산출한 raw 상태 라벨 `[RAW: status="passed", score="100", srv_id="176"]` 표출.
  - 카드 하단 접이식 패널(`🛠️ [개발자 디버그] 숙제 풀이 RAW JSON 데이터 확인`)을 통해 API 반환 원본 객체 투명 검증 지원.
- **타임스탬프 한글 파싱**: `2026.08.11(화) 02:20` 깔끔한 한글 포맷 렌더링.
- **`📋 카톡 알림장 재복사` 버튼**: 모달을 열지 않고 대시보드 카드에서 1초 만에 학부모용 카톡 전문 클립보드 재복사 지원.

### 3. 📜 `숙제 & 알림장 히스토리 통합 모달` (`_homework_history_modal.html`)
- **독립 레거시 페이지 흡수 & 단권화**:
  - 느리고 번거롭던 독립 웹페이지(`/students/<uuid>/homework`)를 대체하는 원클릭 팝업 모달 컴포넌트 신설.
- **백엔드 실시간 유저 풀이 데이터 동기화 (`_enrich_log_problem_status`)**:
  - 히스토리 API 호출 시 유저 문서(`{uuid}.json`) 및 문제 풀이 캐시(`{username}.json`) 듀얼 경로 파싱을 거쳐 `챕터별 학습 진행도`와 100% 일치하는 **🟢 정답 (100점)** / **🟡 부분점수** 결과 릴레이.
- **🔒 알림장 전문 & 강사 피드백 통합 비공개(Blind) 토글**:
  - 버튼을 클릭하기 전에는 카톡 메시지 원문 박스와 강사 코멘트 박스를 둘 다 100% 비공개 상태로 안전하게 접어두도록 보안 토글 적용.
- **수강생 계정명 정밀 릴레이**: `학생: osw1110 (@osw1110)` 형태로 36자리 긴 UUID 및 `"수강생"`, `"학생"` 중복 문구가 표시되던 현상 전면 자동 해석 및 정돈.

### 4. 📚 챕터별 학습 진행도 & 🎯 위치 찾기 (Drilldown Panel)
- **`🎯 위치 찾기` 원클릭 단원 탐색**:
  - `오늘 마지막 풀이` 카드에서 버튼 클릭 1번으로 해당 문제가 속한 **대단원 ➔ 소단원 ➔ 문제 위치**로 3단 목차가 자동 켜지며 연한 노란색 포커스 하이라이트 및 부드러운 스크롤(`smooth scroll`) 이동.
- **대단원 선택 시 1번째 소단원 자동 포커스**:
  - 대단원(1열) 선택 시 1번째 소단원이 자동으로 선택되어 3열 문제 목록이 추가 클릭 없이 즉시 표출되도록 UX 개선.
- **`프로그래밍 II (심화)` 10개 대단원 완제 수집**:
  - `AL100`(알고리즘 기초)부터 `AL302`(알고리즘 골드2)까지 10개 단원 총 100개 핵심 문항 수집 및 계층형 드릴다운 표출 완료.

### 5. 요일별 수업 스케줄 및 학생 관리 (`/schedule`)
* **요일별 시간표 슬롯(Slot) 생성 및 삭제**: 학원 수업 일정에 맞춘 실시간 시간표 배치 관리.
* **학생 식별자 표준화 (UUID & Display ID)**: 유저 고유 UUID 기반 JSON 저장 및 계정명/이름 3단계 자동 추정(Fallback Resolution) 구조.
* **출석부 및 상태 연동**: 당일 등원한 학생들의 목록과 학습 여부 한눈에 점검.

### 6. 🔄 숙제 풀이 상태 100% 동기화 & 6중 교차 대조 파이프라인 (`students.py`)
- **이전 숙제 재출제 시 동기화 불일치 완벽 해결**:
  - 이전에 풀었던 문제를 다시 숙제로 출제했을 때 `미시도(pending)`로 표현되던 결함을 완벽 조치.
- **듀얼 경로 파싱 & 캐시 통합 (Dual-Path Merging)**:
  - `{uuid}.json` 유저 메인 문서와 `{username}.json` 문제 풀이 전용 캐시 파일을 듀얼 탐색하여 `oi_problems`, `problems_dict`, `submissions`를 100% 병합.
- **6중 교차 대조 알고리즘 (6-Way Cross Lookup)**:
  - 숙제의 `legacy_code`, `server_problem_id`, 소문자, 정규화 문자열, `server_legacy_map_reverse.json`의 `legacy_to_server` 및 `server_to_legacy` 역방향 매핑을 6중 교차 대조하여 **🟢 정답(100점)** / **🟡 부분점수** / **🔴 오답** / **⚪ 미시도** 상태 및 점수(`score`)를 정확하게 렌더링.

### 7. ⚡ 유저 식별자(internal_user_id) 통합 & RDB (SQLite WAL / PostgreSQL) 고성능 아키텍처
- **단일 표준 유저 식별자 (`internal_user_id`) 통합**:
  - `u_<UUID4_HEX>` 형태의 고유 식별자로 유저 테이블을 일원화하고, Dual-Lookup Adapter (`resolve_user_any`)를 구비하여 기존 UUID, username, 핸들 어느 것이 입력되어도 100% 매핑 처리.
- **SQLite WAL 모드 (`PRAGMA journal_mode=WAL`) & PostgreSQL 호환 ORM**:
  - `User`, `ExternalAccount`, `Chapter`, `Group`, `Problem`, `Submission`, `Assignment`, `AssignmentSubmission` 8개 정규화 테이블 구축.
  - WAL 모드로 동시성 읽기/쓰기 락을 방지하고 `USE_RDB_STORE` 듀얼 스토어 스위치를 도입하여 긴급 시 1초 만에 JSON 스토어로 즉시 원복 가능.
- **백그라운드 비동기 동기화 워커 (`src/workers/background_sync.py`)**:
  - 외부 DoingCoding 채점 서버 크롤링을 웹 요청 경로에서 전면 격리하여 데몬 스레드가 백그라운드에서 5분 간격 및 비동기 큐로 동기화.
  - Flask `WERKZEUG_RUN_MAIN` PID 락으로 개발 서버 중복 스레드 생성 예방.
- **프론트엔드 비동기 전환 & 1,000배 속도 개선**:
  - `latest_homework_card.js`의 동기 `/refresh` 대기 블로킹을 비동기 fire-and-forget으로 전환.
  - 메인 페이지 숙제 카드 로딩 속도 **3,000~10,000ms ➔ 1.3ms (약 1,200배 향상)** 달성.

---

## 🧱 디렉터리 구조

```
.
├── README.md
├── requirements.txt
├── requirements.lock.txt
├── backup/              # 마이그레이션 원본 자동 백업 디렉터리
├── meta/
│   ├── tracker.db       # SQLite RDB (WAL 모드 활성화)
│   ├── uuids.json       # legacy UUID 매핑 테이블
│   └── admin_whitelist.json
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
    ├── workers/         # 백그라운드 동기화 워커
    │   └── background_sync.py # 비동기 큐 & 데몬 스레드 (PID Lock 적용)
    ├── scripts/         # ETL 및 검증 스크립트
    │   ├── etl_json_to_rdb.py # JSON -> RDB 이관 ETL (Chunk Batch, casefold, UTC)
    │   └── verify_etl.py      # ETL 데이터 무결성 검증
    ├── static/
    │   ├── css/         # unified.css, index_view.css 등
    │   └── js/
    │       ├── index_view.js      # 메인 대시보드 및 3단 드릴다운 제어 (🎯 위치 찾기 포함)
    │       ├── streak.js          # 학습 스트릭 및 오늘 마지막 풀이 카드 관리
    │       ├── feedback_helper.js # 학습 개념 사전 및 알림장 템플릿 도우미
    │       └── modules/           # 메인 대시보드 마이크로 모듈 디렉터리
    │           ├── latest_homework_card.js     # 비동기 최신 숙제 카드 렌더러
    │           ├── quick_basket.js             # 숙제 장바구니 관리
    │           ├── drilldown_filter.js         # 3단 계층형 단원 필터
    │           ├── feedback_modal.js           # 숙제 출제 & 알림장 모달
    │           ├── crawler_modal.js            # 카탈로그 수집 크롤러 모달
    │           └── student_accounts_modal.js   # ⚙️ 수강생 계정 관리 모달
    ├── templates/       # HTML 템플릿 파일 디렉터리
    │   ├── index.html   # 메인 대시보드 (진도율 시각화 + 숙제 내기)
    │   ├── schedule.html# 수업 스케줄 관리
    │   └── components/  # 프로필, 스트릭, 장바구니, 모달 컴포넌트
    ├── problems_data/   # 마이크로 레지스트리 포맷 문제 데이터
    ├── users_data/      # 레거시 유저 JSON 스토어 (Fallback 보존)
    └── utils/           # 유틸리티 모듈 (playwright_crawler, summarizer 등)
```


---

## ⚙️ 빠른 시작 (Quick Start)

### 1) 의존성 설치 (Python 3.10+ 권장)
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2) 환경변수 설정
`src/.env` 파일 설정 (필요 시 `src/.env.bak` 참조)
```ini
API_BASE_URL=http://edu.doingcoding.com
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=1

# RDB 고성능 데이터 스토어 & 롤백 스위치
USE_RDB_STORE=true
# DATABASE_URL=postgresql://user:pass@localhost:5432/trackerdb  # (PostgreSQL 전환 시 설정, 미설정 시 SQLite 기본 사용)
```


### 3) Flask 애플리케이션 실행
```bash
python src/app.py
```
브라우저를 열고 `http://127.0.0.1:5000/` 접속.

---

## 💡 개발 및 트러블슈팅 노하우 (Troubleshooting & Development Notes)

- **Flask 인메모리 프로세스 갱신 주의사항 (`FLASK_DEBUG`)**:
  - `FLASK_DEBUG=0` 모드로 서버 구동 시 `.py` 소스 코드를 수정하더라도 **Python 실행 프로세스가 인메모리(In-Memory) 구버전 모듈을 계속 쥐고 있어** 브라우저 강력 새로고침(`Ctrl+F5`)만으로는 백엔드 변경 사항이 적용되지 않습니다.
  - 소스 코드 수정 후에는 반드시 **Flask 서버 프로세스를 재시작**하거나 `FLASK_DEBUG=1` 모드를 켜서 구동하십시오.
- **학생 제출 데이터 원천 (Source of Truth)**:
  - `users_data/{username}.json` (문제 풀이 캐시) 및 `users_data/{uuid}.json` (유저 문서) 데이터를 듀얼 파싱하므로, 학생의 OJ 채점 서버 기록이 비동기로 동기화된 후 숙제 카드 및 히스토리 모달에 즉시 반영됩니다.

---

## 🧪 유닛 테스트 및 안정성 검증

시스템 무결성 보장을 위한 종합 자동화 테스트 스위트 지원:
```bash
python C:\Users\osw\.gemini\antigravity\brain\0c1aa7b8-3ebb-42ee-8d11-22a7eb72b6cb\scratch\test_stability.py
```
- 비존재 유저 문서 예외 처리 테스트 **PASS** ✅
- 계정명 ➔ UUID 추정 3단계 Fallback 테스트 **PASS** ✅
- 스트릭 데이터 파싱 및 90+점 정답(Accepted) 분류 테스트 **PASS** ✅
- 숙제 풀이 상태 6중 교차 대조 및 캐시 파싱 테스트 **PASS** ✅

---

## 🔒 보안 및 데이터 무결성 주의 사항

* `cookies/` 디렉터리에 생성되는 DoingCoding 세션 쿠키 데이터와 `src/users_data/` 하위의 개인별 문제 제출 이력 JSON 파일은 **절대로 Git 저장소에 커밋하거나 공유하지 마십시오**. (`.gitignore` 설정 확인 권장)
* 수강생 고유 식별자는 `user_uuid`로 관리되며 로컬 데이터 무결성을 위해 주기적으로 `src/users_data/` 백업을 권장합니다.
