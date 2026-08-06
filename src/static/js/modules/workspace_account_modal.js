// workspace_account_modal.js - 도메인 계정 ⚙️ & 비고 메모 관리 모달 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceAccountModal = {
        currentEditingUserUuid: null,

        init: function() {
            this.bindEvents();
        },

        bindEvents: function() {
            const btnAddAccountInput = document.getElementById("btn-add-account-input");
            const btnSaveAmmStudent = document.getElementById("btn-save-amm-student");
            const btnDeleteStudent = document.getElementById("btn-delete-student");
            const btnCloseAmm = document.getElementById("btn-close-amm");
            const btnCloseAmmCancel = document.getElementById("btn-close-amm-cancel");
            const ammModal = document.getElementById("account-manage-modal");

            btnAddAccountInput?.addEventListener("click", () => {
                this.renderAccountInputRow({});
            });

            const closeAmmModal = () => ammModal?.classList.remove("show");
            btnCloseAmm?.addEventListener("click", closeAmmModal);
            btnCloseAmmCancel?.addEventListener("click", closeAmmModal);

            btnSaveAmmStudent?.addEventListener("click", async () => {
                if (!this.currentEditingUserUuid) return;

                const ammNameInput = document.getElementById("amm-name");
                const ammDisplayIdInput = document.getElementById("amm-display-id");
                const ammStatusSelect = document.getElementById("amm-status");
                const ammAccountsContainer = document.getElementById("amm-accounts-container");

                const updatedName = ammNameInput ? ammNameInput.value.trim() : "";
                const updatedDisplayId = ammDisplayIdInput ? ammDisplayIdInput.value.trim() : "";
                const updatedStatus = ammStatusSelect ? ammStatusSelect.value : "active";
                
                // Get selected weekdays
                const wdayCbs = document.querySelectorAll(".amm-wday-cb");
                const selectedWeekdays = [];
                wdayCbs.forEach(cb => {
                    if (cb.checked) selectedWeekdays.push(parseInt(cb.value));
                });

                // Get selected subjects
                const sbjCbs = document.querySelectorAll(".amm-sbj-cb");
                const selectedSubjects = [];
                sbjCbs.forEach(cb => {
                    if (cb.checked) selectedSubjects.push(cb.value.trim());
                });

                const rows = ammAccountsContainer ? ammAccountsContainer.querySelectorAll(".amm-acc-row") : [];
                const updatedAccounts = Array.from(rows).map(row => {
                    const typeSelect = row.querySelector(".amm-acc-type");
                    const inputVal = row.querySelector(".amm-acc-input");
                    return {
                        type: typeSelect ? typeSelect.value : "academy",
                        username: inputVal ? inputVal.value.trim() : ""
                    };
                }).filter(a => a.username);

                try {
                    const res = await fetch("/api/workspace/update_student_profile", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_uuid: this.currentEditingUserUuid,
                            name: updatedName,
                            note: updatedDisplayId,
                            status: updatedStatus,
                            weekdays: selectedWeekdays,
                            subjects: selectedSubjects,
                            accounts: updatedAccounts
                        })
                    });

                    if (!res.ok) throw new Error("Update failed");
                    if (typeof showToast === "function") {
                        showToast(`[${updatedName}] 수강생 프로필 및 계정 정보가 업데이트되었습니다.`);
                    }
                    closeAmmModal();
                    if (typeof window.loadStudents === "function") {
                        window.loadStudents(window.currentWeekday || "all");
                    }
                } catch (e) {
                    if (typeof showToast === "function") {
                        showToast("수강생 프로필 저장에 실패했습니다.", true);
                    }
                }
            });

            btnDeleteStudent?.addEventListener("click", async () => {
                if (!this.currentEditingUserUuid) return;
                const ammNameInput = document.getElementById("amm-name");
                const targetName = ammNameInput ? ammNameInput.value : "";
                if (!confirm(`정말로 수강생 [${targetName}]을(를) 보드에서 삭제하시겠습니까?`)) return;

                try {
                    const res = await fetch("/api/workspace/delete_student", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ display_id: this.currentEditingUserUuid })
                    });

                    if (!res.ok) throw new Error("Delete failed");
                    if (typeof showToast === "function") {
                        showToast(`수강생이 삭제되었습니다.`);
                    }
                    closeAmmModal();
                    if (window.selectedStudentId === this.currentEditingUserUuid) {
                        window.selectedStudentId = null;
                    }
                    if (typeof window.loadStudents === "function") {
                        window.loadStudents(window.currentWeekday || "all");
                    }
                } catch (e) {
                    if (typeof showToast === "function") {
                        showToast("수강생 삭제 실패", true);
                    }
                }
            });
        },

        renderAccountInputRow: function(accObj = {}) {
            const ammAccountsContainer = document.getElementById("amm-accounts-container");
            if (!ammAccountsContainer) return;

            let accType = "academy";
            let username = "";
            if (typeof accObj === "object" && accObj !== null) {
                accType = accObj.type || "academy";
                username = accObj.username || "";
            } else {
                username = String(accObj || "");
            }

            const row = document.createElement("div");
            row.className = "amm-acc-row";
            row.style.cssText = "display: flex; gap: 6px; align-items: center; margin-bottom: 6px;";
            row.innerHTML = `
                <select class="amm-acc-type" style="padding: 6px; font-size: 0.82rem; border: 1px solid var(--panel-border); border-radius: 6px; background: white;">
                    <option value="academy" ${accType === 'academy' ? 'selected' : ''}>🏫 학원사이트</option>
                    <option value="scratch" ${accType === 'scratch' ? 'selected' : ''}>🧩 스크래치</option>
                    <option value="goorm" ${accType === 'goorm' ? 'selected' : ''}>☁️ 구름</option>
                    <option value="etc" ${accType === 'etc' ? 'selected' : ''}>📘 기타/포털</option>
                </select>
                <input type="text" class="amm-acc-input" value="${username}" placeholder="아이디/계정 입력" style="flex: 1; padding: 6px; font-size: 0.85rem; border: 1px solid var(--panel-border); border-radius: 6px;">
                <button type="button" class="btn-small btn-ghost" onclick="this.parentElement.remove()" style="color: var(--danger-color); padding: 4px 8px;">✕</button>
            `;
            ammAccountsContainer.appendChild(row);
        },

        openAccountManageModal: function(studentKey, event) {
            if (event) event.stopPropagation();
            const students = (window.WorkspaceStudents && window.WorkspaceStudents.students) || window.students || [];
            const student = students.find(s => s.user_uuid === studentKey || s.display_id === studentKey);
            if (!student) return;

            const ammModal = document.getElementById("account-manage-modal");
            const ammStudentName = document.getElementById("amm-student-name");
            const ammNameInput = document.getElementById("amm-name");
            const ammDisplayIdInput = document.getElementById("amm-display-id");
            const ammStatusSelect = document.getElementById("amm-status");
            const ammAccountsContainer = document.getElementById("amm-accounts-container");

            this.currentEditingUserUuid = student.user_uuid || student.display_id;
            if (ammStudentName) ammStudentName.textContent = student.name;
            if (ammNameInput) ammNameInput.value = student.name;
            if (ammDisplayIdInput) ammDisplayIdInput.value = student.note || student.display_id || "";
            if (ammStatusSelect) ammStatusSelect.value = student.status || "active";

            // Populate weekdays checkboxes
            const wdayCbs = document.querySelectorAll(".amm-wday-cb");
            const stWeekdays = student.weekdays || [];
            wdayCbs.forEach(cb => {
                cb.checked = stWeekdays.includes(parseInt(cb.value));
            });

            // Populate subjects checkboxes
            const sbjCbs = document.querySelectorAll(".amm-sbj-cb");
            const stSubjects = student.subjects || [];
            sbjCbs.forEach(cb => {
                cb.checked = stSubjects.includes(cb.value);
            });

            if (ammAccountsContainer) ammAccountsContainer.innerHTML = "";

            const accounts = student.accounts && student.accounts.length > 0 ? student.accounts : [{ type: "academy", username: student.display_id }];
            accounts.forEach(acc => this.renderAccountInputRow(acc));

            ammModal?.classList.add("show");
        }
    };
})(window);

