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

  const modalBtn   = document.getElementById("basket-modal-btn");

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      basketItems = [];
      updateBasketUI();
      if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
      if (typeof showToast === "function") showToast("🧹 장바구니를 비웠습니다.");
    });
  }

  if (modalBtn) {
    modalBtn.addEventListener("click", () => {
      const targetUuid     = (window.APP_CONFIG && window.APP_CONFIG.userUuid) || "";
      const targetUsername = (window.APP_CONFIG && (window.APP_CONFIG.viewUsername || window.APP_CONFIG.userUuid)) || "";
      if (typeof window.openFeedbackModal === "function") {
        window.openFeedbackModal(targetUsername, targetUsername, targetUuid);
      } else {
        if (typeof showToast === "function") showToast("⚠️ 피드백 모달을 불러올 수 없습니다.", true);
      }
    });
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      if (basketItems.length === 0) {
        if (typeof showToast === "function") showToast("⚠️ 장바구니에 출제할 문제를 먼저 담아주세요!", true);
        return;
      }

      const targetUuid     = (window.APP_CONFIG && window.APP_CONFIG.userUuid) || "";
      const targetUsername = (window.APP_CONFIG && (window.APP_CONFIG.viewUsername || window.APP_CONFIG.userUuid)) || "";

      const origText = submitBtn.textContent;
      submitBtn.textContent = "⏳ 저장 중...";
      submitBtn.disabled = true;

      try {
        const payload = {
          display_id: targetUsername,
          user_uuid: targetUuid,
          problems: basketItems,
          mode: "homework",
          title: `${targetUsername} 학생 숙제 출제 (${basketItems.length}개)`
        };

        const res = await fetch(`/api/workspace/save_homework_log`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || `저장 실패 (${res.status})`);
        }

        submitBtn.textContent = "✅ 저장 완료!";
        submitBtn.style.background = "#10b981";

        if (typeof showToast === "function") {
          showToast(`🚀 [${targetUsername}] 학생에게 숙제 ${basketItems.length}문항이 저장되었습니다!\n(CLI로 돌아가 Enter를 누르세요)`, false, 4500);
        }

        setTimeout(() => {
          basketItems = [];
          updateBasketUI();
          if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
          submitBtn.disabled = false;
          submitBtn.textContent = origText;
          submitBtn.style.background = "";
        }, 1500);

      } catch (err) {
        submitBtn.disabled = false;
        submitBtn.textContent = origText;
        submitBtn.style.background = "";
        if (typeof showToast === "function") showToast(`⚠️ 숙제 저장 실패: ${err.message}`, true, 4000);
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
    const existing = basketItems.find((item) => (item.pid || item.legacy_code) === pid);
    if (existing) {
      if (probObj.group_title && !existing.group_title) existing.group_title = probObj.group_title;
      if (probObj.chapter_code && !existing.chapter_code) {
        existing.chapter_code = probObj.chapter_code;
        existing.chapter_id = probObj.chapter_code;
      }
    } else {
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
