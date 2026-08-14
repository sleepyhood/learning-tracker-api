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
          <span class="sam-acc-chip ${acc === st.display_id ? 'is-primary' : ''}">
            ${acc === st.display_id ? '<span class="sam-primary-star" title="대표 계정">⭐</span>' : ''}
            <span>@${acc}</span>
            <button type="button" class="sam-chip-del" data-acc="${acc}" title="계정 연결 해제">✕</button>
          </span>
        `).join('')}
        <div class="sam-add-acc-wrap">
          <input type="text" class="sam-add-acc-input" placeholder="+ 부계정 추가..." />
          <button type="button" class="sam-btn-add-acc">추가</button>
        </div>
      </div>
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
        render();
        window.refreshStudentSuggestions?.();
      } catch (err) {
        console.error(err);
      }
    };

    addBtn.addEventListener("click", handleAddAccount);
    addInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleAddAccount();
    });

    // 3. Remove Account
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
          render();
          window.refreshStudentSuggestions?.();
        } catch (err) {
          console.error(err);
        }
      });
    });

    // 4. Delete Student
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
        render();
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
