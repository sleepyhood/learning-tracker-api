/**
 * feedback_helper.js
 * 수강생 학습 개념 사전 및 관찰 메모 / 알림장 템플릿 도우미
 */

const STUDY_CONCEPTS = {
  "출력": "화면에 서식과 특수문자를 제어하여 텍스트 및 결과를 출력하는 기초 문법 개념",
  "변수": "데이터(정수, 실수, 문자)를 메모리에 저장하고 가공하여 알맞은 변수 타입으로 다루는 기본 원리",
  "연산자": "산술, 비교, 논리 연산자를 조합하여 원하는 계산 결과를 도출하는 식 구성 논리",
  "조건문": "조건식의 참/거짓 판단을 통해 프로그램의 진행 흐름을 분기시키는 구조",
  "반복문": "특정 구간을 지정된 횟수나 조건만큼 반복 실행하여 효율적인 루프를 제어하는 알고리즘",
  "배열": "동일한 타입의 데이터들을 연속된 메모리 공간에 묶어서 인덱스를 통해 관리하는 자료구조",
  "배열2차": "격자판 형태의 다차원 데이터를 다중 루프 구조와 행/열 인덱스로 제어하는 심화 논리",
  "함수": "재사용 가능한 코드 블록을 모듈화하고 매개변수와 반환값을 다루는 프로그래밍 구조",
  "문자열": "문자 배열 및 문자열 조작 함수를 활용하여 텍스트 데이터를 분석하고 처리하는 기술",
  "포인터": "메모리 주소에 직접 접근 및 참조 구조를 이해하고 제어하는 C언어 심화 개념"
};

const OFFLINE_PRESETS = [
  { id: "doingcoding", name: "💻 DoingCoding 플랫폼", concept: "DoingCoding 문제 풀이 기반 학습" },
  { id: "c_book", name: "📘 C언어 교재 진도", concept: "C언어의 기본 자료형, 제어문 및 텍스트 기반 기초 코딩 문법을 교재를 보며 연습" },
  { id: "python_book", name: "🐍 파이썬 교재 진도", concept: "파이썬의 동적 자료구조와 기본 함수 활용법을 익히고, 교재 내 실습 문제를 개별 구현" },
  { id: "scratch_block", name: "🐱 블록코딩 (스크래치/엔트리)", concept: "블록을 조립하며 프로그램의 순차, 반복, 조건 3대 논리 제어 구조를 시각적·직관적으로 학습" },
  { id: "goorm_cert", name: "🏆 구름(Goorm) 자격증 실기", concept: "자료형 변환 및 코딩 테스트용 기초 알고리즘을 분석하며 자격증 실기 평가 문항 구현 대비" },
  { id: "theory_logic", name: "💡 알고리즘 및 순서도 이론", concept: "구현에 앞서 논리적인 문제 해결력과 문제 접근 아이디어를 키우기 위한 알고리즘 순서도 설계 수업" }
];

function extractConceptDescription(problemTitle) {
  if (!problemTitle) return "";
  const match = problemTitle.match(/\[(.*?)\]/);
  if (!match) return "";
  const tag = match[1];
  for (const key in STUDY_CONCEPTS) {
    if (tag.includes(key)) {
      return STUDY_CONCEPTS[key];
    }
  }
  return "";
}

function toggleQuickTag(textareaId, tagText) {
  const el = document.getElementById(textareaId);
  if (!el) return;

  let val = el.value.trim();
  if (val.includes(tagText)) {
    val = val.replace(tagText, "").replace(/,\s*,/g, ",").replace(/^,\s*|\s*,\s*$/g, "").trim();
  } else {
    val = val ? `${val}, ${tagText}` : tagText;
  }
  el.value = val;

  if (typeof autoExpandModalTextarea === "function" && (textareaId === "modalTeacherMemo" || textareaId === "teacherMemo")) {
    autoExpandModalTextarea(el);
  }
}

