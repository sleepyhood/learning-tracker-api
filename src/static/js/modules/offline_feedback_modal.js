/**
 * offline_feedback_modal.js
 * 오프라인/교재 전용 1클릭 피드백 작성 모달 전용 JavaScript 모듈 (듀얼 백업 방어 구조)
 */

(function(window) {
    "use strict";

    const STORAGE_KEY = "learning_tracker_offline_feedback_history";

    // ai_prompt.js 미로드 시에도 100% 안전 작동하도록 내장된 디폴트 과목 도메인 맵
    const DEFAULT_OFFLINE_SUBJECT_DOMAINS = {
        scratch: {
            name: "Scratch 블록코딩",
            desc: "스크래치 시각적 블록 조립을 통한 순차, 조건, 반복 제어 및 이벤트 처리 논리 구조 학습",
            concepts: [
                { key: "scratch_basic", title: "기초 블록 순차/반복", desc: "이벤트 블록과 동작/모양 제어 블록을 조립하여 캐릭터 동작 구현" },
                { key: "scratch_cond", title: "조건문과 판단 블록", desc: "만약 ~라면 블록 및 감지 블록을 조합하여 조건 분기 알고리즘 익히기" },
                { key: "scratch_var", title: "변수와 리스트 제어", desc: "점수 및 데이터를 저장하는 변수 생성과 리스트 항목 가공 논리" },
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

    // 철통 방어 헬퍼 함수
    function getSubjectDomain(subjectKey) {
        const domains = window.OFFLINE_SUBJECT_DOMAINS || DEFAULT_OFFLINE_SUBJECT_DOMAINS;
        let d = domains[subjectKey] || domains.other || DEFAULT_OFFLINE_SUBJECT_DOMAINS.other;
        if (!d || !Array.isArray(d.concepts)) {
            d = DEFAULT_OFFLINE_SUBJECT_DOMAINS[subjectKey] || DEFAULT_OFFLINE_SUBJECT_DOMAINS.other;
        }
        return d;
    }

    let offlineState = {
        selectedSubject: "cos_scratch_2",
        selectedConceptKey: "",
        studentName: "",
        memo: "",
        status: "GOOD"
    };

    window.openOfflineFeedbackModal = function(defaultName = "", defaultId = "") {
        const modal = document.getElementById("offlineFeedbackModal");
        if (!modal) return;

        const customNameInput = document.getElementById("offlineStudentCustomName");

        if (defaultName) {
            if (customNameInput) customNameInput.value = defaultName;
            offlineState.studentName = defaultName;
        } else if (!customNameInput?.value) {
            if (customNameInput) customNameInput.value = "";
            offlineState.studentName = "";
        }

        // 기본 과목 및 세부 개념 초기화
        handleOfflineSubjectChange(offlineState.selectedSubject);
        renderOfflineHistoryList();

        modal.style.display = "flex";
        updateOfflineLivePreview();
    };

    window.closeOfflineFeedbackModal = function() {
        const modal = document.getElementById("offlineFeedbackModal");
        if (modal) modal.style.display = "none";
    };

    window.handleOfflineSubjectChange = function(subjectKey) {
        offlineState.selectedSubject = subjectKey;
        const domain = getSubjectDomain(subjectKey);
        
        const conceptSelect = document.getElementById("offlineConceptSelect");
        if (conceptSelect) {
            conceptSelect.innerHTML = "";
            if (Array.isArray(domain.concepts)) {
                domain.concepts.forEach(c => {
                    const opt = document.createElement("option");
                    opt.value = c.key;
                    opt.textContent = `${c.title}`;
                    conceptSelect.appendChild(opt);
                });

                if (domain.concepts.length > 0) {
                    offlineState.selectedConceptKey = domain.concepts[0].key;
                }
            }
        }

        updateOfflineConceptDesc();
        updateOfflineQuickTags();
        updateOfflineLivePreview();
    };

    function updateOfflineConceptDesc() {
        const descEl = document.getElementById("offlineConceptDesc");
        const select = document.getElementById("offlineConceptSelect");
        if (!descEl || !select) return;

        const key = select.value;
        offlineState.selectedConceptKey = key;
        const domain = getSubjectDomain(offlineState.selectedSubject);
        const concepts = domain.concepts || [];
        const concept = concepts.find(c => c.key === key) || concepts[0];

        if (concept) {
            descEl.innerHTML = `💡 <strong>학습목표:</strong> ${concept.desc}`;
        }
    }

    function updateOfflineQuickTags() {
        const container = document.getElementById("offlineQuickTags");
        if (!container) return;

        const defaultTags = [
            "😊 집중도 최고", "❓ 질문 적극적", "💡 오답 혼자 해결",
            "🧩 개념 이해 완료", "⚡ 풀이 속도 빠름", "🚀 자격증 대비 우수",
            "📘 교재 실습 완성", "⚠️ 예외케이스 보완필요"
        ];

        container.innerHTML = "";
        defaultTags.forEach(tag => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "quick-tag-btn";
            btn.style.fontSize = "0.72rem";
            btn.style.padding = "2px 6px";
            btn.textContent = tag;
            btn.onclick = () => {
                const memoEl = document.getElementById("offlineTeacherMemo");
                if (memoEl) {
                    let val = memoEl.value.trim();
                    if (val.includes(tag)) {
                        val = val.replace(tag, "").replace(/,\s*,/g, ",").replace(/^,\s*|\s*,\s*$/g, "").trim();
                    } else {
                        val = val ? `${val}, ${tag}` : tag;
                    }
                    memoEl.value = val;
                    updateOfflineLivePreview();
                }
            };
            container.appendChild(btn);
        });
    }

    /* 1단계: AI 프롬프트 클립보드 복사 */
    window.copyOfflineAiPrompt = async function() {
        const customName = (document.getElementById("offlineStudentCustomName")?.value || "").trim();
        const targetName = customName || "학생";

        const domain = getSubjectDomain(offlineState.selectedSubject);
        const conceptSelect = document.getElementById("offlineConceptSelect");
        const conceptKey = conceptSelect ? conceptSelect.value : "";
        const concepts = domain.concepts || [];
        const conceptObj = concepts.find(c => c.key === conceptKey) || concepts[0];
        const conceptTitle = conceptObj ? conceptObj.title : "";

        const memo = (document.getElementById("offlineTeacherMemo")?.value || "").trim();
        const statusVal = document.querySelector('input[name="offlineStatus"]:checked')?.value || "GOOD";
        const memoStr = memo || "수업 태도 우수하고 차분하게 실습 과제를 완수함 (특이사항 없음)";

        let promptText = "";
        if (typeof getOfflineAiPrompt === "function") {
            promptText = getOfflineAiPrompt(offlineState.selectedSubject, conceptTitle, targetName, memoStr, statusVal);
        } else {
            let statusText = "오늘 수업 성취도가 높고 과제를 안정적으로 완수했습니다.";
            if (statusVal === "WARNING") statusText = "기본 개념은 이해했으나 세부 조건 적용 및 실습 구현에서 일부 막힘이나 실수가 있었습니다.";
            else if (statusVal === "DANGER") statusText = "오늘 다룬 개념의 난도가 높아 초반 이해에 어려움을 겪었으며 원리 재설명과 보완이 진행되었습니다.";

            promptText = `[역할]
너는 코딩학원 전문 강사의 학부모 알림장 작성 전문 비서야.
아래 제공된 [수강생 이름], [수업 과목], [세부 학습 개념/유형], [오늘 성취도], [교사 관찰 메모]를 바탕으로 학부모님께 오늘 수업의 실습 내용과 보완점을 명확히 전달하는 신뢰감 있고 차분한 피드백 코멘트(존댓말, 2~3문장, 약 150~250자)를 작성해줘.

[작성 조건]
1. 무조건적인 칭찬을 지양하고, [실습 중 겪은 구체적 어려움/시행착오 ➔ 교사의 집중 코칭 및 교정 과정 ➔ 향후 보완 과제]의 인과 흐름으로 객관적이고 신뢰감 있게 서술해줘.
2. 성취도(${statusVal}) 및 관찰 메모의 특이사항을 사실에 기반해 서술하고, 과장·상투적 표현("빛나는 성과", "화이팅! 🚀")을 배제해줘.
3. 문장 끝에 '앞으로도 세심히 지도하겠습니다' 등의 상투적인 마무리 다짐 멘트는 절대로 작성하지 마세요.
4. 오직 카카오톡 알림장에 복사해 넣을 2~3문장의 최종 코멘트 텍스트만 출력해줘.

[정보]
- 수강생 이름: ${targetName}
- 과목: ${domain.name || "오프라인 교재"} (${domain.desc || ""})
- 세부 개념/유형: ${conceptTitle || "기초 진도"}
- 오늘 성취도: ${statusText}
- 교사 관찰 메모: ${memoStr}`;
        }

        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(promptText);
            } else {
                let textArea = document.createElement("textarea");
                textArea.value = promptText;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand("copy");
                textArea.remove();
            }
            if (typeof showToast === "function") {
                showToast("📋 AI 프롬프트가 복사되었습니다! (상투적 맺음말 제거 적용)");
            } else {
                alert("📋 AI 프롬프트가 복사되었습니다!");
            }
        } catch (e) {
            alert("프롬프트 복사 실패: " + e.message);
        }
    };

    /* 실시간 카톡 미리보기 갱신 */
    window.updateOfflineLivePreview = function() {
        const previewEl = document.getElementById("offlineKakaoPreview");
        if (!previewEl) return;

        const customName = (document.getElementById("offlineStudentCustomName")?.value || "").trim();
        const targetName = customName; // 미입력 시 빈 문자열

        const subjectKey = offlineState.selectedSubject;
        const domain = getSubjectDomain(subjectKey);

        const conceptSelect = document.getElementById("offlineConceptSelect");
        const conceptKey = conceptSelect ? conceptSelect.value : "";
        const concepts = domain.concepts || [];
        const conceptObj = concepts.find(c => c.key === conceptKey) || concepts[0];
        const conceptTitle = conceptObj ? conceptObj.title : "";

        const memo = (document.getElementById("offlineTeacherMemo")?.value || "").trim();
        const statusVal = document.querySelector('input[name="offlineStatus"]:checked')?.value || "GOOD";

        // 2단계 AI 답변 붙여넣기 란의 내용이 있으면 우선 적용
        const aiResponseInput = (document.getElementById("offlineAiResponseComment")?.value || "").trim();

        let statusComment = "";
        const subjectPrefix = targetName ? `${targetName} 학생은 오늘` : "오늘";

        if (aiResponseInput) {
            statusComment = aiResponseInput;
        } else {
            if (statusVal === "GOOD") {
                statusComment = `${subjectPrefix} 수업에 높은 집중도를 보이며 주어진 핵심 예제와 실기 과제를 높은 완성도로 스스로 구현해냈습니다.`;
            } else if (statusVal === "WARNING") {
                statusComment = `${subjectPrefix} 개념을 다지는 과정에서 일부 난이도 있는 구문에 부딪혔으나, 차근차근 원리를 재점검하며 끝까지 과제를 해결했습니다.`;
            } else {
                statusComment = `${subjectPrefix} 수업에서 다소 까다로운 구조에 부딪혀 핵심 개념을 다시 한번 짚어주며 원리를 익힐 수 있도록 지도했습니다.`;
            }

            if (memo) {
                statusComment += ` 특히 ${memo} 모습이 인상적이었습니다.`;
            }
        }

        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
        const wLabel = weekdays[now.getDay()];
        const dateStr = `${year}.${month}.${day}(${wLabel})`;

        const namePrefix = targetName ? `${targetName} 학부모님, ` : '';

        const fullMessage = `안녕하세요 ${namePrefix}두잉창의코딩학원입니다. 😊
오늘 수업 피드백 안내드립니다.

📝 [오늘 수업 피드백 & 태도]
오늘 [${domain.name} - ${conceptTitle}] 수업을 진행했습니다.
${statusComment}

🗓 수업일: ${dateStr}
=========================`;

        previewEl.textContent = fullMessage;
    };

    window.copyOfflineFeedbackToClipboard = async function() {
        const previewEl = document.getElementById("offlineKakaoPreview");
        if (!previewEl) return;

        const text = previewEl.textContent;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                let textArea = document.createElement("textarea");
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand("copy");
                textArea.remove();
            }
            if (typeof showToast === "function") {
                showToast("📋 카카오톡 알림장이 클립보드에 복사되었습니다!");
            } else {
                alert("📋 카카오톡 알림장이 복사되었습니다!");
            }
            saveOfflineFeedbackToHistory();
        } catch (e) {
            alert("복사 실패: " + e.message);
        }
    };

    window.saveOfflineFeedbackToHistory = function() {
        const previewEl = document.getElementById("offlineKakaoPreview");
        if (!previewEl) return;

        const customName = (document.getElementById("offlineStudentCustomName")?.value || "").trim();
        const targetName = customName || "학생";

        const domain = getSubjectDomain(offlineState.selectedSubject);

        const entry = {
            id: Date.now(),
            name: targetName,
            subject: domain.name,
            text: previewEl.textContent,
            time: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
        };

        let history = getHistoryFromStorage();
        history.unshift(entry);
        if (history.length > 10) history = history.slice(0, 10);

        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
        } catch (e) {
            console.error("Failed to save history to localStorage", e);
        }

        renderOfflineHistoryList();
    };

    function getHistoryFromStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    window.clearOfflineFeedbackHistory = function() {
        localStorage.removeItem(STORAGE_KEY);
        renderOfflineHistoryList();
    };

    function renderOfflineHistoryList() {
        const container = document.getElementById("offlineHistoryContainer");
        if (!container) return;

        const history = getHistoryFromStorage();
        if (history.length === 0) {
            container.innerHTML = '<div style="color: #94a3b8; padding: 8px; text-align: center;">저장된 히스토리가 없습니다.</div>';
            return;
        }

        container.innerHTML = "";
        history.forEach(item => {
            const div = document.createElement("div");
            div.style.cssText = "background:#f1f5f9; padding:5px 8px; border-radius:4px; margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;";
            
            const safeText = JSON.stringify(item.text).replace(/"/g, "&quot;");

            div.innerHTML = `
                <div style="flex:1; min-width:0; margin-right:6px;">
                    <div style="font-weight:bold; color:#1e293b; font-size:0.75rem;">${item.name} <span style="font-weight:normal; color:#64748b;">(${item.subject})</span></div>
                </div>
                <button class="btn-small btn-secondary" style="padding:2px 6px; font-size:0.72rem;" onclick="event.stopPropagation(); window.copySpecificOfflineText(${safeText})">📋 복사</button>
            `;
            container.appendChild(div);
        });
    }

    window.copySpecificOfflineText = async function(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                let textArea = document.createElement("textarea");
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand("copy");
                textArea.remove();
            }
            if (typeof showToast === "function") {
                showToast("📋 과거 히스토리 알림장이 복사되었습니다!");
            } else {
                alert("📋 복사되었습니다!");
            }
        } catch (e) {
            alert("복사 실패: " + e.message);
        }
    };

    // Event Bindings
    document.addEventListener("DOMContentLoaded", () => {
        const customNameInput = document.getElementById("offlineStudentCustomName");
        const conceptSelect = document.getElementById("offlineConceptSelect");
        const memoTextarea = document.getElementById("offlineTeacherMemo");
        const aiResponseInput = document.getElementById("offlineAiResponseComment");

        customNameInput?.addEventListener("input", updateOfflineLivePreview);
        conceptSelect?.addEventListener("change", () => {
            updateOfflineConceptDesc();
            updateOfflineLivePreview();
        });
        memoTextarea?.addEventListener("input", updateOfflineLivePreview);
        aiResponseInput?.addEventListener("input", updateOfflineLivePreview);
    });

})(window);
