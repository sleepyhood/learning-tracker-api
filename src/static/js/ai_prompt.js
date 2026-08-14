/**
 * ai_prompt.js
 * AI 알림장 코멘트 프롬프트 생성기 (온라인 및 오프라인 공통)
 * - 단순 칭찬 일색을 지양하고 [팩트/시행착오 ➔ 지도/해결 과정 ➔ 복습/보완점]의 균형 잡힌 전문 코칭 피드백 생성
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

/**
 * 온라인 피드백 모달용 프롬프트 생성 (OJ 풀이로그 기반)
 */
function getAiPrompt(problemsSummary, finalMemo, todaySolvingLog = "") {
  let extraLogInfo = "";
  if (todaySolvingLog && todaySolvingLog.trim()) {
    extraLogInfo = `\n- 오늘 수업 실습 로그 및 학생 제출 코드:\n${todaySolvingLog.trim()}`;
  }

  const memoText = finalMemo && finalMemo.trim() ? finalMemo.trim() : "오늘 수업에 성실히 임함 (특이사항 없음)";
  const summaryText = problemsSummary && problemsSummary.trim() ? problemsSummary.trim() : "숙제 및 복습 지정 내역 없음";

  return `[역할]
너는 코딩학원 전문 강사의 학부모 알림장 작성 전문 비서야.
제공된 [오늘 수업 실습 로그 및 제출 코드], [숙제/복습 지정 내역], [교사 관찰 메모]를 바탕으로, 학부모님께 오늘 수업의 실제 과정과 학습 보완점을 명확히 전달하는 정중하고 차분한 피드백 코멘트(존댓말, 2~3문장, 약 150~250자)를 작성해줘.

[핵심 작성 원칙]
1. **무조건적인 칭찬이나 미화 지양**: 학생의 부족한 점이나 실수를 무조건 덮어두지 말고, **[실제 겪은 시행착오나 실수 ➔ 수업 중 지도 및 해결 과정 ➔ 앞으로의 보완점/과제 연계]**의 3단 인과관계로 사실에 기반하여 전문성 있게 서술해줘.
2. **시행착오의 구체적 명시**:
   - 오답/부분점수/컴파일에러가 있었다면: 무엇 때문에 틀렸는지(예: 조건문 경계값 누락, 루프 범위 오류, 변수 초기화 실수, 세미콜론/오타 등)를 객관적으로 짚고, 이를 어떻게 수정했는지 서술.
   - 전부 정답이더라도: 단순히 '잘했다'가 아니라 어떤 로직(효율적인 제어문, 구조적 설계 등)을 잘 활용했는지와 다음 단계 과제를 짚어줌.
3. **과장·상투적 AI 표현 배제**: "한 단계 성장할 것입니다", "눈부신 발전", "화이팅! 🚀" 같은 기계적 감탄사나 과장 표현 금지.
4. **상투적 맺음말 금지 (절대 작성 금지)**: 문장 끝에 '앞으로도 세심히 지도하겠습니다', '지속적으로 관찰하겠습니다', '체계적으로 지도하려 합니다' 등과 같은 의례적인 교사 다짐 멘트는 일절 쓰지 말고, 오늘 수업 내용과 과제 안내로만 깔끔하게 끝맺어줘.
5. **호칭 자연화**: '학생', '교사'라는 단어를 직접 명시하지 말고 자연스러운 주어 생략 또는 부드러운 서술체(~했습니다, ~하도록 지도했습니다, ~과제로 안내했습니다)를 사용해줘.
6. **오직 복사해서 알림장에 바로 쓸 최종 2~3문장의 코멘트 텍스트만 출력해줘.**

[정보]${extraLogInfo}
- 숙제/복습 지정 내역:
${summaryText}
- 교사 관찰 메모: ${memoText}

[답변 예시 (참고용)]:
- 예시 A (오답/부분점수 극복 후 숙제 연계):
"오늘 다중 조건문 실습 중 경계값(0 또는 음수 입력) 처리에서 일부 오답이 발생했으나, 반례를 분석하며 스스로 조건식의 범위를 수정해 최종 정답을 도출했습니다. 수업 후에도 이러한 예외 처리 감각을 유지할 수 있도록 오늘 다룬 핵심 제어문 2문항을 과제로 안내했습니다."
- 예시 B (문법/오타 실수 보완 지도):
"문제의 알고리즘 흐름은 정확하게 설계했으나, 변수명 오타와 세미콜론 누락으로 인한 컴파일 에러가 초반에 잦아 코드를 실행하기 전 한 번 더 꼼꼼히 점검하는 습관을 중점 지도했습니다. 스스로 오류를 디버깅하는 속도가 점차 안정되었으며, 완벽히 체화할 수 있도록 오늘 풀이한 문항의 복습을 권장했습니다."
- 예시 C (전부 정답 & 심화 풀이):
"오늘 다룬 2차원 배열 격자 순회 문제를 추가 힌트 없이 2중 루프와 인덱스 연산만을 활용해 깔끔한 구조로 완성해냈습니다. 기본 개념에 대한 이해도가 매우 탄탄하여, 다음 진도에 앞서 다양한 변형 형태를 경험해볼 수 있도록 응용 문항을 과제로 출제했습니다."`;
}

/* Phase 1: 오프라인 / 교재 전용 과목별 도메인 지식 맵 */
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

/**
 * 오프라인 피드백 모달용 프롬프트 생성 (교재/실기 진도 기반)
 */
