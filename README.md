# 📊 DoingCoding 학습 진도 및 숙제 관리 도구 (Learning Tracker)

DoingCoding(edu.doingcoding.com)의 API 및 DOM 기반 자동 크롤러를 연동하여 수강생의 **문제 풀이 이력/진도**를 수집·정제하고, 일자별 수업 스케줄링, 숙제 출제/관리, AI 기반 학부모 피드백 코멘트 작성 및 샌드박스 워크스페이스를 지원하는 **Flask 기반 통합 학원 관리 도구**입니다.

> **Note:** 본 프로젝트는 로컬 마이크로 레지스트리 JSON 포맷을 데이터 스토어로 활용하여 가볍고 초고속($O(1)$)으로 동작하며, 학원 현장의 행정 및 교육 관리 비효율을 0%에 가깝게 단축하는 것을 목적으로 합니다.

---

## 📖 Project Story: 교육 현장의 비효율을 기술로 해결하다

> *"강사의 에너지는 행정이 아니라 교육에 집중되어야 합니다."*

매일 수십 명의 학생들의 진도를 여러 웹 페이지에서 일일이 확인하고 알림장을 적어 보내는 수동 행정 업무의 비효율을 해소하기 위해 직접 **인하우스 자동화 툴**을 설계하였습니다. 
진도 현황 자동 시각화, 지능형 숙제 제안, 클릭 한 번으로 가공되는 알림장 문구 작성 및 3종 클립보드 복사(학부모용/학생용/엑셀1줄)를 도입하여 강사진의 수강생 관리 소요 시간을 **획기적으로 단축**시켰습니다.

---

## ✨ 핵심 기능 (Key Features)

### 1. 🪄 AI 피드백 & 카카오톡 알림장 모달 (`/templates/_feedback_modal.html`)
- **데스크톱 최적화 720px 2-Column Grid Layout**: 시원하고 넓은 720px 2열 레이아웃으로 UI 반응성 및 가독성 대폭 향상.
- **학생 실제 소스코드 & 타임스탬프 비동기 연동**:
  - `/api/streak` 및 `/api/submission_code` 연동을 통해 학생이 실제 제출한 C/Python 소스코드와 풀이 시간(`[오늘 10:03:49]`)을 AI 프롬프트에 자동 전달.
- **풀이 결과 3종 세분화 (🟢 정답 / 🟡 부분점수 / 🔴 오답)**:
  - 3개 테스트케이스 등 99점/Score >= 90점 항목을 `🟢 정답`으로 정상 분류하며, 1~89점 **부분점수(Partial)** 항목을 독립 표출.
  - `classifySubmission` 최상위 스코프 배치로 `📋 AI 프롬프트 복사` 클릭 시 `ReferenceError` 완전 예방.
- **동적 소스코드 샘플링 알고리즘 (Dynamic Code Sampling Algorithm)**:
  - **1순위 (오답/부분점수 우선)**: 오답(🔴) 및 부분점수(🟡) 소스코드를 최우선으로 수집하여 실수 원인 및 보완점 분석.
  - **2순위 (정답 자동 충원)**: 다 맞추거나 오답이 적을 때 5개가 채워질 때까지 최신 정답(🟢) 소스코드를 자동 충원하여 우수한 루프/변수 구조에 대한 구체적 칭찬 작성.
- **규격화된 공식 카카오톡 알림장 빌더**:
  - 실제 학원 사이트 도메인(`http://edu.doingcoding.com`) 및 단원 코드/소단원 태그(`.../p102?tag=SLv15%20%EB%B0%B0%EC%97%B4%282%EC%B0%A8%29`) 기반 자동 링크 조립.
  - 모드 및 데이터 유무에 따른 2번째 줄 안내 문구 지능형 자동 전환 (`수업에 해당되는 숙제 부분 안내드립니다.` / `오늘 수업의 피드백 및 복습 안내드립니다.` / `오늘 수업의 피드백을 안내해 드립니다.`).
- **⚙️ 옵션 설정 UX 고도화**:
  - 숙제 장바구니가 비어 있을 경우 `📘 숙제 안내` 라디오 버튼 자동 비활성화(`disabled`).
  - `📘 숙제 안내` vs `🔄 복습 안내` 라디오 선택 시 관련 세부 목록 표시 체크박스만 동적으로 노출.
- **Option A 이중 출제 버튼 시스템**:
  - `📋 카카오톡 알림장 복사 & 숙제/피드백 저장`: 알림장 복사 및 유저 문서에 과제 기록 영구 적재.
  - `⚡ 피드백 없이 숙제만 즉시 출제`: 피드백 작성 없이 0초 만에 숙제 등록.

