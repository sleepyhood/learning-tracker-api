// workspace_feedback_ufm.js - 통합 AI 피드백 모달(UFM) & 코멘트 컨트롤 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceFeedbackUfm = {
        currentUfmStudent: null,
        currentUfmProblems: [],

        init: function() {
            this.bindEvents();
            this.initPresetDropdown();
        },

        initPresetDropdown: function() {
            const ufmPresetSelect = document.getElementById("ufm-preset-select");
            if (typeof OFFLINE_PRESETS !== "undefined" && ufmPresetSelect) {
                ufmPresetSelect.innerHTML = "";
                OFFLINE_PRESETS.forEach(p => {
                    const opt = document.createElement("option");
                    opt.value = p.id;
                    opt.textContent = p.name;
                    ufmPresetSelect.appendChild(opt);
                });
            }
        },

        bindEvents: function() {
            const ufmModal = document.getElementById("unified-feedback-modal");
            const ufmPresetSelect = document.getElementById("ufm-preset-select");

            document.getElementById("btn-close-ufm")?.addEventListener("click", () => {
                ufmModal?.classList.remove("show");
            });

            ufmPresetSelect?.addEventListener("change", () => {
                this.updateUfmConceptView();
            });

            document.getElementById("btn-copy-ufm-prompt")?.addEventListener("click", () => {
                this.copyUfmPrompt();
            });

            document.getElementById("btn-copy-parent-msg")?.addEventListener("click", () => {
                this.copyParentMsg();
            });

            document.getElementById("btn-copy-student-msg")?.addEventListener("click", () => {
                this.copyStudentMsg();
            });

            document.getElementById("btn-copy-excel-line")?.addEventListener("click", () => {
                this.copyExcelLine();
            });

            document.getElementById("btn-save-ufm-final")?.addEventListener("click", () => {
                this.saveUfmFinal();
            });
        },

        updateUfmConceptView: function() {
            const ufmPresetSelect = document.getElementById("ufm-preset-select");
            const ufmConceptText = document.getElementById("ufm-concept-text");
            if (!ufmPresetSelect || !ufmConceptText) return;

            const selectedId = ufmPresetSelect.value;
            const preset = typeof OFFLINE_PRESETS !== "undefined" ? OFFLINE_PRESETS.find(p => p.id === selectedId) : null;
            if (selectedId === "doingcoding") {
                let autoConcepts = [];
                if (typeof extractConceptDescription === "function") {
                    this.currentUfmProblems.forEach(p => {
                        const desc = extractConceptDescription(p.title);
                        if (desc && !autoConcepts.includes(desc)) {
                            autoConcepts.push(desc);
                        }
                    });
                }
                if (autoConcepts.length > 0) {
                    ufmConceptText.textContent = autoConcepts.join(" / ");
                } else {
                    ufmConceptText.textContent = "DoingCoding 문제 풀이 기반 학습 (자동 감지 중)";
                }
            } else if (preset) {
                ufmConceptText.textContent = preset.concept;
            }
        },

        generateFeedback: async function(displayId, event) {
            if (event) event.stopPropagation();
            const students = window.students || [];
            const student = students.find(s => s.display_id === displayId);
            this.currentUfmStudent = student || { display_id: displayId, name: displayId };

            const ufmModal = document.getElementById("unified-feedback-modal");
            const ufmStudentName = document.getElementById("ufm-student-name");
            const ufmTeacherMemo = document.getElementById("ufm-teacher-memo");
            const ufmAiComment = document.getElementById("ufm-ai-comment");
            const ufmProblemSummary = document.getElementById("ufm-problem-summary");
            const ufmPresetSelect = document.getElementById("ufm-preset-select");

            if (ufmStudentName) ufmStudentName.textContent = this.currentUfmStudent.name;
            if (ufmTeacherMemo) ufmTeacherMemo.value = "";
            if (ufmAiComment) ufmAiComment.value = "";
            if (ufmProblemSummary) ufmProblemSummary.innerHTML = "불러오는 중...";
            if (ufmPresetSelect) ufmPresetSelect.value = "doingcoding";

            ufmModal?.classList.add("show");

            try {
                const res = await fetch(`/api/workspace/student_problems/${displayId}`);
                if (res.ok) {
                    const data = await res.json();
                    this.currentUfmProblems = data.problems || [];
                    this.renderUfmProblemSummary();
                    this.updateUfmConceptView();
                } else {
                    if (ufmProblemSummary) ufmProblemSummary.innerHTML = "(오늘 풀이 내역 조회 불가)";
                }
            } catch (e) {
                if (ufmProblemSummary) ufmProblemSummary.innerHTML = "(오류 발생)";
            }
        },

        renderUfmProblemSummary: function() {
            const ufmProblemSummary = document.getElementById("ufm-problem-summary");
            if (!ufmProblemSummary) return;

            let summaryText = "";
            const solved = this.currentUfmProblems.filter(p => p.status === "solved").map(p => p.title);
            const wrong = this.currentUfmProblems.filter(p => p.status === "wrong").map(p => p.title);
            const basket = window.basket || [];
            const basketTitles = basket.map(p => p.title);

            if (solved.length > 0) summaryText += `🟢 오늘 완료 (${solved.length}개): ${solved.join(", ")}<br>`;
            if (wrong.length > 0) summaryText += `🔴 오답 (${wrong.length}개): ${wrong.join(", ")}<br>`;
            if (basketTitles.length > 0) summaryText += `🛒 바구니 지정 숙제 (${basketTitles.length}개): ${basketTitles.join(", ")}`;
            
            if (!summaryText) {
                summaryText = "지정된 문항 또는 풀이 이력 없음 (오프라인 수업 선택 가능)";
            }
            ufmProblemSummary.innerHTML = summaryText;
        },

        copyUfmPrompt: async function() {
            const ufmPresetSelect = document.getElementById("ufm-preset-select");
            const ufmConceptText = document.getElementById("ufm-concept-text");
            const ufmTeacherMemo = document.getElementById("ufm-teacher-memo");

            let summary = "";
            const selectedPresetId = ufmPresetSelect ? ufmPresetSelect.value : "doingcoding";
            const conceptDesc = ufmConceptText ? ufmConceptText.textContent.trim() : "";

            if (selectedPresetId !== "doingcoding") {
                const preset = typeof OFFLINE_PRESETS !== "undefined" ? OFFLINE_PRESETS.find(p => p.id === selectedPresetId) : null;
                summary = `  * 오프라인 수업 진행: ${preset ? preset.name : "교재 수업"} (${conceptDesc})\n`;
            } else {
                const solved = this.currentUfmProblems.filter(p => p.status === "solved").map(p => p.title);
                const basket = window.basket || [];
                const basketTitles = basket.map(p => p.title);
                if (basketTitles.length > 0) {
                    summary += `  * 숙제 지정 문항 (${basketTitles.length}개): ${basketTitles.join(", ")}\n`;
                }
                if (solved.length > 0) {
                    summary += `  * 오늘 학습/복습 문항 (${solved.length}개): ${solved.join(", ")}\n`;
                }
                if (!summary) summary = "  * (신규 숙제 및 지정 문항 없음)\n";
            }

            const memoVal = ufmTeacherMemo ? ufmTeacherMemo.value.trim() : "";
            const finalMemo = memoVal || "오늘 수업에 차분하고 성실하게 임함 (특이사항 없음)";
            const fullPrompt = typeof getAiPrompt === "function" ? getAiPrompt(summary, finalMemo) : `[정보]\n- 숙제: ${summary}\n- 메모: ${finalMemo}`;

            try {
                await navigator.clipboard.writeText(fullPrompt);
                if (typeof showToast === "function") {
                    showToast("📋 AI 프롬프트가 클립보드에 복사되었습니다!\nChatGPT나 Claude에 붙여넣으세요.");
                }
            } catch (e) {
                if (typeof showToast === "function") {
                    showToast("프롬프트 복사에 실패했습니다.", true);
                }
            }
        },

        copyParentMsg: async function() {
            const ufmAiComment = document.getElementById("ufm-ai-comment");
            const comment = ufmAiComment ? ufmAiComment.value.trim() : "";
            if (!comment) {
                if (typeof showToast === "function") {
                    showToast("⚠️ 먼저 외부 AI 답변을 붙여넣어 주세요!", true);
                }
                return;
            }
            const text = this.buildFinalMessage(true);
            try {
                await navigator.clipboard.writeText(text);
                if (typeof showToast === "function") {
                    showToast("📱 학부모용 카톡 메시지가 복사되었습니다!");
                }
            } catch (e) {
                if (typeof showToast === "function") showToast("복사 실패", true);
            }
        },

        copyStudentMsg: async function() {
            const text = this.buildFinalMessage(false);
            try {
                await navigator.clipboard.writeText(text);
                if (typeof showToast === "function") {
                    showToast("🎒 학생용 숙제 안내 메시지가 복사되었습니다!");
                }
            } catch (e) {
                if (typeof showToast === "function") showToast("복사 실패", true);
            }
        },

        copyExcelLine: async function() {
            const ufmAiComment = document.getElementById("ufm-ai-comment");
            const ufmTeacherMemo = document.getElementById("ufm-teacher-memo");
            const basket = window.basket || [];

            const todayStr = new Date().toISOString().split("T")[0];
            const comment = (ufmAiComment ? ufmAiComment.value.trim() : "") || (ufmTeacherMemo ? ufmTeacherMemo.value.trim() : "") || "성실히 임함";
            const lastProblem = basket.length > 0 ? basket[basket.length - 1].title : (this.currentUfmProblems.length > 0 ? this.currentUfmProblems[this.currentUfmProblems.length - 1].title : "교재/이론");
            const countVal = "1";

            const tabLine = `${todayStr}\t${countVal}\t${lastProblem}\t${comment}`;
            try {
                await navigator.clipboard.writeText(tabLine);
                if (typeof showToast === "function") {
                    showToast("📊 엑셀 1줄(날짜/회차/문제/비고) 복사 완료!\n엑셀 셀에 Ctrl+V 하세요.");
                }
            } catch (e) {
                if (typeof showToast === "function") showToast("엑셀 복사 실패", true);
            }
        },

        saveUfmFinal: async function() {
            const ufmAiComment = document.getElementById("ufm-ai-comment");
            const ufmModal = document.getElementById("unified-feedback-modal");

            const comment = ufmAiComment ? ufmAiComment.value.trim() : "";
            const displayId = this.currentUfmStudent ? this.currentUfmStudent.display_id : "";
            const finalMsg = this.buildFinalMessage(true);
            const basket = window.basket || [];

            try {
                const res = await fetch(`/api/workspace/save_homework_log`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        display_id: displayId,
                        problems: basket,
                        message: finalMsg,
                        comment: comment
                    })
                });
                if (!res.ok) throw new Error("Save failed");
                
                if (typeof showToast === "function") {
                    showToast(`💾 [${this.currentUfmStudent.name}] 피드백 및 숙제 로그 저장 완료!`);
                }
                ufmModal?.classList.remove("show");
                if (typeof window.WorkspaceBasket !== "undefined") {
                    window.WorkspaceBasket.clearBasket();
                }
            } catch (e) {
                if (typeof showToast === "function") showToast("저장에 실패했습니다.", true);
            }
        },

        buildFinalMessage: function(includeComment = true) {
            const ufmAiComment = document.getElementById("ufm-ai-comment");
            const sName = this.currentUfmStudent ? this.currentUfmStudent.name : "학생";
            const sDisplayId = this.currentUfmStudent ? this.currentUfmStudent.display_id : "";
            const todayStr = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" });
            const basket = window.basket || [];

            let lines = [];
            lines.push("안녕하세요 두잉창의코딩학원입니다. 😊");
            lines.push(`📘 ${sName} 학생 수업 피드백`);
            lines.push(`🗓 수업일: ${todayStr}`);
            if (sDisplayId) lines.push(`👤 풀이 계정: ${sDisplayId}`);

            const basketTitles = basket.map(p => p.title);
            if (basketTitles.length > 0) {
                lines.push(`⏰ 다음 마감 숙제: ${basketTitles.join(", ")}`);
            }

            if (includeComment && ufmAiComment) {
                const comment = ufmAiComment.value.trim();
                if (comment) {
                    lines.push(`📝 코멘트: ${comment}`);
                }
            }

            return lines.join("\n");
        }
    };
})(window);
