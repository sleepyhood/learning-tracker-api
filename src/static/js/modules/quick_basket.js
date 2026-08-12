/**
 * quick_basket.js
 * 메인 대시보드 퀵 숙제 장바구니 Drawer 제어 모듈
 * (index_view.js Line 602~725 분리본)
 *
 * 전역 노출 함수 (다른 모듈에서 사용):
 *   window.getBasketItems()           - 현재 장바구니 항목 배열 반환
 *   window.addProblemToBasket(obj)    - 장바구니에 문제 추가
 *   window.removeProblemFromBasket(pid) - 장바구니에서 문제 제거
 *   window.isProblemInBasket(pid)     - 장바구니 포함 여부 확인
 *   window.clearQuickBasket()         - 장바구니 전체 초기화
 */
(function initQuickHomeworkBasket() {
  let basketItems = [];

  const badgeEl    = document.getElementById("basket-count-badge");
  const emptyMsgEl = document.getElementById("basket-empty-msg");
  const listEl     = document.getElementById("basket-items-list");
  const clearBtn   = document.getElementById("basket-clear-btn");
  const submitBtn  = document.getElementById("basket-submit-btn");

  function toggleBasketDrawer(forceOpen = null) {
    const bBody   = document.getElementById("basket-body");
    const bFooter = document.querySelector("#quick-homework-basket .basket-footer");
    const tBtn    = document.getElementById("basket-toggle-btn");
    if (!bBody || !tBtn) return;

    const isCurrentlyHidden = bBody.style.display === "none";
    const shouldOpen = forceOpen !== null ? Boolean(forceOpen) : isCurrentlyHidden;

    bBody.style.display = shouldOpen ? "block" : "none";
    if (bFooter) bFooter.style.display = shouldOpen ? "flex" : "none";
    tBtn.textContent = shouldOpen ? "▼" : "▲";
    tBtn.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    tBtn.title = shouldOpen ? "장바구니 접기" : "장바구니 펼치기";
  }

  const toggleBtn = document.getElementById("basket-toggle-btn");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleBasketDrawer();
    });
  }

  function updateBasketUI() {
    if (!badgeEl || !listEl || !emptyMsgEl) return;
    badgeEl.textContent = `${basketItems.length}개`;
    emptyMsgEl.style.display = basketItems.length === 0 ? "block" : "none";

    listEl.innerHTML = basketItems.map((item, idx) => `
      <li style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 8px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.8rem;">
        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; color: #334155;" title="${item.title}">${item.title}</span>
        <button type="button" data-idx="${idx}" class="basket-remove-item-btn" style="background: none; border: none; color: #ef4444; cursor: pointer; font-weight: bold; font-size: 0.9rem;">✕</button>
      </li>
    `).join("");

    listEl.querySelectorAll(".basket-remove-item-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        if (!isNaN(idx)) {
          basketItems.splice(idx, 1);
          updateBasketUI();
          if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
        }
      });
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      basketItems = [];
      updateBasketUI();
      if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
      if (typeof showToast === "function") showToast("🧹 장바구니를 비웠습니다.");
    });
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", () => {
      const targetUuid     = (window.APP_CONFIG && window.APP_CONFIG.userUuid) || "";
      const targetUsername = (window.APP_CONFIG && (window.APP_CONFIG.viewUsername || window.APP_CONFIG.userUuid)) || "";
      if (typeof window.openFeedbackModal === "function") {
        window.openFeedbackModal(targetUsername, targetUsername, targetUuid);
      } else {
        if (typeof showToast === "function") showToast("⚠️ 피드백 모달을 불러올 수 없습니다.", true);
      }
    });
  }

  // 전역 API
  window.getBasketItems = () => basketItems;

  window.clearQuickBasket = function() {
    basketItems = [];
    updateBasketUI();
    if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
  };

  window.addProblemToBasket = function(probObj) {
    if (!probObj || (!probObj.pid && !probObj.legacy_code)) return;
    const pid = probObj.pid || probObj.legacy_code;
    if (!basketItems.some((item) => (item.pid || item.legacy_code) === pid)) {
      basketItems.push({
        pid,
        legacy_code: probObj.legacy_code || pid,
        title: probObj.title || "",
        url: probObj.url || "",
        chapter_code: probObj.chapter_code || probObj.chapter_id || "",
        chapter_id: probObj.chapter_code || probObj.chapter_id || "",
        group_title: probObj.group_title || ""
      });
      updateBasketUI();
      toggleBasketDrawer(true);
    }
  };

  window.removeProblemFromBasket = function(pid) {
    basketItems = basketItems.filter((item) => item.pid !== pid && item.legacy_code !== pid);
    updateBasketUI();
  };

  window.isProblemInBasket = function(pid) {
    return basketItems.some((item) => item.pid === pid || item.legacy_code === pid);
  };

  updateBasketUI();
})();