function getOfflineAiPrompt(subjectKey, conceptTitle, studentName, memo, statusVal = "GOOD") {
  const domain = window.OFFLINE_SUBJECT_DOMAINS?.[subjectKey] || window.OFFLINE_SUBJECT_DOMAINS?.other || { name: "오프라인 수업", desc: "개별 진도 학습" };
  const nameStr = studentName ? studentName.trim() : "학생";
  const memoStr = memo && memo.trim() ? memo.trim() : "수업 태도 양호하며 당일 실습 과제를 차분히 수행함";

  let statusText = "오늘 수업 성취도가 높고 과제를 안정적으로 완수했습니다.";
  let statusGuide = "기본 개념을 잘 숙지했음을 짚어주되, 다음 심화 단계나 세부 구현 시 신경 써야 할 포인트를 함께 전달하세요.";
  
  if (statusVal === "WARNING") {
    statusText = "기본 개념은 이해했으나 세부 조건 적용 및 실습 구현에서 일부 막힘이나 실수가 있었습니다.";
    statusGuide = "어떤 부분에서 혼란이나 실수가 있었는지 객관적으로 짚고, 수업 중 어떻게 교정했는지와 가정에서의 가벼운 복습 필요성을 서술하세요.";
  } else if (statusVal === "DANGER") {
    statusText = "오늘 다룬 개념의 난도가 높아 초반 이해에 어려움을 겪었으며 원리 재설명과 보완이 진행되었습니다.";
    statusGuide = "학생을 탓하지 않고 개념의 난이도로 인해 막혔던 지점을 명확히 설명한 뒤, 시각화/원리 분해로 다시 다잡은 과정과 차후 반복 학습 계획을 서술하세요.";
  }

  return `[역할]
너는 코딩학원 전문 강사의 학부모 알림장 작성 전문 비서야.
제공된 [수강생 이름], [수업 과목], [세부 학습 개념/유형], [오늘 성취도 현황], [교사 관찰 메모]를 바탕으로 학부모님께 오늘 수업의 실습 내용과 보완점을 명확히 전달하는 신뢰감 있고 차분한 피드백 코멘트(존댓말, 2~3문장, 약 150~250자)를 작성해줘.

[핵심 작성 원칙]
1. **무조건적인 칭찬 지양**: 무조건 잘했다는 식의 미화는 피하고, **[실습 중 겪은 구체적 어려움/시행착오 ➔ 교사의 집중 코칭 및 교정 과정 ➔ 향후 보완 과제]**의 인과 흐름으로 객관적이고 신뢰감 있게 서술해줘.
2. **성취도 및 메모 사실 반영**:
   - 성취도(${statusVal})와 교사 관찰 메모의 내용(예: 특정 블록 연결 실수, 변수 개념 혼동, 오타, 집중도 등)을 숨기지 말고 수업 중 어떻게 짚고 넘어갔는지 명시해줘.
3. **과장·상투적 표현 배제**: "빛나는 성과", "화이팅! 🚀", "무한한 가능성" 등 기계적인 감탄사 배제.
4. **상투적 맺음말 금지 (절대 작성 금지)**: 문장 끝에 '앞으로도 세심히 지도하겠습니다', '지속적으로 관찰하겠습니다' 등의 의례적인 마무리 다짐 멘트는 절대로 작성하지 마세요. 오늘 실습한 내용과 가정에서 신경 쓸 포인트로만 담백하게 끝맺으세요.
5. **호칭 자연화**: 수강생 이름('${nameStr}')을 자연스럽게 활용하고, '학생'/'교사'라는 단어를 직접 언급하지 마세요.
6. **오직 복사해서 카카오톡 알림장에 바로 쓸 최종 2~3문장의 코멘트 텍스트만 출력해줘.**

[정보]
- 수강생 이름: ${nameStr}
- 과목: ${domain.name} (${domain.desc})
- 세부 개념/유형: ${conceptTitle || "기초 진도"}
- 오늘 성취도: ${statusText} (지침: ${statusGuide})
- 교사 관찰 메모: ${memoStr}

[답변 예시 (참고용)]:
- 예시 A (성취도 보통/보완 - WARNING):
"오늘 ${conceptTitle || "실습"} 과정에서 조건 판단 블록과 변수 변경 순서가 엇갈려 의도치 않은 동작이 발생했으나, 단계별 실행 흐름을 함께 짚어보며 올바른 위치로 블록을 재배치했습니다. 원리는 충분히 이해했으므로 교재에 수록된 유사 유형을 집에서 한 번 더 확인해본다면 완전히 본인의 것으로 체화할 수 있을 것입니다."
- 예시 B (성취도 우수 - GOOD):
"${conceptTitle || "오늘 개념"}의 핵심 원리를 빠르게 이해하고 주어진 실습 예제를 스스로 막힘없이 완성했습니다. 기본 구현력이 안정적이므로, 다음 수업에서는 한 단계 높은 응용 과제와 예외 상황 처리에 도전할 수 있도록 안내했습니다."`;
}

// 글로벌 등록
window.STUDY_CONCEPTS = STUDY_CONCEPTS;
window.OFFLINE_PRESETS = OFFLINE_PRESETS;
window.extractConceptDescription = extractConceptDescription;
window.toggleQuickTag = toggleQuickTag;
window.getAiPrompt = getAiPrompt;
window.getOfflineAiPrompt = getOfflineAiPrompt;
