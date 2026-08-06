// workspace_register_modal.js - 신규 수강생 수동 등록 및 슬롯 지정 모달 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceRegisterModal = {
        init: function() {
            this.bindEvents();
        },

        bindEvents: function() {
            const modal = document.getElementById("register-modal");
            const btnAddStudent = document.getElementById("btn-add-student-modal");
            const btnCloseModal = document.getElementById("btn-close-modal");
            const btnSubmitRegister = document.getElementById("btn-submit-register");

            btnAddStudent?.addEventListener("click", () => {
                modal?.classList.add("show");
            });

            btnCloseModal?.addEventListener("click", () => {
                modal?.classList.remove("show");
            });

            btnSubmitRegister?.addEventListener("click", async () => {
                const nameElem = document.getElementById("reg-name");
                const birthElem = document.getElementById("reg-birth");
                const regSlotSelect = document.getElementById("reg-slot");

                const name = nameElem ? nameElem.value.trim() : "";
                const birth = birthElem ? birthElem.value.trim() : "";
                const slot = regSlotSelect ? regSlotSelect.value : "";

                if (!name || !slot) {
                    if (typeof showToast === "function") {
                        showToast("이름과 요일 슬롯을 입력해주세요.", true);
                    }
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

                    if (typeof showToast === "function") {
                        showToast(`${data.display_id} 등록 완료!`);
                    }
                    modal?.classList.remove("show");
                    
                    if (nameElem) nameElem.value = "";
                    if (birthElem) birthElem.value = "";
                    
                    if (typeof window.loadStudents === "function") {
                        window.loadStudents(window.currentWeekday || "all");
                    }
                } catch (e) {
                    if (typeof showToast === "function") {
                        showToast(e.message, true);
                    }
                }
            });
        }
    };
})(window);
