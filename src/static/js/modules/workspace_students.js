// workspace_students.js - 수강생 보드 & 요일 슬롯 관리 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceStudents = {
        students: [],
        allSlots: [],
        selectedStudentId: null,
        currentWeekday: "all",

        init: function() {
            this.bindEvents();
        },

        bindEvents: function() {
            const weekdayTabs = document.querySelectorAll(".tab-btn");
            weekdayTabs.forEach(tab => {
                tab.addEventListener("click", (e) => {
                    weekdayTabs.forEach(t => t.classList.remove("active"));
                    e.target.classList.add("active");
                    this.currentWeekday = e.target.getAttribute("data-weekday");
                    this.loadStudents(this.currentWeekday);
                });
            });
        },

        loadStudents: async function(weekday = "all") {
            try {
                const res = await fetch(`/api/workspace/schedule_students?weekday=${weekday}`);
                if (!res.ok) throw new Error("Failed to load students");
                const data = await res.json();
                this.students = data.students || [];
                this.allSlots = data.all_slots || [];
                
                this.updateSlotDropdown();
                this.renderStudents();
            } catch (e) {
                if (typeof showToast === "function") {
                    showToast("수강생을 불러오는데 실패했습니다.", true);
                }
                console.error(e);
            }
        },

        updateSlotDropdown: function() {
            const regSlotSelect = document.getElementById("reg-slot");
            if (!regSlotSelect) return;
            regSlotSelect.innerHTML = "<option value=''>슬롯을 선택하세요</option>";
            const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
            this.allSlots.forEach(slot => {
                let w = parseInt(slot.weekday);
                let wLabel = (w >= 0 && w <= 6) ? `${weekdays[w]}요일` : "기타/일정불확실";
                const opt = document.createElement("option");
                opt.value = slot.id;
                opt.textContent = `[${wLabel}] ${slot.label}`;
                regSlotSelect.appendChild(opt);
            });
        },

        renderStudents: function() {
            const gridContainer = document.getElementById("student-grid-container");
            if (!gridContainer) return;
            gridContainer.innerHTML = "";
            if (this.students.length === 0) {
                gridContainer.innerHTML = "<div class='problem-empty-state'>선택한 요일에 해당하는 학생이 없습니다.</div>";
                return;
            }

            this.students.forEach(student => {
                const card = document.createElement("div");
                const isSelected = this.selectedStudentId === student.display_id;
                card.className = `student-card ${isSelected ? 'selected' : ''}`;
                card.onclick = () => this.selectStudent(student.display_id);

                let badgesHTML = "";
                if (student.slot_label) {
                    badgesHTML += `<span class="student-accounts" style="background: rgba(52,199,89,0.1); color: var(--success-color);">${student.slot_label}</span>`;
                }
                if (student.accounts && student.accounts.length > 0) {
                    student.accounts.forEach(acc => {
                        let icon = "🔗";
                        let typeStr = "";
                        let uname = "";
                        if (typeof acc === "object" && acc !== null) {
                            uname = acc.username || "";
                            if (acc.type === "academy") { icon = "🏫"; typeStr = "학원: "; }
                            else if (acc.type === "scratch") { icon = "🧩"; typeStr = "스크래치: "; }
                            else if (acc.type === "goorm") { icon = "☁️"; typeStr = "구름: "; }
                            else { icon = "📘"; typeStr = "기타: "; }
                        } else {
                            uname = String(acc);
                            icon = "🏫"; typeStr = "학원: ";
                        }
                        if (uname) {
                            badgesHTML += `<span class="student-accounts" style="background: rgba(0,113,227,0.08); color: var(--accent-color);" title="${typeStr}${uname}">${icon} ${uname}</span>`;
                        }
                    });
                }
                if (student.note) {
                    badgesHTML += `<span class="student-accounts" style="background: rgba(255,149,0,0.1); color: var(--warning-color);">${student.note}</span>`;
                }

                const memoText = (student.display_id && student.display_id !== student.name) ? ` <span style="font-size:0.75rem; color:#86868b; font-weight:500;">(📝 ${student.display_id})</span>` : "";

                card.innerHTML = `
                    <div class="student-header" style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div class="student-info" style="flex:1; min-width:0;">
                            <span class="student-name" style="font-size:0.98rem; font-weight:700;">${student.name}</span>
                            ${memoText}
                            ${isSelected ? '<span style="font-size:0.7rem; background:var(--accent-color); color:white; padding:1px 5px; border-radius:4px; margin-left:4px; font-weight:600;">✔ 선택됨</span>' : ''}
                        </div>
                        <button class="btn-small btn-ghost" style="padding:2px 5px; font-size:0.85rem; color:#86868b;" onclick="openAccountManageModal('${student.display_id}', event)" title="계정 연동 & 정보 관리">⚙️</button>
                    </div>
                    <div style="display:flex; gap:4px; flex-wrap:wrap; margin-top:4px;">${badgesHTML}</div>
                    <div style="margin-top:6px;">
                        <button class="btn-small btn-primary" style="width:100%; padding:6px; font-size:0.8rem; font-weight:600; box-shadow:0 1px 3px rgba(0,113,227,0.15);" onclick="generateFeedback('${student.display_id}', event)">✨ AI 피드백 & 숙제 컨트롤</button>
                    </div>
                `;
                gridContainer.appendChild(card);
            });
        },

        selectStudent: function(displayId) {
            this.selectedStudentId = displayId;
            this.renderStudents();

            if (typeof window.onStudentSelected === "function") {
                window.onStudentSelected(displayId);
            }
        }
    };
})(window);
