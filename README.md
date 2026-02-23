# 📊 학습 진도 시각화 (Legacy Snapshot)

> 이 저장소는 **기존 아키텍처의 최종 스냅샷**입니다.
> 이후 개발은 **DB 도입 + React 프런트 + 경량화/최적화** 중심의 새 구조로 진행됩니다.
> (버그 수정만 최소한으로 반영, 신규 기능은 차세대 버전에서 개발)

---

## 📖 Project Story: 교육 현장의 비효율을 기술로 해결하다

> "강사의 에너지는 행정이 아니라 교육에 집중되어야 합니다."

이 프로젝트는 프로그래밍 학원 현장에서 강사가 겪는 **'수동 데이터 관리의 고통'**에서 시작되었습니다. 매일 수십 명의 학생들의 진도를 여러 사이트에서 일일이 확인하고 기록하는 비효율을 해결하기 위해, 직접 **인하우스 자동화 툴**을 구축했습니다.

### 🎯 주요 성과 (Impact)

- **행정 업무 효율화:** 수동 확인 방식을 API 자동화로 전환하여, 강사진의 학생 관리 소요 시간을 **약 00% 이상 단축**했습니다.
- **데이터 기반 상담:** 단순한 감이 아닌, 시각화된 대시보드를 통해 학부모 상담 및 학생 진도 관리에 객관적인 지표를 제공합니다.

### 💡 기술적 도전과 해결 (Engineering Note)

- **LLM 협업 및 직접 디버깅:** 초기 프로토타입 개발 시 LLM(Codex 등)을 활용해 속도를 높였으나, 외부 API의 복잡한 비정형 데이터(JSON) 파싱에서 발생하는 예외 상황들은 **직접 디버깅하고 스키마를 설계**하며 정밀도를 높였습니다.
- **아키텍처 리팩터링:** 초기 '크롤링' 기반의 불안정한 접근을 **'API 중심'**으로 리팩터링하여 데이터 수집의 안정성과 속도를 확보했습니다.

---

## ✨ 프로젝트 개요

DoingCoding(edu.doingcoding.com)의 **API**를 통해 수강생의 **문제 풀이 이력/진도**를 수집·정제하고, Flask 기반 웹 대시보드로 시각화하는 **Python 도구**입니다.
초기 크롤링 기반 접근을 API 중심으로 리팩터링한 버전이며, 파일 캐시(JSON)를 활용해 빠르게 시각화를 제공합니다.

---

## ✅ 이 스냅샷에 포함된 핵심 기능

- 로그인 세션 유지(쿠키 기반) 및 API 호출
- 문제 태그/챕터/그룹 단위 카탈로그 수집 및 정제(JSON)
- 사용자 제출(submissions) 수집·집계(해당 챕터/그룹/문제별 진행 현황)
- Flask + Jinja 템플릿 대시보드(챕터/그룹 상세, 진행 카드/차트)
- 환경변수/`.gitignore` 기반의 민감정보 분리
- (프런트 토대만 있음) **숙제 모드(assignMode)** UI 훅—백엔드 미구현

> 한계(스냅샷): 파일 캐시 중심 구조로 **동시성/무결성·검색성**이 약하고, **숙제/과제 백엔드**가 미구현입니다.

---

## 🧱 디렉터리 구조(요약)

```
.
├─ README.md
├─ .env                # 로컬 환경변수(예: API_BASE_URL 등)
├─ cookies.json        # 쿠키 스냅샷(민감, 커밋 금지 권장)
└─ src/
   ├─ app.py           # Flask 엔트리
   ├─ login.py
   ├─ templates/       # index.html, chapter_detail.html, group_detail.html ...
   ├─ static/          # style.css, js/, images/
   ├─ problems_data/   # 서버 문제 메타/카탈로그(JSON)
   ├─ users_data/      # 유저별 풀이 스냅샷(JSON, 저장소 제외 권장)
   └─ utils/           # requests wrapper, summarizer, streak utils, crawler 등
```

---

## ⚙️ 빠른 시작

```bash
# 1) 의존성 설치 (Python 3.10+ 권장)
pip install -r requirements.txt

# 2) 환경변수 설정
cp .env.example .env
# .env에 API_BASE_URL 등 채우기
# * DoingCoding 계정/쿠키는 로컬에서만 관리(커밋 금지)

# 3) 실행
python src/app.py
# 기본: http://127.0.0.1:5000
# 사내 공유 실행: FLASK_HOST=0.0.0.0 로 실행 후 http://<서버IP>:5000 접속
```

**.env 예시**

```
# DoingCoding API
API_BASE_URL=https://...
# 서버 바인딩(공유 운영 시 권장)
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=0

# 공유 스토리지 경로(선택)
# 여러 PC에서 같은 데이터가 보여야 하면 USER_DATA_DIR/PROBLEM_DIR/COOKIE_PATH를
# 동일한 공용 경로로 맞추세요.
# USER_DATA_DIR=Z:/learning-tracker/users_data
# PROBLEM_DIR=Z:/learning-tracker/problems_data
# COOKIE_PATH=Z:/learning-tracker/cookies.json

# 선택: 계정 직접 로그인 플로우를 사용할 경우
USER_ID=your_id
USER_PW=your_password

# 경로 커스터마이즈(단일 PC 운영 시)
# PROBLEM_DIR=./src/problems_data
# USER_DATA_DIR=./src/users_data
```