/* 과목별 개념 도메인 맵 */
window.OFFLINE_SUBJECT_DOMAINS = {
  scratch: {
    name: "Scratch 블록코딩",
    desc: "스크래치 시각적 블록 조립을 통한 순차, 조건, 반복 제어 및 이벤트 처리 논리 구조 학습",
    concepts: [
      { key: "scratch_basic", title: "기초 블록 순차/반복", desc: "이벤트 블록과 동작/모양 제어 블록을 조립하여 캐릭터 동작 구현" },
      { key: "scratch_cond", title: "조건문과 판단 블록", desc: "만약 ~라면 블록 및 감지 블록을 조합하여 조건 분기 알고리즘 익히기" },
      { key: "scratch_var", title: "변수 및 리스트 제어", desc: "점수 및 데이터를 저장하는 변수 생성과 리스트 항목 가공 논리" },
      { key: "scratch_signal", title: "신호 보내기 및 방송", desc: "스프라이트 간 메시지 전달(신호 보내기)을 통한 장면 전환과 상호작용" },
      { key: "scratch_clone", title: "복제본(클론) 생성을 통한 게임 구현", desc: "나 자신 복제하기 블록을 활용하여 장애물 생성 및 적 캐릭터 연출" }
    ]
  },
  cos_scratch_3: {
    name: "COS (Scratch) 3급 자격증",
    desc: "COS Scratch 3급 실기 평가 대비 기초 블록 조립, 순차·조건·반복 제어 및 간단한 프로젝트 구현",
    concepts: [
      { key: "cos_s3_seq", title: "순차 및 기본 동작 제어", desc: "COS 3급 평가 항목: 좌표 이동, 모양 바꾸기 및 기본 이벤트 조립" },
      { key: "cos_s3_loop", title: "반복문과 감지 연산", desc: "COS 3급 평가 항목: ~까지 반복하기 및 벽에 닿았는가 감지 판단" },
      { key: "cos_s3_project", title: "3급 실기 종합 프로젝트", desc: "기출 예제 분석: 간단한 애니메이션 및 미로 탈출 프로젝트 구현" }
    ]
  },
  cos_scratch_2: {
    name: "COS (Scratch) 2급 자격증",
    desc: "COS Scratch 2급 실기 평가 대비 변수, 난수, 신호 방송, 연산자 활용 중급 실기 프로젝트 완성",
    concepts: [
      { key: "cos_s2_var", title: "변수 및 난수 활용 계산", desc: "COS 2급 평가 항목: 변수 값 변경, 난수 생성 및 점수 계산 알고리즘" },
      { key: "cos_s2_broadcast", title: "신호 보내기 및 장면 제어", desc: "COS 2급 평가 항목: 방송하기와 받기 블록을 이용한 게임 씬 전환" },
      { key: "cos_s2_op", title: "연산자 및 판단 조건 결합", desc: "COS 2급 평가 항목: 그리고/또는/아니다 논리 연산 조합 및 경계 조건 처리" },
      { key: "cos_s2_mock", title: "2급 실기 모의고사 점검", desc: "2급 실기 기출 모의고사 풀이 및 요구사항 정확도 체크" }
    ]
  },
  cos_pro_2: {
    name: "COS PRO 2급 (Python/C/C++/Java)",
    desc: "COS PRO 2급 자격증 실기 평가 대비 빈칸 채우기, 한 줄 수정(디버깅), 기초 알고리즘 구현",
    concepts: [
      { key: "cos_p2_fill", title: "빈칸 채우기 (Fill-in-the-blank)", desc: "COS PRO 2급 핵심 유형: 주어진 코드 흐름을 분석하여 괄호 안의 정답 표현식 작성" },
      { key: "cos_p2_fix", title: "한 줄 수정 (One-line Debugging)", desc: "COS PRO 2급 핵심 유형: 잘못된 한 줄의 조건식/연산자를 찾아 올바르게 수정" },
      { key: "cos_p2_impl", title: "기초 구현 (Implementation)", desc: "COS PRO 2급 핵심 유형: 배열 탐색, 최대/최소값 구하기, 문자열 처리 문제 직접 코딩" },
      { key: "cos_p2_mock", title: "2급 실기 모의고사 기출 풀이", desc: "실제 검정 시험 기준 10문항 완주 훈련 및 제출 검증" }
    ]
  },
  cos_pro_1: {
    name: "COS PRO 1급 (Python/C/C++/Java)",
    desc: "COS PRO 1급 자격증 실기 평가 대비 자료구조, 고급 알고리즘(DP/DFS/BFS), 심화 디버깅 검증",
    concepts: [
      { key: "cos_p1_ds", title: "자료구조 활용 (Stack/Queue/Graph)", desc: "COS PRO 1급 핵심 유형: 스택, 큐, 해시, 그래프 등 적절한 자료구조 적용" },
      { key: "cos_p1_algo", title: "고급 알고리즘 (DP / DFS / BFS)", desc: "COS PRO 1급 핵심 유형: 동적 계획법 및 완전 탐색 알고리즘 설계" },
      { key: "cos_p1_fix", title: "1급 심화 코드 디버깅 및 한 줄 수정", desc: "COS PRO 1급 핵심 유형: 복잡한 비즈니스 로직 및 예외 케이스 내 오류 탐지 및 수정" },
      { key: "cos_p1_mock", title: "1급 실기 모의고사 최상위 훈련", desc: "1급 시험 기준 고난도 10문항 타임어택 분석 및 최적화" }
    ]
  },
  other: {
    name: "기타 오프라인 교재 및 진도",
    desc: "기타 자체 교재, C/Python 기본 문법, 오프라인 이론 수업 및 개별 프로젝트",
    concepts: [
      { key: "other_grammar", title: "기본 프로그래밍 문법 및 제어 구조", desc: "변수, 연산자, 조건문, 반복문 등 기본 제어 흐름 연습" },
      { key: "other_project", title: "개별 실습 및 소형 프로젝트", desc: "배운 개념을 적용하여 스스로 주제를 선정하고 코드로 구현" },
      { key: "other_theory", title: "알고리즘 사고력 및 순서도 설계", desc: "문제 해결 과정 시각화 및 논리적 접근법 연습" }
    ]
  }
};

// 글로벌 등록
window.STUDY_CONCEPTS = STUDY_CONCEPTS;
window.OFFLINE_PRESETS = OFFLINE_PRESETS;
window.extractConceptDescription = extractConceptDescription;
window.toggleQuickTag = toggleQuickTag;