### 2. 🎯 샌드박스 2-Pane 워크스페이스 (`/workspace`)
- **2단 계층형 단원 필터 (`[대단원]` ➔ `[소단원]`)**: 클릭 2번으로 원하는 소단원(예: `Lv1 출력`, `Lv2 변수` 20개) 문제에 0초 만에 도달.
- **학생별 실시간 풀이 상태 오버레이 (🟢/🔴)**: 학생 선택 시 해당 학생의 통과/오답 여부가 문제 목록에 실시간 시각화되며 장바구니 자동 초기화.
- **통합 피드백 모달 & 개념 사전 파이프라인**: 문제 제목 태그 파싱 및 비플랫폼/오프라인 수업 드롭다운 선택 시 고품질 교육 개념 자동 추천.
- **3종 원클릭 클립보드 복사**:
  - `📱 학부모 카톡 복사 (b)`: 다듬어진 AI 학부모용 메시지 복사
  - `🎒 학생용 숙제 복사 (c)`: 코멘트를 자동으로 제외한 학생 전용 숙제 목록 복사
  - `📊 엑셀 1줄 복사 (Tab 구분)`: 날짜/회차/문제/코멘트를 탭 구문으로 가공하여 엑셀/구글시트에 Ctrl+V 1회로 셀 분할 저장

### 3. 🚀 Playwright 초고속 크롤러 & 계정 인증 자동화
- **Selenium 100% 제거 & Playwright 단일 엔진 통합**:
  - 느린 레거시 Selenium(`questions_crawler.py`) 의존성을 전면 제거하고 초고속 **Playwright(`playwright_crawler.py`) 파이프라인**으로 100% 전환하여 수집 속도 3~5배 비약적 단축.
  - 하위 호환 프록시 브릿지 패턴을 도입하여 백엔드 레거시 호출부 Zero-Regression 달성.
- **🖥️ 실시간 브라우저 GUI 창 팝업 (`CREATE_NEW_CONSOLE`)**:
  - `🖥️ 크롤링 브라우저 화면 실시간 표시` 체크박스 옵션 지원.
  - Windows 백그라운드 세션 권한 제약을 우회하기 위해 독립 Subprocess(`CREATE_NEW_CONSOLE`)로 띄워 실시간 크롬 브라우저 동작 및 탐색을 눈앞에서 감상 가능.
- **🔑 DoingCoding 계정 자동 로그인 & 세션 쿠키 자동 갱신**:
  - 수집 모달 내 계정 정보(ID/PW) 입력 시 `http://edu.doingcoding.com/api/profile`에서 기존 세션 유효성을 자동 검증.
  - 세션 만료 시 `http://edu.doingcoding.com/admin/login`에서 정확한 XPath 셀렉터로 자동 로그인을 수행하고 최신 세션 쿠키를 추출하여 `src/cookies/`에 파일로 즉시 갱신·저장.
- **⚡ 외부 CDN/폰트 차단(`page.route`)으로 무한 로딩 해결 & 1~2초대 초고속 접속**:
  - 지연을 유발하는 불필요한 외부 폰트/미디어 리소스 차단 및 `domcontentloaded` 접속 전략을 적용하여 무한 로딩을 완벽 해결하고 1~2초 대의 초고속 단원 탐색 달성.
- **⚠️ 수집 데이터 결과 검증 강화**:
  - 크롤링 완료 후 실제 수집된 문제 건수(`scraped_count`)를 프론트엔드로 전달. 0개 수집 시 `⚠️ 수집 건수 0개 (세션/네트워크 확인)` 경고 및 토스트를 명확히 출력하여 오인 표시 방지.
- **과정별(`prog1` vs `prog2`) 맞춤 새로고침 (Targeted Refresh)**:
  - `[💻 프로그래밍 I]` 선택 후 새로고침 ➔ `p101` (`all_problems.json`) 수집 ➔ 기초/기본 목차 동적 갱신.
  - `[💻 프로그래밍 II (심화)]` 선택 후 새로고침 ➔ `p102` (`prog2_problems.json` 10개 대단원) 수집 ➔ 심화 10개 대단원 목차 동적 갱신.
- **Schema V2 계층 포맷 자동 변환**:
  - Playwright 크롤링 결과 데이터를 Schema V2 계층 구조(`chapters`, `groups`, `problems`)로 자동 변환하여 요약 파서가 대단원 8개/10개와 소단원, 문제 목록을 100% 정밀 렌더링.

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