> 보안 안내
>
> - `cookies.json`, 유저별 JSON은 **커밋하지 마세요**.
> - 가능하면 `secrets/` 또는 OS 비밀 저장소에 보관하세요.
> - 파일명에 실명/개인정보가 드러나지 않도록 주의하세요.

---

## 🧭 사용 시나리오

- **학급/개인 진행 현황 점검**: 챕터/그룹별 통과율·시도 수·최근 활동(streak)을 개요 페이지에서 확인
- **문제 메타 리프레시**: 필요한 경우 도구 내부 엔드포인트(또는 스크립트)로 문제 카탈로그 강제 갱신
- **숙제 모드(프런트 토대)**: 선택 UI는 존재하나, 서버 저장/배포/마감 로직은 차세대 버전에서 구현

---

## 🚧 알려진 제한 사항(스냅샷)

- 파일 캐시에 의존 → **동시 접근/락·무결성** 취약
- 대규모 쿼리/통계에 비효율적
- **숙제/과제**: UI 토대만 존재, 백엔드는 미구현
- 스케줄러/큐 기반의 **자동 동기화/리포트** 미구현

---

## 🔭 다음 버전(차세대) 로드맵 요약

> 이 부분은 새 저장소/브랜치에서 진행됩니다. 아래는 설계 방향 요약입니다.

### 1) 백엔드 & 데이터

- **PostgreSQL** + **SQLAlchemy & Alembic** 도입(마이그레이션 관리)
- 핵심 스키마(예시)
  - 카탈로그: `chapters`, `groups`, `problems`, `problem_aliases`
  - 계정/수업: `users`, `classes`, `enrollments`, `external_accounts(enc_cookies)`
  - 진행/제출: `submissions`, `user_problem_status`, `progress_snapshots`
  - 숙제: `assignments`, `assignment_problems`, `assignment_submissions`
  - 운영/감사: `sync_jobs`, `audit_logs`

- **머티리얼라이즈드 뷰**로 주간/숙제 통계 가속(`mv_user_weekly_progress`, `mv_assignment_stats`)

### 2) 애플리케이션 구조

- Flask(또는 FastAPI) **레이어드 구조**
  - `adapters/doingcoding` : API 우선 + 크롤링 fallback, 재시도/레이트리밋 표준화
  - `services/` : 집계/동기화/숙제 등 도메인 로직
  - `routes/` : `auth`, `sync`, `progress`, `assignments` 등 블루프린트 분리

- **작업 큐 + 스케줄러**
  - RQ/Celery + Redis로 `sync_user`, `sync_class` 잡 구성
  - APScheduler로 야간 동기화(예: 02:00 KST), 주간 리포트 예약

### 3) 프런트엔드

- **React + Vite**로 경량 SPA
  - 상태관리/쿼리 캐싱, 컴포넌트 단위 차트(예: Recharts/Chart.js)
  - 기존 `assignMode`를 **과제 생성 → 배포 → 현황/마감** 플로우와 연결
  - RBAC(관리자/강사/학생) 뷰 분리

### 4) 보안/운영

- **쿠키/토큰 암호화 저장**, 만료 자동 감지 및 재인증 플로우
- **로그/메트릭/감사 로그** 표준화(요청/응답 핵심 필드)
- 백업 전략: DB 스냅샷 + 오브젝트 스토리지 버전닝

---

## 🔁 마이그레이션(파일 → DB) 가이드 스케치

1. **문제 메타 이행**
   - `server_problems.json` + 내부 카탈로그 매핑을 이용해 `chapters/groups/problems` 업서트

2. **유저 진행/제출 이행**
   - `users_data/*.json`에서 문제별 최신 상태·제출 이벤트 파싱
   - `submissions`와 `user_problem_status` 적재 → 요약 뷰 리프레시

3. **검증**
   - 미매핑/다중매핑 리포트 출력, 수동 보정 워크플로우

> 실제 스크립트/DDL, 새 디렉터리 구조는 차세대 저장소에서 제공됩니다.

---

## 🔗 관련 프로젝트

- **COS 스크래치 자동 채점기**: Scratch(.sb2) 내부 JSON 파싱으로 자동 채점, HTML 리포트 출력
- (이 프로젝트) **학원 사이트 기반 진도 시각화(API 리팩터링판)**

---

## 🤝 기여 & 라이선스

- 내부 교육 운영을 위한 프로젝트입니다. 외부 기여(PR) 환영합니다.
- 라이선스: 저장소 루트의 `LICENSE` 참고(미포함 시 추후 명시).

---

## 📝 변경 이력(요약)

- 2025-08-28: 기존 아키텍처 **Legacy Snapshot** 선언, 차세대 설계 로드맵 공개
