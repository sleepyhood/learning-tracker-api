document.addEventListener("DOMContentLoaded", () => {
    // 1. Initial State
    let students = [];
    let basket = [];
    let allSlots = [];
    let selectedStudentId = null;
    let currentWeekday = "all";

    // Elements
    const gridContainer = document.getElementById("student-grid-container");
    const problemListContainer = document.getElementById("problem-list-container");
    const basketCount = document.getElementById("basket-count");
    const basketItemsContainer = document.getElementById("basket-items");
    const weekdayTabs = document.querySelectorAll(".tab-btn");

    // Modal Elements
    const modal = document.getElementById("register-modal");
    const btnAddStudent = document.getElementById("btn-add-student-modal");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const btnSubmitRegister = document.getElementById("btn-submit-register");
    const regSlotSelect = document.getElementById("reg-slot");

    // 2. Tab Events
    weekdayTabs.forEach(tab => {
        tab.addEventListener("click", (e) => {
            weekdayTabs.forEach(t => t.classList.remove("active"));
            e.target.classList.add("active");
            currentWeekday = e.target.getAttribute("data-weekday");
            loadStudents(currentWeekday);
        });
    });

    // 3. Load Students & Slots
    async function loadStudents(weekday = "all") {
        try {
            const res = await fetch(`/api/workspace/schedule_students?weekday=${weekday}`);
            if (!res.ok) throw new Error("Failed to load students");
            const data = await res.json();
            students = data.students || [];
            allSlots = data.all_slots || [];
            
            updateSlotDropdown();
            renderStudents();
        } catch (e) {
            showToast("수강생을 불러오는데 실패했습니다.", true);
            console.error(e);
        }
    }

    function updateSlotDropdown() {
        regSlotSelect.innerHTML = "<option value=''>슬롯을 선택하세요</option>";
        const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
        allSlots.forEach(slot => {
            let w = parseInt(slot.weekday);
            let wLabel = (w >= 0 && w <= 6) ? `${weekdays[w]}요일` : "기타/일정불확실";
            const opt = document.createElement("option");
            opt.value = slot.id;
            opt.textContent = `[${wLabel}] ${slot.label}`;
            regSlotSelect.appendChild(opt);
        });
    }

    // 4. Render Students
    function renderStudents() {
        gridContainer.innerHTML = "";
        if (students.length === 0) {
            gridContainer.innerHTML = "<div class='problem-empty-state'>선택한 요일에 해당하는 학생이 없습니다.</div>";
            return;
        }

        students.forEach(student => {
            const card = document.createElement("div");
            card.className = `student-card ${selectedStudentId === student.display_id ? 'selected' : ''}`;
            card.onclick = () => selectStudent(student.display_id);

            let badgesHTML = "";
            if (student.slot_label) {
                badgesHTML += `<span class="student-accounts" style="background: rgba(52,199,89,0.1); color: var(--success-color);">${student.slot_label}</span>`;
            }
            if (student.note) {
                badgesHTML += `<span class="student-accounts" style="background: rgba(255,149,0,0.1); color: var(--warning-color);">${student.note}</span>`;
            }

            card.innerHTML = `
                <div class="student-header">
                    <div class="student-info">
                        <span class="student-name">${student.name} <span class="student-display-id">(${student.display_id})</span></span>
                        <div style="display:flex; gap: 4px; margin-top: 4px;">${badgesHTML}</div>
                    </div>
                </div>
                <div class="student-actions" style="margin-top: 12px;">
                    <button class="btn-small btn-primary" onclick="generateFeedback('${student.display_id}', event)">✨ AI 피드백 생성</button>
                    <button class="btn-small btn-secondary" onclick="assignBasketToStudent('${student.display_id}', event)">➕ 장바구니 할당</button>
                </div>
            `;
            gridContainer.appendChild(card);
        });
    }

    // 5. Select Student
    window.selectStudent = (displayId) => {
        selectedStudentId = displayId;
        renderStudents();
        loadStudentProblems(displayId);
    };

    // 6. Load Student Problems
    async function loadStudentProblems(displayId) {
        problemListContainer.innerHTML = "<div class='problem-empty-state'>로딩 중...</div>";
        try {
            const res = await fetch(`/api/workspace/student_problems/${displayId}`);
            if (!res.ok) throw new Error("Failed to load problems");
            const data = await res.json();
            
            problemListContainer.innerHTML = "";
            const problems = data.problems || [];
            
            if (problems.length === 0) {
                problemListContainer.innerHTML = "<div class='problem-empty-state'>오늘의 숙제/풀이 내역이 없습니다.</div>";
                return;
            }

            problems.forEach(p => {
                const item = document.createElement("div");
                item.className = "problem-item";
                item.onclick = () => addToBasket(p);
                
                let icon = "⚪";
                if (p.status === "solved") icon = "🟢";
                else if (p.status === "wrong") icon = "🔴";
                else if (p.status === "partial") icon = "🟡";

                item.innerHTML = `
                    <span class="problem-status-icon">${icon}</span>
                    <span class="problem-title">[${p.legacy_code}] ${p.title}</span>
                    <button class="btn-small btn-ghost" onclick="event.stopPropagation(); addToBasket(${JSON.stringify(p).replace(/"/g, '&quot;')})">담기</button>
                `;
                problemListContainer.appendChild(item);
            });

        } catch (e) {
            showToast("문제 목록을 불러오는데 실패했습니다.", true);
        }
    }

    // 7. Basket Logic
    window.addToBasket = (problem) => {
        if (!basket.find(p => p.legacy_code === problem.legacy_code)) {
            basket.push(problem);
            renderBasket();
            showToast("바구니에 담았습니다.");
        }
    };

    document.getElementById("btn-clear-basket").onclick = () => {
        basket = [];
        renderBasket();
    };

    function renderBasket() {
        basketCount.innerText = basket.length;
        basketItemsContainer.innerHTML = "";
        basket.forEach((p, index) => {
            const li = document.createElement("li");
            li.className = "basket-item";
            li.innerHTML = `
                <span>${p.legacy_code} ${p.title}</span>
                <button class="btn-small btn-ghost" onclick="removeFromBasket(${index})">❌</button>
            `;
            basketItemsContainer.appendChild(li);
        });
    }

    window.removeFromBasket = (index) => {
        basket.splice(index, 1);
        renderBasket();
    };

    // 8. AI Prompt Generation & Assignment
    window.generateFeedback = async (displayId, event) => {
        event.stopPropagation();
        showToast("프롬프트 생성 중...");
        try {
            const res = await fetch('/api/workspace/generate_ai_prompt', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ display_id: displayId })
            });
            if (!res.ok) throw new Error("Generate failed");
            const data = await res.json();
            
            await navigator.clipboard.writeText(data.prompt);
            showToast("AI 피드백 프롬프트가 클립보드에 복사되었습니다!");
        } catch(e) {
            showToast("프롬프트 생성에 실패했습니다.", true);
        }
    };

    window.assignBasketToStudent = async (displayId, event) => {
        event.stopPropagation();
        if (basket.length === 0) {
            showToast("바구니가 비어 있습니다.", true);
            return;
        }

        try {
            const res = await fetch(`/api/workspace/save_homework_log`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    display_id: displayId,
                    problems: basket
                })
            });
            if (!res.ok) throw new Error("Save failed");
            
            showToast(`[${displayId}] 숙제가 할당되었습니다.`);
            basket = []; 
            renderBasket();
            loadStudentProblems(displayId); // Refresh problem list
        } catch (e) {
            showToast("숙제 할당에 실패했습니다.", true);
        }
    };

    // 9. Manual Registration Modal
    btnAddStudent.addEventListener("click", () => {
        modal.classList.add("show");
    });

    btnCloseModal.addEventListener("click", () => {
        modal.classList.remove("show");
    });

    btnSubmitRegister.addEventListener("click", async () => {
        const name = document.getElementById("reg-name").value;
        const birth = document.getElementById("reg-birth").value;
        const slot = regSlotSelect.value;

        if (!name || !slot) {
            showToast("이름과 요일 슬롯을 입력해주세요.", true);
            return;
        }

        try {
            const res = await fetch('/api/workspace/register_student', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: name,
                    birth_md: birth,
                    slot_id: slot
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Register failed");

            showToast(`${data.display_id} 등록 완료!`);
            modal.classList.remove("show");
            
            // Clear inputs
            document.getElementById("reg-name").value = "";
            document.getElementById("reg-birth").value = "";
            
            // Reload
            loadStudents(currentWeekday);
        } catch (e) {
            showToast(e.message, true);
        }
    });

    // Toast
    function showToast(message, isError = false) {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.style.background = isError ? "var(--danger-color)" : "rgba(0,0,0,0.8)";
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 3000);
    }

    // === UFM (Unified Feedback Modal) Logic ===
    const ufmModal = document.getElementById("unified-feedback-modal");
    const ufmPresetSelect = document.getElementById("ufm-preset-select");
    const ufmConceptText = document.getElementById("ufm-concept-text");
    const ufmProblemSummary = document.getElementById("ufm-problem-summary");
    const ufmTeacherMemo = document.getElementById("ufm-teacher-memo");
    const ufmAiComment = document.getElementById("ufm-ai-comment");
    const ufmStudentName = document.getElementById("ufm-student-name");

    let currentUfmStudent = null;
    let currentUfmProblems = [];

    // Populate preset dropdown
    if (typeof OFFLINE_PRESETS !== "undefined" && ufmPresetSelect) {
        ufmPresetSelect.innerHTML = "";
        OFFLINE_PRESETS.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.id;
            opt.textContent = p.name;
            ufmPresetSelect.appendChild(opt);
        });
    }

    // UFM Close
    document.getElementById("btn-close-ufm")?.addEventListener("click", () => {
        ufmModal.classList.remove("show");
    });

    // Preset select change listener
    ufmPresetSelect?.addEventListener("change", () => {
        updateUfmConceptView();
    });

    function updateUfmConceptView() {
        const selectedId = ufmPresetSelect.value;
        const preset = typeof OFFLINE_PRESETS !== "undefined" ? OFFLINE_PRESETS.find(p => p.id === selectedId) : null;
        if (selectedId === "doingcoding") {
            let autoConcepts = [];
            if (typeof extractConceptDescription === "function") {
                currentUfmProblems.forEach(p => {
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
    }

    // Override window.generateFeedback to open UFM Modal
    window.generateFeedback = async (displayId, event) => {
        if (event) event.stopPropagation();
        const student = students.find(s => s.display_id === displayId);
        currentUfmStudent = student || { display_id: displayId, name: displayId };
        ufmStudentName.textContent = currentUfmStudent.name;

        ufmTeacherMemo.value = "";
        ufmAiComment.value = "";
        ufmProblemSummary.innerHTML = "불러오는 중...";
        if (ufmPresetSelect) ufmPresetSelect.value = "doingcoding";

        ufmModal.classList.add("show");

        try {
            const res = await fetch(`/api/workspace/student_problems/${displayId}`);
            if (res.ok) {
                const data = await res.json();
                currentUfmProblems = data.problems || [];
                renderUfmProblemSummary();
                updateUfmConceptView();
            } else {
                ufmProblemSummary.innerHTML = "(오늘 풀이 내역 조회 불가)";
            }
        } catch (e) {
            ufmProblemSummary.innerHTML = "(오류 발생)";
        }
    };

    function renderUfmProblemSummary() {
        let summaryText = "";
        const solved = currentUfmProblems.filter(p => p.status === "solved").map(p => p.title);
        const wrong = currentUfmProblems.filter(p => p.status === "wrong").map(p => p.title);
        const basketTitles = basket.map(p => p.title);

        if (solved.length > 0) summaryText += `🟢 오늘 완료 (${solved.length}개): ${solved.join(", ")}<br>`;
        if (wrong.length > 0) summaryText += `🔴 오답 (${wrong.length}개): ${wrong.join(", ")}<br>`;
        if (basketTitles.length > 0) summaryText += `🛒 바구니 지정 숙제 (${basketTitles.length}개): ${basketTitles.join(", ")}`;
        
        if (!summaryText) {
            summaryText = "지정된 문항 또는 풀이 이력 없음 (오프라인 수업 선택 가능)";
        }
        ufmProblemSummary.innerHTML = summaryText;
    }

    // Copy Prompt Button
    document.getElementById("btn-copy-ufm-prompt")?.addEventListener("click", async () => {
        let summary = "";
        const selectedPresetId = ufmPresetSelect.value;
        const conceptDesc = ufmConceptText.textContent.trim();

        if (selectedPresetId !== "doingcoding") {
            const preset = OFFLINE_PRESETS.find(p => p.id === selectedPresetId);
            summary = `  * 오프라인 수업 진행: ${preset ? preset.name : "교재 수업"} (${conceptDesc})\n`;
        } else {
            const solved = currentUfmProblems.filter(p => p.status === "solved").map(p => p.title);
            const basketTitles = basket.map(p => p.title);
            if (basketTitles.length > 0) {
                summary += `  * 숙제 지정 문항 (${basketTitles.length}개): ${basketTitles.join(", ")}\n`;
            }
            if (solved.length > 0) {
                summary += `  * 오늘 학습/복습 문항 (${solved.length}개): ${solved.join(", ")}\n`;
            }
            if (!summary) summary = "  * (신규 숙제 및 지정 문항 없음)\n";
        }

        const memoVal = ufmTeacherMemo.value.trim();
        const finalMemo = memoVal || "오늘 수업에 차분하고 성실하게 임함 (특이사항 없음)";
        const fullPrompt = typeof getAiPrompt === "function" ? getAiPrompt(summary, finalMemo) : `[정보]\n- 숙제: ${summary}\n- 메모: ${finalMemo}`;

        try {
            await navigator.clipboard.writeText(fullPrompt);
            showToast("📋 AI 프롬프트가 클립보드에 복사되었습니다!\nChatGPT나 Claude에 붙여넣으세요.");
        } catch (e) {
            showToast("프롬프트 복사에 실패했습니다.", true);
        }
    });

    // Copy Parent Message (b)
    document.getElementById("btn-copy-parent-msg")?.addEventListener("click", async () => {
        const comment = ufmAiComment.value.trim();
        if (!comment) {
            showToast("⚠️ 먼저 외부 AI 답변을 붙여넣어 주세요!", true);
            return;
        }
        const text = buildFinalMessage(true);
        try {
            await navigator.clipboard.writeText(text);
            showToast("📱 학부모용 카톡 메시지가 복사되었습니다!");
        } catch (e) {
            showToast("복사 실패", true);
        }
    });

    // Copy Student Message (c) - Strips AI comment
    document.getElementById("btn-copy-student-msg")?.addEventListener("click", async () => {
        const text = buildFinalMessage(false);
        try {
            await navigator.clipboard.writeText(text);
            showToast("🎒 학생용 숙제 안내 메시지가 복사되었습니다!");
        } catch (e) {
            showToast("복사 실패", true);
        }
    });

    // Copy Excel Line (Tab Separated)
    document.getElementById("btn-copy-excel-line")?.addEventListener("click", async () => {
        const todayStr = new Date().toISOString().split("T")[0];
        const comment = ufmAiComment.value.trim() || ufmTeacherMemo.value.trim() || "성실히 임함";
        const lastProblem = basket.length > 0 ? basket[basket.length - 1].title : (currentUfmProblems.length > 0 ? currentUfmProblems[currentUfmProblems.length - 1].title : "교재/이론");
        const countVal = "1";

        const tabLine = `${todayStr}\t${countVal}\t${lastProblem}\t${comment}`;
        try {
            await navigator.clipboard.writeText(tabLine);
            showToast("📊 엑셀 1줄(날짜/회차/문제/비고) 복사 완료!\n엑셀 셀에 Ctrl+V 하세요.");
        } catch (e) {
            showToast("엑셀 복사 실패", true);
        }
    });

    // Final Save Button
    document.getElementById("btn-save-ufm-final")?.addEventListener("click", async () => {
        const comment = ufmAiComment.value.trim();
        const displayId = currentUfmStudent ? currentUfmStudent.display_id : "";
        const finalMsg = buildFinalMessage(true);

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
            
            showToast(`💾 [${currentUfmStudent.name}] 피드백 및 숙제 로그 저장 완료!`);
            ufmModal.classList.remove("show");
            basket = [];
            renderBasket();
        } catch (e) {
            showToast("저장에 실패했습니다.", true);
        }
    });

    function buildFinalMessage(includeComment = true) {
        const sName = currentUfmStudent ? currentUfmStudent.name : "학생";
        const sDisplayId = currentUfmStudent ? currentUfmStudent.display_id : "";
        const todayStr = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" });

        let lines = [];
        lines.push("안녕하세요 두잉창의코딩학원입니다. 😊");
        lines.push(`📘 ${sName} 학생 수업 피드백`);
        lines.push(`🗓 수업일: ${todayStr}`);
        if (sDisplayId) lines.push(`👤 풀이 계정: ${sDisplayId}`);

        const basketTitles = basket.map(p => p.title);
        if (basketTitles.length > 0) {
            lines.push(`⏰ 다음 마감 숙제: ${basketTitles.join(", ")}`);
        }

        if (includeComment) {
            const comment = ufmAiComment.value.trim();
            if (comment) {
                lines.push(`📝 코멘트: ${comment}`);
            }
        }

        return lines.join("\n");
    }

    // Init
    loadStudents(currentWeekday);
});
