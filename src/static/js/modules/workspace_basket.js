// workspace_basket.js - 숙제 바구니 & 실시간 할당 관리 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceBasket = {
        basket: [],

        init: function() {
            this.bindEvents();
        },

        bindEvents: function() {
            const btnClearBasket = document.getElementById("btn-clear-basket");
            const btnApplyBasket = document.getElementById("btn-apply-basket");

            btnClearBasket?.addEventListener("click", () => {
                this.clearBasket();
            });

            btnApplyBasket?.addEventListener("click", () => {
                const selectedStudentId = window.selectedStudentId || null;
                if (!selectedStudentId) {
                    if (typeof showToast === "function") {
                        showToast("⚠️ 먼저 우측 수강생 보드에서 숙제를 지정할 학생 카드를 클릭해 주세요!", true);
                    }
                    return;
                }
                if (this.basket.length === 0) {
                    if (typeof showToast === "function") {
                        showToast("🛒 숙제 바구니가 비어 있습니다. 카탈로그에서 문제를 선택해 담아주세요.", true);
                    }
                    return;
                }
                this.assignBasketToStudent(selectedStudentId);
            });
        },

        addToBasket: function(problem) {
            if (!this.basket.find(p => p.legacy_code === problem.legacy_code)) {
                this.basket.push(problem);
                this.renderBasket();

                const problemListContainer = document.getElementById("problem-list-container");
                if (problemListContainer) {
                    const items = problemListContainer.querySelectorAll(".problem-item");
                    items.forEach(item => {
                        const codeSpan = item.querySelector(".problem-status-icon");
                        if (codeSpan && codeSpan.textContent.trim() === problem.legacy_code) {
                            item.style.opacity = "0.45";
                            const btn = item.querySelector("button");
                            if (btn) btn.textContent = "✓";
                        }
                    });
                }
                if (typeof showToast === "function") {
                    showToast(`🛒 [${problem.legacy_code}] 바구니에 담았습니다.`);
                }
            } else {
                if (typeof showToast === "function") {
                    showToast("이미 바구니에 있습니다.", true);
                }
            }
        },

        removeFromBasket: function(index) {
            this.basket.splice(index, 1);
            this.renderBasket();
        },

        clearBasket: function() {
            this.basket = [];
            this.renderBasket();

            const problemListContainer = document.getElementById("problem-list-container");
            if (problemListContainer) {
                const items = problemListContainer.querySelectorAll(".problem-item");
                items.forEach(item => {
                    item.style.opacity = "";
                    const btn = item.querySelector("button.btn-primary");
                    if (btn && btn.textContent === "✓") btn.textContent = "+";
                });
            }
        },

        renderBasket: function() {
            const basketCount = document.getElementById("basket-count");
            const basketItemsContainer = document.getElementById("basket-items");
            if (basketCount) basketCount.innerText = this.basket.length;
            if (basketItemsContainer) {
                basketItemsContainer.innerHTML = "";
                this.basket.forEach((p, index) => {
                    const li = document.createElement("li");
                    li.className = "basket-item";
                    li.innerHTML = `
                        <span>${p.legacy_code} ${p.title}</span>
                        <button class="btn-small btn-ghost" onclick="WorkspaceBasket.removeFromBasket(${index})">❌</button>
                    `;
                    basketItemsContainer.appendChild(li);
                });
            }
        },

        assignBasketToStudent: async function(displayId, event) {
            if (event) event.stopPropagation();
            if (this.basket.length === 0) {
                if (typeof showToast === "function") {
                    showToast("🛒 숙제 바구니가 비어 있습니다.", true);
                }
                return;
            }

            try {
                const res = await fetch(`/api/workspace/save_homework_log`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        display_id: displayId,
                        problems: this.basket
                    })
                });
                if (!res.ok) throw new Error("Save failed");
                
                if (typeof showToast === "function") {
                    showToast(`[${displayId}] 숙제가 할당되었습니다.`);
                }
                this.clearBasket();
            } catch (e) {
                if (typeof showToast === "function") {
                    showToast("숙제 할당에 실패했습니다.", true);
                }
            }
        }
    };
})(window);
