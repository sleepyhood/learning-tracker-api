document.addEventListener("DOMContentLoaded", () => {
    // 1. Initialize Modules (Phase 1)
    if (window.WorkspaceStudents) {
        window.WorkspaceStudents.init();
        window.WorkspaceStudents.loadStudents();
    }

    // Legacy State Compatibility Wrappers
    Object.defineProperty(window, "students", {
        get: () => (window.WorkspaceStudents ? window.WorkspaceStudents.students : []),
        set: (val) => { if (window.WorkspaceStudents) window.WorkspaceStudents.students = val; }
    });
    Object.defineProperty(window, "selectedStudentId", {
        get: () => (window.WorkspaceStudents ? window.WorkspaceStudents.selectedStudentId : null),
        set: (val) => { if (window.WorkspaceStudents) window.WorkspaceStudents.selectedStudentId = val; }
    });
    Object.defineProperty(window, "currentWeekday", {
        get: () => (window.WorkspaceStudents ? window.WorkspaceStudents.currentWeekday : "all"),
        set: (val) => { if (window.WorkspaceStudents) window.WorkspaceStudents.currentWeekday = val; }
    });

    window.loadStudents = (weekday = "all") => window.WorkspaceStudents && window.WorkspaceStudents.loadStudents(weekday);
    window.renderStudents = () => window.WorkspaceStudents && window.WorkspaceStudents.renderStudents();
    window.updateSlotDropdown = () => window.WorkspaceStudents && window.WorkspaceStudents.updateSlotDropdown();

    let basket = [];
    let searchDebounceTimer = null;

    // Elements
    const gridContainer = document.getElementById("student-grid-container");
    const problemListContainer = document.getElementById("problem-list-container");
    const problemSearchInput = document.getElementById("problem-search");
    const basketCount = document.getElementById("basket-count");
    const basketItemsContainer = document.getElementById("basket-items");

    // Modal Elements
    const modal = document.getElementById("register-modal");
    const btnAddStudent = document.getElementById("btn-add-student-modal");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const btnSubmitRegister = document.getElementById("btn-submit-register");
    const regSlotSelect = document.getElementById("reg-slot");


    // Multi-Curriculum & Chapter Filter Elements & Functions
    const curriculumSelect = document.getElementById("curriculum-select");
    const chapterFilterSelect = document.getElementById("chapter-filter-select");
    const subChapterFilterSelect = document.getElementById("sub-chapter-filter-select");
    const quickTagChips = document.querySelectorAll("#quick-tag-chips button");

    // Modal Elements
    const btnOpenCatalogManage = document.getElementById("btn-open-catalog-manage");
    const btnCloseCatalogManage = document.getElementById("btn-close-catalog-manage");
    const catalogManageModal = document.getElementById("catalog-manage-modal");
    const tabCatCrawl = document.getElementById("tab-cat-crawl");
    const tabCatBatch = document.getElementById("tab-cat-batch");
    const manageTabContentCrawl = document.getElementById("manage-tab-content-crawl");
    const manageTabContentBatch = document.getElementById("manage-tab-content-batch");
    const curriculumManageList = document.getElementById("curriculum-manage-list");
    const btnSubmitBatchAdd = document.getElementById("btn-submit-batch-add");

    let curriculumsData = [];
    let lastSearchTree = {};
    let selectedTag = "";

    async function loadCurriculums() {
        try {
            const res = await fetch("/api/workspace/curriculums");
            if (!res.ok) return;
            const data = await res.json();
            curriculumsData = data.curriculums || [];
            updateChapterDropdown();
            renderCurriculumManageList();
        } catch (e) {
            console.error("Failed to load curriculums", e);
        }
    }

    function updateChapterDropdown(tree = lastSearchTree) {
        if (!chapterFilterSelect) return;
        const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
        const currObj = curriculumsData.find(c => c.key === currKey);
        const savedVal = chapterFilterSelect.value || "all";

        const majorSet = new Set();

        if (tree && typeof tree === "object") {
            Object.keys(tree).forEach(m => {
                if (m && m !== "undefined") majorSet.add(m);
            });
        }

        if (currObj && currObj.chapters) {
            currObj.chapters.forEach(ch => {
                const majorName = typeof ch === "object" ? (ch.major || ch) : ch;
                if (majorName && majorName !== "undefined") majorSet.add(majorName);
            });
        }

        chapterFilterSelect.innerHTML = `<option value="all">전체 대단원 목차</option>`;
        if (subChapterFilterSelect && savedVal === "all") {
            subChapterFilterSelect.innerHTML = `<option value="all">전체 소단원</option>`;
        }

        majorSet.forEach(majorName => {
            const opt = document.createElement("option");
            opt.value = majorName;
            opt.textContent = majorName;
            chapterFilterSelect.appendChild(opt);
        });

        if (Array.from(chapterFilterSelect.options).some(o => o.value === savedVal)) {
            chapterFilterSelect.value = savedVal;
        }
    }

    function updateSubChapterDropdown(tree = lastSearchTree) {
        if (!subChapterFilterSelect) return;
        const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
        const currObj = curriculumsData.find(c => c.key === currKey);
        const selectedMajor = chapterFilterSelect ? chapterFilterSelect.value : "all";
        const savedSubVal = subChapterFilterSelect.value || "all";

        subChapterFilterSelect.innerHTML = `<option value="all">전체 소단원</option>`;
        if (selectedMajor === "all") return;

        const subSet = new Set();

        if (tree && tree[selectedMajor] && Array.isArray(tree[selectedMajor])) {
            tree[selectedMajor].forEach(subName => {
                if (subName) subSet.add(subName);
            });
        }

        if (currObj && currObj.chapters) {
            const majorObj = currObj.chapters.find(ch => (typeof ch === "object" ? ch.major : ch) === selectedMajor);
            if (majorObj && typeof majorObj === "object" && majorObj.subs) {
                majorObj.subs.forEach(subName => {
                    if (subName) subSet.add(subName);
                });
            }
        }

        subSet.forEach(subName => {
            const opt = document.createElement("option");
            opt.value = subName;
            opt.textContent = subName;
            subChapterFilterSelect.appendChild(opt);
        });

        if (Array.from(subChapterFilterSelect.options).some(o => o.value === savedSubVal)) {
            subChapterFilterSelect.value = savedSubVal;
        }
    }

    function triggerCatalogSearch() {
        const q = problemSearchInput ? problemSearchInput.value.trim() : "";
        searchProblems(q);
    }

    // Curriculum & Chapter Select Event Handlers
    curriculumSelect?.addEventListener("change", () => {
        updateChapterDropdown();
        triggerCatalogSearch();
    });

    chapterFilterSelect?.addEventListener("change", () => {
        updateSubChapterDropdown();
        triggerCatalogSearch();
    });

    subChapterFilterSelect?.addEventListener("change", () => {
        triggerCatalogSearch();
    });

    // Quick Tag Chips Event Handlers
    quickTagChips.forEach(chip => {
        chip.addEventListener("click", (e) => {
            quickTagChips.forEach(c => {
                c.style.background = "";
                c.style.color = "";
            });
            e.target.style.background = "var(--accent-color)";
            e.target.style.color = "white";
            selectedTag = e.target.getAttribute("data-tag") || "";

            if (selectedTag) {
                if (problemSearchInput) problemSearchInput.value = selectedTag;
            } else {
                if (problemSearchInput) problemSearchInput.value = "";
            }
            triggerCatalogSearch();
        });
    });

    // Modal Event Bindings
    btnOpenCatalogManage?.addEventListener("click", () => {
        catalogManageModal?.classList.add("show");
        loadCurriculums();
    });

    btnCloseCatalogManage?.addEventListener("click", () => {
        catalogManageModal?.classList.remove("show");
    });

    tabCatCrawl?.addEventListener("click", () => {
        tabCatCrawl.style.background = "var(--accent-color)";
        tabCatCrawl.style.color = "white";
        tabCatBatch.style.background = "";
        tabCatBatch.style.color = "";
        manageTabContentCrawl.style.display = "flex";
        manageTabContentBatch.style.display = "none";
    });

    tabCatBatch?.addEventListener("click", () => {
        tabCatBatch.style.background = "var(--accent-color)";
        tabCatBatch.style.color = "white";
        tabCatCrawl.style.background = "";
        tabCatCrawl.style.color = "";
        manageTabContentBatch.style.display = "flex";
        manageTabContentCrawl.style.display = "none";
    });

    function renderCurriculumManageList() {
        if (!curriculumManageList) return;
        curriculumManageList.innerHTML = "";

        curriculumsData.forEach((cfg, idx) => {
            const selectId = `scope-select-${cfg.key}-${idx}`;
            const item = document.createElement("div");
            item.style.cssText = "display:flex; flex-direction:column; gap:6px; background:#f8fafc; padding:10px 12px; border-radius:8px; border:1px solid #e2e8f0;";

            let optionsHtml = `<option value="all">🌐 전체 갱신 (전체 단원)</option>`;
            if (cfg.key === "prog2") {
                optionsHtml += `
                    <option value="AL100">1. 알고리즘 기초 (AL100)</option>
                    <option value="STR101">2. 자료구조 브론즈1 (STR101)</option>
                    <option value="AL101">3. 알고리즘 브론즈1 (AL101)</option>
                    <option value="STR102">4. 자료구조 브론즈2 (STR102)</option>
                    <option value="AL102">5. 알고리즘 브론즈2 (AL102)</option>
                    <option value="STR201">6. 자료구조 실버 (STR201)</option>
                    <option value="AL201">7. 알고리즘 실버1 (AL201)</option>
                    <option value="AL202">8. 알고리즘 실버2 (AL202)</option>
                    <option value="AL301">9. 알고리즘 골드1 (AL301)</option>
                    <option value="AL302">10. 알고리즘 골드2 (AL302)</option>
                `;
            } else if (cfg.key === "prog1") {
                optionsHtml += `
                    <option value="p101">1. 기초문법1 (p101)</option>
                    <option value="p102">2. 기초문법2 (p102)</option>
                    <option value="p201">3. 알고리즘 초급 (p201)</option>
                    <option value="p202">4. 알고리즘 중급1 (p202)</option>
                    <option value="p203">5. 알고리즘 중급2 (p203)</option>
                    <option value="p206">6. 알고리즘 중급3 (p206)</option>
                    <option value="p204">7. 알고리즘 고급1 (p204)</option>
                    <option value="p205">8. 알고리즘 고급2 (p205)</option>
                `;
            } else if (cfg.chapters && cfg.chapters.length > 0) {
                cfg.chapters.forEach((ch, cidx) => {
                    const majorName = typeof ch === "object" ? ch.major : ch;
                    const slugVal = (typeof ch === "object" && ch.slug) ? ch.slug : (cidx + 1).toString();
                    optionsHtml += `<option value="${slugVal}">${majorName}</option>`;
                });
            }

            item.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-weight:700; font-size:0.88rem;">${cfg.name}</div>
                        <div style="font-size:0.75rem; color:#64748b;">${cfg.url ? cfg.url : "오프라인/자체 데이터셋"}</div>
                    </div>
                </div>
                ${cfg.url ? `
                <div style="display:flex; gap:6px; align-items:center; margin-top:2px;">
                    <select id="${selectId}" style="flex:1; padding:4px 8px; border-radius:6px; border:1px solid var(--panel-border); font-size:0.8rem;">
                        ${optionsHtml}
                    </select>
                    <button class="btn-small btn-primary" onclick="triggerChapterUpdate('${cfg.key}', '${selectId}', this)">🔄 선택 갱신</button>
                </div>
                ` : `<div style="font-size:0.75rem; color:#94a3b8; padding-top:2px;">수동 수집 전용 (엑셀/텍스트 등록 탭 이용)</div>`}
            `;
            curriculumManageList.appendChild(item);
        });
    }

    let crawlPollInterval = null;

    function startCrawlProgressPolling() {
        if (crawlPollInterval) clearInterval(crawlPollInterval);
        crawlPollInterval = setInterval(async () => {
            try {
                const res = await fetch("/api/workspace/crawl_status");
                if (!res.ok) return;
                const data = await res.json();
                if (data.ok && data.status) {
                    const st = data.status;
                    if (st.active) {
                        const pctStr = st.percent > 0 ? ` (${st.percent}%)` : "";
                        const stepStr = st.total_steps > 0 ? `[${st.current_step}/${st.total_steps}] ` : "";
                        showToast(`⏳ ${stepStr}${st.current_name || st.message}${pctStr}`);
                    } else if (st.percent === 100) {
                        clearInterval(crawlPollInterval);
                        crawlPollInterval = null;
                    }
                }
            } catch (e) {}
        }, 1000);
    }

    window.triggerChapterUpdate = async (currKey, selectId, btnElem) => {
        const selectElem = document.getElementById(selectId);
        const chapterVal = selectElem ? selectElem.value : "all";
        const chapterLabel = selectElem && selectElem.selectedIndex >= 0 ? selectElem.options[selectElem.selectedIndex].text : "전체";

        const originalText = btnElem ? btnElem.textContent : "🔄 선택 갱신";
        if (btnElem) {
            btnElem.disabled = true;
            btnElem.textContent = "갱신 중...";
        }

        showToast(`🚀 ${chapterLabel} 문제 목록 갱신을 시작합니다...`);
        startCrawlProgressPolling();

        try {
            let res, data;
            if (currKey === "prog1" && chapterVal !== "all") {
                // Chapter-specific update via /update_problems
                res = await fetch("/update_problems", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ chapter: chapterVal })
                });
            } else {
                // Full curriculum crawl via Playwright / trigger_crawl
                res = await fetch("/api/workspace/trigger_crawl", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ curriculum_key: currKey, chapter: chapterVal })
                });
            }

            data = await res.json().catch(() => ({}));
            if (res.ok && (data.ok || data.message)) {
                showToast(`✅ ${data.message || `${chapterLabel} 문제 목록을 갱신했습니다.`}`);
                await loadCurriculums();
                triggerCatalogSearch();
            } else {
                showToast(`❌ ${data.error || "갱신에 실패했습니다."}`, true);
            }
        } catch (e) {
            showToast("요청 중 오류가 발생했습니다.", true);
        } finally {
            if (crawlPollInterval) {
                clearInterval(crawlPollInterval);
                crawlPollInterval = null;
            }
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.textContent = originalText;
            }
        }
    };

    btnSubmitBatchAdd?.addEventListener("click", async () => {
        const currKey = document.getElementById("batch-curr-select")?.value || "prog1";
        const major = document.getElementById("batch-major-input")?.value || "기타 단원";
        const sub = document.getElementById("batch-sub-input")?.value || "일반";
        const rawText = document.getElementById("batch-raw-text")?.value || "";

        if (!rawText.trim()) {
            showToast("붙여넣을 문제 텍스트를 입력하세요.", true);
            return;
        }

        try {
            const res = await fetch("/api/workspace/batch_add_problems", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    curriculum_key: currKey,
                    major: major,
                    sub: sub,
                    raw_text: rawText
                })
            });
            const data = await res.json();
            if (data.ok) {
                showToast("✅ " + data.message);
                document.getElementById("batch-raw-text").value = "";
                catalogManageModal?.classList.remove("show");
                await loadCurriculums();
                triggerCatalogSearch();
            } else {
                showToast("❌ " + (data.error || "일괄 등록 실패"), true);
            }
        } catch (e) {
            showToast("일괄 등록 중 오류가 발생했습니다.", true);
        }
    });

    // 5. Select Student
    window.selectStudent = (displayId) => {
        selectedStudentId = displayId;
        renderStudents();

        // 1. Clear basket when switching student to avoid cross-assignment
        basket = [];
        renderBasket();

        // 2. Re-trigger active search with newly selected student ID to update solve status icons (🟢)
        if (problemSearchInput) {
            problemSearchInput.focus();
            triggerCatalogSearch();
        }
    };

    // 6. Live Problem Search (replaces loadStudentProblems)
    async function searchProblems(query) {
        let q = query.trim();
        const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
        const chapterVal = chapterFilterSelect ? chapterFilterSelect.value : "all";
        const subVal = subChapterFilterSelect ? subChapterFilterSelect.value : "all";

        // If query is empty but chapter filter or curriculum is set, search all in that chapter
        if (q.length < 2 && chapterVal === "all" && subVal === "all" && !q) {
            q = "ALL";
        }

        problemListContainer.innerHTML = `<div class='problem-empty-state'>검색 중...</div>`;

        try {
            const displayIdParam = selectedStudentId ? `&display_id=${encodeURIComponent(selectedStudentId)}` : "";
            const chapterParam = chapterVal !== "all" ? `&chapter=${encodeURIComponent(chapterVal)}` : "";
            const subParam = subVal !== "all" ? `&sub=${encodeURIComponent(subVal)}` : "";
            const currParam = `&curriculum=${encodeURIComponent(currKey)}&curr=${encodeURIComponent(currKey)}`;


            const res = await fetch(`/api/workspace/search_problems?q=${encodeURIComponent(q)}&limit=80${currParam}${chapterParam}${subParam}${displayIdParam}`);
            const data = await res.json();
            const problems = data.problems || [];

            if (data.tree) {
                lastSearchTree = data.tree;
                updateChapterDropdown(data.tree);
                updateSubChapterDropdown(data.tree);
            }

            problemListContainer.innerHTML = "";


            if (problems.length === 0) {
                problemListContainer.innerHTML = `<div class='problem-empty-state'>"${query}" 검색 결과 없음</div>`;
                return;
            }

            // Summary badge
            const solvedCount = problems.filter(p => p.status === "solved").length;
            const countBadge = document.createElement("div");
            countBadge.style.cssText = "font-size:0.78rem;color:#86868b;padding:2px 4px 8px;";
            countBadge.innerHTML = `${problems.length}개 목록${selectedStudentId ? ` · <span style='color:#34c759'>🟢 풀이완료 ${solvedCount}개</span>` : ""}`;
            problemListContainer.appendChild(countBadge);

            problems.forEach(p => {
                const inBasket = basket.find(b => b.legacy_code === p.legacy_code);
                const isSolved = p.status === "solved";
                const isWrong  = p.status === "wrong";
                const isPartial = p.status === "partial";

                // Status icon
                let statusIcon = "";
                let rowStyle = "";
                if (isSolved) {
                    statusIcon = `<span title="이미 풀이 완료" style="margin-right:4px;font-size:0.85rem;">🟢</span>`;
                    rowStyle = "background:#f0fdf4;border-color:#bbf7d0;";
                } else if (isWrong) {
                    statusIcon = `<span title="오답" style="margin-right:4px;font-size:0.85rem;">🔴</span>`;
                } else if (isPartial) {
                    statusIcon = `<span title="진행 중" style="margin-right:4px;font-size:0.85rem;">🟡</span>`;
                }

                const item = document.createElement("div");
                item.className = "problem-item" + (inBasket ? " in-basket" : "");
                item.style.cssText = (inBasket ? "opacity:0.45;" : "") + rowStyle;

                const safeP = JSON.stringify(p).replace(/"/g, "&quot;");
                item.innerHTML = `
                    <span class="problem-status-icon" style="flex-shrink:0;min-width:75px;font-size:0.75rem;">${statusIcon}${p.legacy_code}</span>
                    <span class="problem-title">${p.title}</span>
                    <button class="btn-small btn-primary" style="flex-shrink:0;padding:2px 7px;font-size:0.75rem;border-radius:4px;${isSolved ? 'background:#34c759;' : ''}" onclick="event.stopPropagation(); addToBasket(${safeP})">${inBasket ? "✓" : "+"}</button>
                `;
                item.onclick = () => addToBasket(p);
                problemListContainer.appendChild(item);
            });

        } catch (e) {
            showToast("문제 검색에 실패했습니다.", true);
        }
    }


    // Wire search input with debounce (300ms)
    if (problemSearchInput) {
        problemSearchInput.addEventListener("input", () => {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                triggerCatalogSearch();
            }, 300);
        });
        // Trigger on Enter for speed
        problemSearchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                clearTimeout(searchDebounceTimer);
                searchProblems(problemSearchInput.value);
            }
        });
    }

    // 7. Basket Logic
    window.addToBasket = (problem) => {
        if (!basket.find(p => p.legacy_code === problem.legacy_code)) {
            basket.push(problem);
            renderBasket();
            // Update the matching row in search results in-place (no re-search needed)
            const items = problemListContainer.querySelectorAll(".problem-item");
            items.forEach(item => {
                const codeSpan = item.querySelector(".problem-status-icon");
                if (codeSpan && codeSpan.textContent.trim() === problem.legacy_code) {
                    item.style.opacity = "0.45";
                    const btn = item.querySelector("button");
                    if (btn) btn.textContent = "✓";
                }
            });
            showToast(`🛒 [${problem.legacy_code}] 바구니에 담았습니다.`);
        } else {
            showToast("이미 바구니에 있습니다.", true);
        }
    };

    document.getElementById("btn-clear-basket").onclick = () => {
        basket = [];
        renderBasket();
        // Re-enable all dimmed search items
        const items = problemListContainer.querySelectorAll(".problem-item");
        items.forEach(item => {
            item.style.opacity = "";
            const btn = item.querySelector("button.btn-primary");
            if (btn && btn.textContent === "✓") btn.textContent = "+";
        });
    };

    // 1-Click Batch Homework Apply Handler for Selected Student
    document.getElementById("btn-apply-basket")?.addEventListener("click", () => {
        if (!selectedStudentId) {
            showToast("⚠️ 먼저 우측 수강생 보드에서 숙제를 지정할 학생 카드를 클릭해 주세요!", true);
            return;
        }
        if (basket.length === 0) {
            showToast("🛒 숙제 바구니가 비어 있습니다. 카탈로그에서 문제를 선택해 담아주세요.", true);
            return;
        }
        assignBasketToStudent(selectedStudentId);
    });

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
        if (event) event.stopPropagation();
        if (basket.length === 0) {
            showToast("🛒 숙제 바구니가 비어 있습니다.", true);
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

    // === UFM (Unified Feedback Modal) Logic ===
    const ufmModal = document.getElementById("unified-feedback-modal");
    const ufmPresetSelect = document.getElementById("ufm-preset-select");
    const ufmConceptText = document.getElementById("ufm-concept-text");
    const ufmProblemSummary = document.getElementById("ufm-problem-summary");
    const ufmTeacherMemo = document.getElementById("ufm-teacher-memo");
    const ufmAiComment = document.getElementById("ufm-ai-comment");
    const ufmStudentName = document.getElementById("ufm-student-name");

    let currentUfmStudent = null;
    let currentUfmProblems = [];

    // Populate preset dropdown
    if (typeof OFFLINE_PRESETS !== "undefined" && ufmPresetSelect) {
        ufmPresetSelect.innerHTML = "";
        OFFLINE_PRESETS.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.id;
            opt.textContent = p.name;
            ufmPresetSelect.appendChild(opt);
        });
    }

    // UFM Close
    document.getElementById("btn-close-ufm")?.addEventListener("click", () => {
        ufmModal.classList.remove("show");
    });

    // Preset select change listener
    ufmPresetSelect?.addEventListener("change", () => {
        updateUfmConceptView();
    });

    function updateUfmConceptView() {
        const selectedId = ufmPresetSelect.value;
        const preset = typeof OFFLINE_PRESETS !== "undefined" ? OFFLINE_PRESETS.find(p => p.id === selectedId) : null;
        if (selectedId === "doingcoding") {
            let autoConcepts = [];
            if (typeof extractConceptDescription === "function") {
                currentUfmProblems.forEach(p => {
                    const desc = extractConceptDescription(p.title);
                    if (desc && !autoConcepts.includes(desc)) {
                        autoConcepts.push(desc);
                    }
                });
            }
            if (autoConcepts.length > 0) {
                ufmConceptText.textContent = autoConcepts.join(" / ");
            } else {
                ufmConceptText.textContent = "DoingCoding 문제 풀이 기반 학습 (자동 감지 중)";
            }
        } else if (preset) {
            ufmConceptText.textContent = preset.concept;
        }
    }

    // Override window.generateFeedback to open UFM Modal
    window.generateFeedback = async (displayId, event) => {
        if (event) event.stopPropagation();
        const student = students.find(s => s.display_id === displayId);
        currentUfmStudent = student || { display_id: displayId, name: displayId };
        ufmStudentName.textContent = currentUfmStudent.name;

        ufmTeacherMemo.value = "";
        ufmAiComment.value = "";
        ufmProblemSummary.innerHTML = "불러오는 중...";
        if (ufmPresetSelect) ufmPresetSelect.value = "doingcoding";

        ufmModal.classList.add("show");

        try {
            const res = await fetch(`/api/workspace/student_problems/${displayId}`);
            if (res.ok) {
                const data = await res.json();
                currentUfmProblems = data.problems || [];
                renderUfmProblemSummary();
                updateUfmConceptView();
            } else {
                ufmProblemSummary.innerHTML = "(오늘 풀이 내역 조회 불가)";
            }
        } catch (e) {
            ufmProblemSummary.innerHTML = "(오류 발생)";
        }
    };

    function renderUfmProblemSummary() {
        let summaryText = "";
        const solved = currentUfmProblems.filter(p => p.status === "solved").map(p => p.title);
        const wrong = currentUfmProblems.filter(p => p.status === "wrong").map(p => p.title);
        const basketTitles = basket.map(p => p.title);

        if (solved.length > 0) summaryText += `🟢 오늘 완료 (${solved.length}개): ${solved.join(", ")}<br>`;
        if (wrong.length > 0) summaryText += `🔴 오답 (${wrong.length}개): ${wrong.join(", ")}<br>`;
        if (basketTitles.length > 0) summaryText += `🛒 바구니 지정 숙제 (${basketTitles.length}개): ${basketTitles.join(", ")}`;
        
        if (!summaryText) {
            summaryText = "지정된 문항 또는 풀이 이력 없음 (오프라인 수업 선택 가능)";
        }
        ufmProblemSummary.innerHTML = summaryText;
    }

    // Copy Prompt Button
    document.getElementById("btn-copy-ufm-prompt")?.addEventListener("click", async () => {
        let summary = "";
        const selectedPresetId = ufmPresetSelect.value;
        const conceptDesc = ufmConceptText.textContent.trim();

        if (selectedPresetId !== "doingcoding") {
            const preset = OFFLINE_PRESETS.find(p => p.id === selectedPresetId);
            summary = `  * 오프라인 수업 진행: ${preset ? preset.name : "교재 수업"} (${conceptDesc})\n`;
        } else {
            const solved = currentUfmProblems.filter(p => p.status === "solved").map(p => p.title);
            const basketTitles = basket.map(p => p.title);
            if (basketTitles.length > 0) {
                summary += `  * 숙제 지정 문항 (${basketTitles.length}개): ${basketTitles.join(", ")}\n`;
            }
            if (solved.length > 0) {
                summary += `  * 오늘 학습/복습 문항 (${solved.length}개): ${solved.join(", ")}\n`;
            }
            if (!summary) summary = "  * (신규 숙제 및 지정 문항 없음)\n";
        }

        const memoVal = ufmTeacherMemo.value.trim();
        const finalMemo = memoVal || "오늘 수업에 차분하고 성실하게 임함 (특이사항 없음)";
        const fullPrompt = typeof getAiPrompt === "function" ? getAiPrompt(summary, finalMemo) : `[정보]\n- 숙제: ${summary}\n- 메모: ${finalMemo}`;

        try {
            await navigator.clipboard.writeText(fullPrompt);
            showToast("📋 AI 프롬프트가 클립보드에 복사되었습니다!\nChatGPT나 Claude에 붙여넣으세요.");
        } catch (e) {
            showToast("프롬프트 복사에 실패했습니다.", true);
        }
    });

    // Copy Parent Message (b)
    document.getElementById("btn-copy-parent-msg")?.addEventListener("click", async () => {
        const comment = ufmAiComment.value.trim();
        if (!comment) {
            showToast("⚠️ 먼저 외부 AI 답변을 붙여넣어 주세요!", true);
            return;
        }
        const text = buildFinalMessage(true);
        try {
            await navigator.clipboard.writeText(text);
            showToast("📱 학부모용 카톡 메시지가 복사되었습니다!");
        } catch (e) {
            showToast("복사 실패", true);
        }
    });

    // Copy Student Message (c) - Strips AI comment
    document.getElementById("btn-copy-student-msg")?.addEventListener("click", async () => {
        const text = buildFinalMessage(false);
        try {
            await navigator.clipboard.writeText(text);
            showToast("🎒 학생용 숙제 안내 메시지가 복사되었습니다!");
        } catch (e) {
            showToast("복사 실패", true);
        }
    });

    // Copy Excel Line (Tab Separated)
    document.getElementById("btn-copy-excel-line")?.addEventListener("click", async () => {
        const todayStr = new Date().toISOString().split("T")[0];
        const comment = ufmAiComment.value.trim() || ufmTeacherMemo.value.trim() || "성실히 임함";
        const lastProblem = basket.length > 0 ? basket[basket.length - 1].title : (currentUfmProblems.length > 0 ? currentUfmProblems[currentUfmProblems.length - 1].title : "교재/이론");
        const countVal = "1";

        const tabLine = `${todayStr}\t${countVal}\t${lastProblem}\t${comment}`;
        try {
            await navigator.clipboard.writeText(tabLine);
            showToast("📊 엑셀 1줄(날짜/회차/문제/비고) 복사 완료!\n엑셀 셀에 Ctrl+V 하세요.");
        } catch (e) {
            showToast("엑셀 복사 실패", true);
        }
    });

    // Final Save Button
    document.getElementById("btn-save-ufm-final")?.addEventListener("click", async () => {
        const comment = ufmAiComment.value.trim();
        const displayId = currentUfmStudent ? currentUfmStudent.display_id : "";
        const finalMsg = buildFinalMessage(true);

        try {
            const res = await fetch(`/api/workspace/save_homework_log`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    display_id: displayId,
                    problems: basket,
                    message: finalMsg,
                    comment: comment
                })
            });
            if (!res.ok) throw new Error("Save failed");
            
            showToast(`💾 [${currentUfmStudent.name}] 피드백 및 숙제 로그 저장 완료!`);
            ufmModal.classList.remove("show");
            basket = [];
            renderBasket();
        } catch (e) {
            showToast("저장에 실패했습니다.", true);
        }
    });

    function buildFinalMessage(includeComment = true) {
        const sName = currentUfmStudent ? currentUfmStudent.name : "학생";
        const sDisplayId = currentUfmStudent ? currentUfmStudent.display_id : "";
        const todayStr = new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" });

        let lines = [];
        lines.push("안녕하세요 두잉창의코딩학원입니다. 😊");
        lines.push(`📘 ${sName} 학생 수업 피드백`);
        lines.push(`🗓 수업일: ${todayStr}`);
        if (sDisplayId) lines.push(`👤 풀이 계정: ${sDisplayId}`);

        const basketTitles = basket.map(p => p.title);
        if (basketTitles.length > 0) {
            lines.push(`⏰ 다음 마감 숙제: ${basketTitles.join(", ")}`);
        }

        if (includeComment) {
            const comment = ufmAiComment.value.trim();
            if (comment) {
                lines.push(`📝 코멘트: ${comment}`);
            }
        }

        return lines.join("\n");
    }

    // 10. Account Management Modal Functions (P1: 1:N 계정 매핑 및 정보 관리)
    const ammModal = document.getElementById("account-manage-modal");
    const ammStudentName = document.getElementById("amm-student-name");
    const ammNameInput = document.getElementById("amm-name");
    const ammDisplayIdInput = document.getElementById("amm-display-id");
    const ammAccountsContainer = document.getElementById("amm-accounts-container");
    const btnAddAccountInput = document.getElementById("btn-add-account-input");
    const btnSaveAmmStudent = document.getElementById("btn-save-amm-student");
    const btnDeleteStudent = document.getElementById("btn-delete-student");
    const btnCloseAmm = document.getElementById("btn-close-amm");
    const btnCloseAmmCancel = document.getElementById("btn-close-amm-cancel");

    let currentEditingDisplayId = null;

    function renderAccountInputRow(accObj = {}) {
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
    }

    window.openAccountManageModal = (displayId, event) => {
        if (event) event.stopPropagation();
        const student = students.find(s => s.display_id === displayId);
        if (!student) return;

        currentEditingDisplayId = displayId;
        ammStudentName.textContent = student.name;
        ammNameInput.value = student.name;
        ammDisplayIdInput.value = student.display_id || "";
        ammAccountsContainer.innerHTML = "";

        const accounts = student.accounts && student.accounts.length > 0 ? student.accounts : [{ type: "academy", username: student.display_id }];
        accounts.forEach(acc => renderAccountInputRow(acc));

        ammModal.classList.add("show");
    };

    btnAddAccountInput?.addEventListener("click", () => {
        renderAccountInputRow({});
    });

    const closeAmmModal = () => ammModal.classList.remove("show");
    btnCloseAmm?.addEventListener("click", closeAmmModal);
    btnCloseAmmCancel?.addEventListener("click", closeAmmModal);

    btnSaveAmmStudent?.addEventListener("click", async () => {
        if (!currentEditingDisplayId) return;

        const updatedName = ammNameInput.value.trim();
        const updatedDisplayId = ammDisplayIdInput.value.trim();
        const rows = ammAccountsContainer.querySelectorAll(".amm-acc-row");
        const updatedAccounts = Array.from(rows).map(row => {
            const typeSelect = row.querySelector(".amm-acc-type");
            const inputVal = row.querySelector(".amm-acc-input");
            return {
                type: typeSelect ? typeSelect.value : "academy",
                username: inputVal ? inputVal.value.trim() : ""
            };
        }).filter(a => a.username);

        try {
            const res = await fetch("/api/workspace/update_student_accounts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    display_id: currentEditingDisplayId,
                    name: updatedName,
                    note: updatedDisplayId,
                    accounts: updatedAccounts
                })
            });

            if (!res.ok) throw new Error("Update failed");
            showToast(`[${updatedName}] 계정 연동 및 비고 메모 정보가 업데이트되었습니다.`);
            closeAmmModal();
            loadStudents(currentWeekday);
        } catch (e) {
            showToast("계정 연동 저장에 실패했습니다.", true);
        }
    });

    btnDeleteStudent?.addEventListener("click", async () => {
        if (!currentEditingDisplayId) return;
        if (!confirm(`정말로 수강생 [${ammNameInput.value}]을(를) 보드에서 삭제하시겠습니까?`)) return;

        try {
            const res = await fetch("/api/workspace/delete_student", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ display_id: currentEditingDisplayId })
            });

            if (!res.ok) throw new Error("Delete failed");
            showToast(`수강생이 삭제되었습니다.`);
            closeAmmModal();
            if (selectedStudentId === currentEditingDisplayId) selectedStudentId = null;
            loadStudents(currentWeekday);
        } catch (e) {
            showToast("수강생 삭제 실패", true);
        }
    });

    // Init
    loadCurriculums();
    loadStudents(currentWeekday);
    triggerCatalogSearch();
});