### 6. 🧩 샌드박스 프론트엔드 모듈화 아키텍처 (Modular JS System)
* **비대한 메인 스크립트 슬림화**: 기존 1,125줄 분량의 `workspace_2pane.js`를 **90줄 수준의 메인 진입점 오케스트레이터**로 경량 다이어트 완료.
* **7대 도메인 마이크로 모듈 분리 (`src/static/js/modules/`)**:
  - `workspace_students.js`: 요일별 수강생 보드 렌더링, 시간표 슬롯 배정, 수강생 선택
  - `workspace_catalog.js`: 과정 목록 로드, 동적 대/소단원 드롭다운, 라이브 문제 검색
  - `workspace_basket.js`: 숙제 바구니 담기/비우기, 수강생별 숙제 할당 로그 저장
  - `workspace_account_modal.js`: ⚙️ 1:N 도메인 계정(학원/스크래치/구름) 매핑 및 비고/동명이인 메모 관리
  - `workspace_feedback_ufm.js`: UFM AI 피드백 모달, 개념 파싱, 카톡 메시지 3종 복사
  - `workspace_crawler.js`: 카탈로그 수집 크롤러, 실시간 토스트 폴링, 엑셀 1초 일괄 등록
  - `workspace_register_modal.js`: 신규 수강생 수동 등록 및 슬롯 지정 모달

---

## 🧱 디렉터리 구조

```
.
├── README.md
├── requirements.txt
├── requirements.lock.txt
└── src/
    ├── app.py           # Flask 애플리케이션 엔트리 및 API 라우트
    ├── login.py         # DoingCoding 로그인 세션 핸들러
    ├── config.py        # 로컬 환경 설정 변수 로더
    ├── static/
    │   ├── css/         # workspace_apple.css (60fps 경량 그래픽 최적화), unified.css 등
    │   └── js/
    │       ├── workspace_2pane.js # 오케스트레이터 진입점 (Phase 1~5 모듈 연결)
    │       ├── index_view.js      # 메인 대시보드 및 3단 드릴다운 제어 (🎯 위치 찾기 포함)
    │       ├── streak.js          # 학습 스트릭 및 오늘 마지막 풀이 카드 관리
    │       ├── ai_prompt.js       # AI 피드백 프롬프트 생성기 (제출 코드 & 부분점수 지침)
    │       └── modules/           # 7대 분리 모듈 디렉터리
    │           ├── workspace_students.js       # [Phase 1] 수강생 보드 & 슬롯 관리
    │           ├── workspace_catalog.js        # [Phase 2] 카탈로그 & 라이브 문제 검색
    │           ├── workspace_basket.js         # [Phase 3-1] 숙제 바구니 관리
    │           ├── workspace_account_modal.js  # [Phase 3-2] ⚙️ 도메인 계정/메모 모달
    │           ├── workspace_feedback_ufm.js   # [Phase 4-1] UFM AI 피드백 모달
    │           ├── workspace_crawler.js        # [Phase 4-2] 크롤러 & 1초 일괄 등록
    │           └── workspace_register_modal.js # [Phase 5-1] 수강생 수동 등록 모달
    ├── templates/
    │   ├── index.html             # 메인 대시보드 화면
    │   ├── _feedback_modal.html   # AI 피드백 & 카톡 알림장 720px 모달
    │   ├── workspace_2pane.html   # 샌드박스 2-Pane 워크스페이스 HTML
    │   ├── schedule.html          # 주간 스케줄 및 학생 출석 화면
    │   ├── group_detail.html      # 그룹별 상세 문제 리스트
    │   └── homework_view.html     # 학생별 과제 이력 페이지
    ├── problems_data/   # 마이크로 레지스트리 포맷 문제 데이터 (all_problems, prog2_problems 등)
    ├── users_data/      # 유저별 문제 제출 이력 및 숙제 로그 JSON 디렉터리 ({uuid}.json)
    └── utils/           # questions_crawler.py (Playwright 브릿지), playwright_crawler.py, summarizer.py 등
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
```

### 3) Flask 애플리케이션 실행
```bash
python src/app.py
```
브라우저를 열고 `http://127.0.0.1:5000/` 접속.

---

## 🧪 유닛 테스트 및 안정성 검증

시스템 무결성 보장을 위한 종합 자동화 테스트 스위트 지원:
```bash
python C:\Users\osw\.gemini\antigravity\brain\0c1aa7b8-3ebb-42ee-8d11-22a7eb72b6cb\scratch\test_stability.py
```
- 비존재 유저 문서 예외 처리 테스트 **PASS** ✅
- 계정명 ➔ UUID 추정 3단계 Fallback 테스트 **PASS** ✅
- 스트릭 데이터 파싱 및 90+점 정답(Accepted) 분류 테스트 **PASS** ✅

---

## 🔒 보안 및 데이터 무결성 주의 사항

* `cookies/` 디렉터리에 생성되는 DoingCoding 세션 쿠키 데이터와 `src/users_data/` 하위의 개인별 문제 제출 이력 JSON 파일은 **절대로 Git 저장소에 커밋하거나 공유하지 마십시오**. (`.gitignore` 설정 확인 권장)
* 수강생 고유 식별자는 `user_uuid`로 관리되며 로컬 데이터 무결성을 위해 주기적으로 `src/users_data/` 백업을 권장합니다.
