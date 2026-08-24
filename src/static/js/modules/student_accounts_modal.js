/**
 * Student Accounts Mapping Manager Modal Controller
 */

(function () {
  let allStudents = [];
  let unlinkedAccounts = [];
  let currentSearchQuery = "";

  const modalEl = document.getElementById("studentAccountsModal");
  const cardsContainer = document.getElementById("samCardsContainer");
  const unlinkedSection = document.getElementById("samUnlinkedSection");
  const unlinkedChipsContainer = document.getElementById("samUnlinkedChips");
  const searchInput = document.getElementById("samSearchInput");
  const emptyState = document.getElementById("samEmptyState");
  const statStudentCount = document.getElementById("samStatStudentCount");
  const statAccountCount = document.getElementById("samStatAccountCount");

  const isStandardAcademyId = (str) => {
    if (!str || typeof str !== 'string') return false;
    return /^([가-힣]{2,4}|[a-zA-Z]{2,15})\d{4}$/.test(str.trim());
  };

  const loadMappingData = async () => {
    try {
      const res = await fetch("/api/students/mapping");
      if (!res.ok) throw new Error("Failed to fetch mapping data");
      const data = await res.json();
      if (data && data.ok) {
        allStudents = data.students || [];
        unlinkedAccounts = data.unlinked_accounts || [];
        render();
      }
    } catch (err) {
      console.error("[StudentAccountsModal] load error:", err);
    }
  };

  const renderUnlinkedAccounts = () => {
    if (!unlinkedSection || !unlinkedChipsContainer) return;

    if (!unlinkedAccounts || unlinkedAccounts.length === 0) {
      unlinkedSection.style.display = "none";
      return;
    }

    unlinkedSection.style.display = "block";
    unlinkedChipsContainer.innerHTML = "";

    unlinkedAccounts.forEach((acc) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "sam-unlinked-chip";
      chip.innerHTML = `<span>@${acc}</span> <span>➕ 연결</span>`;
      chip.title = `'${acc}' 계정을 수강생에게 연결하거나 새 학생으로 등록합니다.`;
      
      chip.addEventListener("click", () => {
        handleLinkUnlinkedAccount(acc);
      });

      unlinkedChipsContainer.appendChild(chip);
    });
  };

  const handleLinkUnlinkedAccount = (acc) => {
    const studentNames = allStudents.map((s, idx) => `${idx + 1}. ${s.name} (@${s.display_id})`).join("\n");
    const choice = prompt(
      `[미연결 계정 연결: @${acc}]\n\n연결할 수강생의 번호를 입력하거나, 새 학생으로 등록하려면 빈칸으로 두고 확인을 누르세요:\n\n${studentNames}`
    );

    if (choice === null) return;

    const trimmed = choice.trim();
    if (!trimmed) {
      // Create as new student
      fetch("/api/students/mapping/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account: acc })
      })
        .then(res => res.json())
        .then(() => {
          loadMappingData();
          window.refreshStudentSuggestions?.();
        });
      return;
    }

    const idx = parseInt(trimmed, 10) - 1;
    if (idx >= 0 && idx < allStudents.length) {
      const targetStudent = allStudents[idx];
      const nextAccs = Array.from(new Set([...(targetStudent.accounts || []), acc]));
      
      fetch("/api/students/mapping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_uuid: targetStudent.user_uuid,
          accounts: nextAccs
        })
      })
        .then(res => res.json())
        .then(() => {
          loadMappingData();
          window.refreshStudentSuggestions?.();
        });
    } else {
      alert("올바른 번호를 입력해주세요.");
    }
  };

  const renderStudentCard = (st) => {
    const card = document.createElement("div");
    card.className = "sam-card";
    card.dataset.uuid = st.user_uuid;

    const isCustom = !isStandardAcademyId(st.display_id) && !isStandardAcademyId(st.name);
    const accounts = Array.isArray(st.accounts) ? st.accounts : [st.display_id];
    const suggestedAccounts = Array.isArray(st.suggested_accounts) ? st.suggested_accounts : [];

    card.innerHTML = `
      <div class="sam-card-header">
        <div class="sam-name-wrap">
          <span class="sam-student-name" title="클릭하여 이름 수정">${st.name}</span>
          ${st.birth_md ? `<span class="sam-badge-birth">🎂 ${st.birth_md}</span>` : ''}
          ${isCustom ? `<span class="sam-badge-custom-id">외부/커스텀ID</span>` : ''}
        </div>
        <div class="sam-card-actions">
          <button type="button" class="sam-btn-delete-student" title="수강생 삭제">🗑️ 삭제</button>
        </div>
      </div>
      <div class="sam-accounts-row">
        ${accounts.map(acc => `
          <span class="sam-acc-chip ${acc === st.display_id ? 'is-primary' : ''}" title="${acc === st.display_id ? '현재 대표 계정' : '클릭하여 대표 계정으로 전환'}">
            <span class="sam-primary-star" title="${acc === st.display_id ? '대표 계정' : '클릭 시 대표 계정 지정'}">${acc === st.display_id ? '⭐' : '☆'}</span>
            <span>@${acc}</span>
            <button type="button" class="sam-chip-del" data-acc="${acc}" title="계정 연결 해제">✕</button>
          </span>
        `).join('')}
        <div class="sam-add-acc-wrap">
          <input type="text" class="sam-add-acc-input" placeholder="+ 부계정 추가..." />
          <button type="button" class="sam-btn-add-acc">추가</button>
        </div>
      </div>
      ${suggestedAccounts.length > 0 ? `
        <div class="sam-suggested-row">
          <span class="sam-suggested-label">💡 유사 계정 추천:</span>
          ${suggestedAccounts.map(sAcc => `
            <button type="button" class="sam-btn-suggested-chip" data-acc="${sAcc}" title="'${sAcc}' 계정을 ${st.name} 학생의 부계정으로 1클릭 연결합니다.">
              <span>@${sAcc}</span> <span>➕</span>
            </button>
          `).join('')}
        </div>
      ` : ''}
    `;

    // 1. Inline Name Edit
    const nameEl = card.querySelector(".sam-student-name");
    nameEl.addEventListener("click", () => {
      const currentName = st.name;
      const input = document.createElement("input");
      input.type = "text";
      input.className = "sam-name-edit-input";
      input.value = currentName;
      nameEl.replaceWith(input);
      input.focus();
      input.select();

      const saveName = async () => {
        const nextName = input.value.trim();
        if (nextName && nextName !== currentName) {
          try {
            await fetch("/api/students/mapping", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_uuid: st.user_uuid,
                name: nextName
              })
            });
            st.name = nextName;
            window.refreshStudentSuggestions?.();
          } catch (e) {
            console.error(e);
          }
        }
        render();
      };

      input.addEventListener("blur", saveName);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") saveName();
        else if (e.key === "Escape") render();
      });
    });

    // 2. Add Sub-Account
    const addInput = card.querySelector(".sam-add-acc-input");
    const addBtn = card.querySelector(".sam-btn-add-acc");
    const handleAddAccount = async () => {
      const newAcc = addInput.value.trim();
      if (!newAcc) return;
      if (accounts.includes(newAcc)) {
        alert("이미 연결된 계정입니다.");
        return;
      }
      const nextAccounts = [...accounts, newAcc];
      try {
        await fetch("/api/students/mapping", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_uuid: st.user_uuid,
            accounts: nextAccounts
          })
        });
        st.accounts = nextAccounts;
        unlinkedAccounts = unlinkedAccounts.filter(a => a !== newAcc);
        loadMappingData();
        window.refreshStudentSuggestions?.();
      } catch (err) {
        console.error(err);
      }
    };

    addBtn.addEventListener("click", handleAddAccount);
    addInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleAddAccount();
    });

    // 3. 1-Click Smart Sub-Account Link
    card.querySelectorAll(".sam-btn-suggested-chip").forEach(sBtn => {
      sBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const accToLink = sBtn.dataset.acc;
        sBtn.disabled = true;
        sBtn.innerHTML = `<span>@${accToLink}</span> <span>⏳</span>`;
        try {
          const res = await fetch("/api/students/mapping/link_subaccount", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_uuid: st.user_uuid,
              account: accToLink
            })
          });
          const data = await res.json();
          if (data && data.ok) {
            await loadMappingData();
            window.refreshStudentSuggestions?.();
          } else {
            alert(data.error || "부계정 연결에 실패했습니다.");
            sBtn.disabled = false;
            sBtn.innerHTML = `<span>@${accToLink}</span> <span>➕</span>`;
          }
        } catch (err) {
          console.error(err);
          alert("네트워크 오류가 발생했습니다.");
          sBtn.disabled = false;
          sBtn.innerHTML = `<span>@${accToLink}</span> <span>➕</span>`;
        }
      });
    });

    // 4. Toggle Primary Account (⭐)
    card.querySelectorAll(".sam-acc-chip").forEach(chip => {
      chip.addEventListener("click", async (e) => {
        if (e.target.closest(".sam-chip-del")) return;
        const starEl = chip.querySelector(".sam-primary-star");
        const chipAcc = chip.querySelector("span:nth-child(2)")?.textContent?.replace("@", "").trim();
        if (chipAcc && chipAcc !== st.display_id) {
          if (confirm(`'@${chipAcc}' 계정을 '${st.name}' 학생의 대표(본계정)으로 지정하시겠습니까?`)) {
            try {
              await fetch("/api/students/mapping", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  user_uuid: st.user_uuid,
                  display_id: chipAcc
                })
              });
              st.display_id = chipAcc;
              render();
              window.refreshStudentSuggestions?.();
            } catch (err) {
              console.error(err);
            }
          }
        }
      });
    });

    // 5. Remove Account
    card.querySelectorAll(".sam-chip-del").forEach(delBtn => {
      delBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const accToRemove = delBtn.dataset.acc;
        if (!confirm(`'@${accToRemove}' 계정을 '${st.name}' 수강생에서 연결 해제하시겠습니까?`)) return;

        const nextAccounts = accounts.filter(a => a !== accToRemove);
        const nextDisplayId = (st.display_id === accToRemove) ? (nextAccounts[0] || "") : st.display_id;

        try {
          await fetch("/api/students/mapping", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_uuid: st.user_uuid,
              display_id: nextDisplayId,
              accounts: nextAccounts
            })
          });
          st.accounts = nextAccounts;
          st.display_id = nextDisplayId;
          unlinkedAccounts.push(accToRemove);
          loadMappingData();
          window.refreshStudentSuggestions?.();
        } catch (err) {
          console.error(err);
        }
      });
    });

    // 6. Delete Student
    const btnDelStudent = card.querySelector(".sam-btn-delete-student");
    btnDelStudent.addEventListener("click", async () => {
      if (!confirm(`'${st.name}' 수강생 매핑 정보를 정말 삭제하시겠습니까?`)) return;
      try {
        await fetch("/api/students/mapping/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_uuid: st.user_uuid })
        });
        allStudents = allStudents.filter(s => s.user_uuid !== st.user_uuid);
        loadMappingData();
        window.refreshStudentSuggestions?.();
      } catch (err) {
        console.error(err);
      }
    });

    return card;
  };

  const render = () => {
    if (!cardsContainer) return;

    renderUnlinkedAccounts();

    const q = currentSearchQuery.toLowerCase().trim();
    const filtered = allStudents.filter((st) => {
      if (!q) return true;
      const name = (st.name || "").toLowerCase();
      const displayId = (st.display_id || "").toLowerCase();
      const hasAcc = Array.isArray(st.accounts) && st.accounts.some(a => String(a).toLowerCase().includes(q));
      return name.includes(q) || displayId.includes(q) || hasAcc;
    });

    cardsContainer.innerHTML = "";

    if (filtered.length === 0) {
      emptyState.style.display = "block";
    } else {
      emptyState.style.display = "none";
      filtered.forEach(st => {
        cardsContainer.appendChild(renderStudentCard(st));
      });
    }

    // Stats
    let totalAccCount = 0;
    allStudents.forEach(st => {
      totalAccCount += Array.isArray(st.accounts) ? st.accounts.length : 1;
    });

    if (statStudentCount) statStudentCount.textContent = allStudents.length;
    if (statAccountCount) statAccountCount.textContent = totalAccCount;
  };

  window.openStudentAccountsModal = () => {
    if (!modalEl) return;
    modalEl.style.display = "flex";
    currentSearchQuery = "";
    if (searchInput) searchInput.value = "";
    loadMappingData();
  };

  window.closeStudentAccountsModal = () => {
    if (!modalEl) return;
    modalEl.style.display = "none";
    window.refreshStudentSuggestions?.();
  };

  window.samPromptNewStudent = async () => {
    const input = prompt("등록할 수강생 실명 또는 대표 계정 ID를 입력하세요 (예: 홍길동0101, leo0719):");
    if (!input || !input.trim()) return;

    try {
      const res = await fetch("/api/students/mapping/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account: input.trim() })
      });
      const data = await res.json();
      if (data && data.ok) {
        loadMappingData();
        window.refreshStudentSuggestions?.();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Listeners
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      currentSearchQuery = e.target.value;
      render();
    });
  }

  if (modalEl) {
    modalEl.addEventListener("click", (e) => {
      if (e.target === modalEl) {
        closeStudentAccountsModal();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modalEl && modalEl.style.display === "flex") {
      closeStudentAccountsModal();
    }
  });
})();
