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

    // Init
    loadStudents(currentWeekday);
});
