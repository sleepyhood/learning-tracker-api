// workspace_students.js - 수강생 보드 & 요일 슬롯 관리 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceStudents = {
        students: [],
        allSlots: [],
        selectedStudentId: null,
        currentWeekday: "all",
        searchQuery: "",
        statusFilter: "active",
        sortOrder: "name",

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

            const searchInput = document.getElementById("student-search-input");
            if (searchInput) {
                searchInput.addEventListener("input", (e) => {
                    this.searchQuery = (e.target.value || "").toLowerCase().trim();
                    this.renderStudents();
                });
            }

            const statusFilterSelect = document.getElementById("student-status-filter");
            if (statusFilterSelect) {
                statusFilterSelect.addEventListener("change", (e) => {
                    this.statusFilter = e.target.value;
                    this.renderStudents();
                });
            }

            const sortSelect = document.getElementById("student-sort-select");
            if (sortSelect) {
                sortSelect.addEventListener("change", (e) => {
                    this.sortOrder = e.target.value;
                    this.renderStudents();
                });
            }
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
            regSlotSelect.innerHTML = "<option value=''>슬롯을 선택하세요 (선택)</option>";
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

            // Filter by status
            let list = [...this.students];
            if (this.statusFilter !== "all") {
                list = list.filter(st => (st.status || "active") === this.statusFilter);
            }

            // Filter by search query
            if (this.searchQuery) {
                const q = this.searchQuery;
                list = list.filter(st => {
                    const nameMatch = (st.name || "").toLowerCase().includes(q);
                    const noteMatch = (st.note || "").toLowerCase().includes(q);
                    const displayMatch = (st.display_id || "").toLowerCase().includes(q);
                    const sbjMatch = (st.subjects || []).some(s => String(s).toLowerCase().includes(q));
                    const accMatch = (st.accounts || []).some(a => (typeof a === "object" ? a.username || "" : String(a)).toLowerCase().includes(q));
                    return nameMatch || noteMatch || displayMatch || sbjMatch || accMatch;
                });
            }

            // Sort list
            if (this.sortOrder === "name") {
                list.sort((a, b) => (a.name || "").localeCompare(b.name || "", "ko"));
            } else if (this.sortOrder === "wrong") {
                list.sort((a, b) => (b.wrong_count || 0) - (a.wrong_count || 0));
            } else if (this.sortOrder === "hw") {
                list.sort((a, b) => (b.homework_count || 0) - (a.homework_count || 0));
            }

            if (list.length === 0) {
                gridContainer.innerHTML = "<div class='problem-empty-state'>조건에 해당하는 학생이 없습니다.</div>";
                return;
            }

            const weekdayLabels = ["월", "화", "수", "목", "금", "토", "일"];

            list.forEach(student => {
                const card = document.createElement("div");
                const studentIdKey = student.display_id || student.user_uuid;
                const isSelected = (this.selectedStudentId === studentIdKey);
                card.className = `student-card ${isSelected ? 'selected' : ''}`;
                card.onclick = () => this.selectStudent(studentIdKey);

                let badgesHTML = "";

                // 1. Status Chip (재원 / 휴원 / 퇴원)
                const status = student.status || "active";
                let statusTagHTML = "";
                if (status === "active") {
                    statusTagHTML = '<span style="font-size:0.7rem; font-weight:700; background:rgba(52,199,89,0.12); color:#15803d; border:1px solid rgba(52,199,89,0.3); padding:1px 6px; border-radius:10px; margin-left:4px;">🟢 재원</span>';
                } else if (status === "paused") {
                    statusTagHTML = '<span style="font-size:0.7rem; font-weight:700; background:rgba(245,158,11,0.12); color:#b45309; border:1px solid rgba(245,158,11,0.3); padding:1px 6px; border-radius:10px; margin-left:4px;">🟡 휴원</span>';
                } else if (status === "inactive") {
                    statusTagHTML = '<span style="font-size:0.7rem; font-weight:700; background:rgba(156,163,175,0.15); color:#4b5563; border:1px solid rgba(156,163,175,0.3); padding:1px 6px; border-radius:10px; margin-left:4px;">⚪ 퇴원</span>';
                }

                // 2. Status Badge (실시간 학습 현황 배지)
                const solvedCnt = student.solved_count || 0;
                const wrongCnt = student.wrong_count || 0;
                const hwCnt = student.homework_count || 0;
                
                let statusChipHTML = `
                    <div style="display:flex; gap:4px; font-size:0.75rem; font-weight:700; margin-bottom:4px; flex-wrap:wrap;">
                        <span style="background:rgba(52,199,89,0.12); color:#15803d; border:1px solid rgba(52,199,89,0.3); padding:1px 6px; border-radius:12px;">🟢 완료 ${solvedCnt}</span>
                        ${wrongCnt > 0 ? `<span style="background:rgba(239,68,68,0.12); color:#b91c1c; border:1px solid rgba(239,68,68,0.3); padding:1px 6px; border-radius:12px;">🔴 오답 ${wrongCnt}</span>` : ''}
                        ${hwCnt > 0 ? `<span style="background:rgba(14,165,233,0.12); color:#0369a1; border:1px solid rgba(14,165,233,0.3); padding:1px 6px; border-radius:12px;">🛒 숙제 ${hwCnt}</span>` : ''}
                    </div>
                `;

                // 3. Weekdays Chip
                if (student.weekdays && student.weekdays.length > 0) {
                    const wStr = student.weekdays.map(w => weekdayLabels[w] || "").filter(Boolean).join(",");
                    if (wStr) {
                        badgesHTML += `<span class="student-accounts" style="background: rgba(147,51,234,0.1); color: #7e22ce;" title="등원 요일">📅 ${wStr}</span>`;
                    }
                } else if (student.slot_label) {
                    badgesHTML += `<span class="student-accounts" style="background: rgba(52,199,89,0.1); color: var(--success-color);">${student.slot_label}</span>`;
                }

                // 4. Subjects Tag
                if (student.subjects && student.subjects.length > 0) {
                    student.subjects.forEach(sbj => {
                        badgesHTML += `<span class="student-accounts" style="background: rgba(245,158,11,0.12); color: #b45309;" title="수강 과목">📘 ${sbj}</span>`;
                    });
                }

                // 5. Accounts Badge
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

                // Duplicate Tag
                const dupTagHTML = student.dup_tag ? ` <span style="font-size:0.73rem; font-weight:700; color:#e11d48; background:#ffe4e6; border:1px solid #fecdd3; padding:1px 5px; border-radius:4px; margin-left:2px;">${student.dup_tag}</span>` : "";
                const memoText = (student.display_id && student.display_id !== student.name) ? ` <span style="font-size:0.75rem; color:#86868b; font-weight:500;">(📝 ${student.display_id})</span>` : "";

                card.innerHTML = `
                    ${statusChipHTML}
                    <div class="student-header" style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div class="student-info" style="flex:1; min-width:0;">
                            <span class="student-name" style="font-size:0.98rem; font-weight:700;">${student.name}</span>
                            ${statusTagHTML}
                            ${dupTagHTML}
                            ${memoText}
                            ${isSelected ? '<span style="font-size:0.7rem; background:var(--accent-color); color:white; padding:1px 5px; border-radius:4px; margin-left:4px; font-weight:600;">✔ 선택됨</span>' : ''}
                        </div>
                        <button class="btn-small btn-ghost" style="padding:2px 5px; font-size:0.85rem; color:#86868b;" onclick="openAccountManageModal('${studentIdKey}', event)" title="계정 연동 & 정보 관리">⚙️</button>
                    </div>
                    <div style="display:flex; gap:4px; flex-wrap:wrap; margin-top:4px;">${badgesHTML}</div>
                    <div style="margin-top:6px;">
                        <button class="btn-small btn-primary" style="width:100%; padding:6px; font-size:0.8rem; font-weight:600; box-shadow:0 1px 3px rgba(0,113,227,0.15);" onclick="generateFeedback('${studentIdKey}', event)">✨ AI 피드백 & 숙제 컨트롤</button>
                    </div>
                `;
                gridContainer.appendChild(card);
            });
        },

        selectStudent: function(studentKey) {
            this.selectedStudentId = studentKey;
            this.renderStudents();

            if (typeof window.onStudentSelected === "function") {
                window.onStudentSelected(studentKey);
            }
        }
    };
})(window);

