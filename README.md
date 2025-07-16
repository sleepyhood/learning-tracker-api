# 📊 학습 진도 시각화 프로젝트 (API 기반)

이 프로젝트는 [DoingCoding](http://edu.doingcoding.com) 학습 사이트의 **API**를 통해,  
수강생의 **문제 풀이 이력 및 학습 진도**를 수집/분석하고 시각화하는 Python 기반 도구입니다.

> 기존 크롤링 기반 프로젝트: [crawling-edu-progress](https://github.com/sleepyhood/crawling-edu-progress)  
> 이 프로젝트는 해당 접근 방식을 **API 기반으로 리팩터링**한 버전입니다.

---

## 💡 주요 기능

- 로그인 세션 유지 및 쿠키 기반 인증
- 문제 태그(Lv, SLv) 기반 문제집 목록 수집
- 각 문제집별 문제 상세 정보 수집
- 사용자 제출 결과(submissions) 수집 및 정리
- 문제집 구조로 재가공된 JSON 변환
- 향후 Flask 등으로 시각화 웹 대시보드 개발 예정
- `.gitignore`와 `.env`를 통한 민감 정보 관리

---

## 📦 사용 기술

- Python 3.10+
- `requests`, `selenium`, `webdriver-manager`
- `json`, `dotenv`, `os`, `re` 등 내장 모듈
- Git / GitHub

---

## 🗂️ 디렉토리 구조 예시

```

project/
│
├── crawl/ # 크롤링 및 API 요청 모듈
│ └── login.py # 로그인 & 쿠키 처리
│
├── data/ # 수집된 JSON 저장 위치
│ └── tags.json
│
├── utils/ # 유틸 함수 모듈
│ └── processor.py
│
├── secrets/ # 민감 정보 보관 (gitignore 대상)
│ ├── cookies.json
│ └── .env
│
├── .gitignore
├── README.md
└── main.py # 실행 진입점

```

---

## 🔐 보안 주의사항

- 아이디/비밀번호, 쿠키 등 **민감 정보는 `secrets/` 디렉토리에 분리**됩니다.
- `.env` 예시 파일을 배포 시 제공하며, 실제 정보는 로컬에서만 관리됩니다.
- `.gitignore`에 해당 항목이 포함되어 있으니, 깃헙에 업로드되지 않습니다.

---

## 🛠️ 개발 TODO

- [ ] 문제 태그 기반 구조(JSON)로 재가공 정리
- [ ] 유저별 문제집 학습 진도율 계산
- [ ] 제출 결과 통계화 (제출 횟수, 성공률 등)
- [ ] Flask 기반 웹 대시보드 시각화
- [ ] `cron` 혹은 CLI 자동화 루틴 구축

---

## ⚙️ 설치 및 실행 방법 (예정)

```bash
# 의존 패키지 설치
pip install -r requirements.txt

# 환경변수 세팅
cp secrets/.env.example secrets/.env
# 또는 직접 환경 변수 설정

# 실행
python main.py
```

> ※ 실제 실행 예시는 프로젝트 진행에 따라 갱신될 수 있습니다.

---

## 🔗 참고 링크

- 학원 사이트: [http://edu.doingcoding.com](http://edu.doingcoding.com)
- 이전 프로젝트: [crawling-edu-progress](https://github.com/sleepyhood/crawling-edu-progress)

---

## 📝 라이선스 및 기여

- 개인 학습용으로 제작된 프로젝트입니다.
- 외부 기여, Pull Request 환영합니다!
