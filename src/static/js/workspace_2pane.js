document.addEventListener("DOMContentLoaded", () => {
    // 1. Initial State
    let students = [];
    let basket = [];
    let allSlots = [];
    let selectedStudentId = null;
    let currentWeekday = "all";
    let searchDebounceTimer = null;

    // Elements
    const gridContainer = document.getElementById("student-grid-container");
    const problemListContainer = document.getElementById("problem-list-container");
    const problemSearchInput = document.getElementById("problem-search");
    const basketCount = document.getElementById("basket-count");
    const basketItemsContainer = document.getElementById("basket-items");
    const weekdayTabs = document.querySelectorAll(".tab-btn");

    // Modal Elements
    const modal = document.getElementById("register-modal");
    const btnAddStudent = document.getElementById("btn-add-student-modal");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const btnSubmitRegister = document.getElementById("btn-submit-register");
    const regSlotSelect = document.getElementById("reg-slot");

    // 2. Tab Events
    weekdayTabs.forEach(tab => {
        tab.addEventListener("click", (e) => {
            weekdayTabs.forEach(t => t.classList.remove("active"));
            e.target.classList.add("active");
            currentWeekday = e.target.getAttribute("data-weekday");
            loadStudents(currentWeekday);
        });
    });

    // 3. Load Students & Slots
    async function loadStudents(weekday = "all") {
        try {
            const res = await fetch(`/api/workspace/schedule_students?weekday=${weekday}`);
            if (!res.ok) throw new Error("Failed to load students");
            const data = await res.json();
            students = data.students || [];
            allSlots = data.all_slots || [];
            
            updateSlotDropdown();
            renderStudents();
        } catch (e) {
            showToast("수강생을 불러오는데 실패했습니다.", true);
            console.error(e);
        }
    }

    function updateSlotDropdown() {
        regSlotSelect.innerHTML = "<option value=''>슬롯을 선택하세요</option>";
        const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
        allSlots.forEach(slot => {
            let w = parseInt(slot.weekday);
            let wLabel = (w >= 0 && w <= 6) ? `${weekdays[w]}요일` : "기타/일정불확실";
            const opt = document.createElement("option");
            opt.value = slot.id;
            opt.textContent = `[${wLabel}] ${slot.label}`;
            regSlotSelect.appendChild(opt);
        });
    }

    // 4. Render Students
    function renderStudents() {
        gridContainer.innerHTML = "";
        if (students.length === 0) {
            gridContainer.innerHTML = "<div class='problem-empty-state'>선택한 요일에 해당하는 학생이 없습니다.</div>";
            return;
        }

        students.forEach(student => {
            const card = document.createElement("div");
            card.className = `student-card ${selectedStudentId === student.display_id ? 'selected' : ''}`;
            card.onclick = () => selectStudent(student.display_id);

            let badgesHTML = "";
            if (student.slot_label) {
                badgesHTML += `<span class="student-accounts" style="background: rgba(52,199,89,0.1); color: var(--success-color);">${student.slot_label}</span>`;
            }
            if (student.note) {
                badgesHTML += `<span class="student-accounts" style="background: rgba(255,149,0,0.1); color: var(--warning-color);">${student.note}</span>`;
            }

            card.innerHTML = `
                <div class="student-header">
                    <div class="student-info">
                        <span class="student-name">${student.name} <span class="student-display-id">(${student.display_id})</span></span>
                        <div style="display:flex; gap: 4px; margin-top: 4px;">${badgesHTML}</div>
                    </div>
                </div>
                <div class="student-actions" style="margin-top: 12px;">
                    <button class="btn-small btn-primary" onclick="generateFeedback('${student.display_id}', event)">✨ AI 피드백 생성</button>
                    <button class="btn-small btn-secondary" onclick="assignBasketToStudent('${student.display_id}', event)">➕ 장바구니 할당</button>
                </div>
            `;
            gridContainer.appendChild(card);
        });
    }

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

    function updateChapterDropdown() {
        if (!chapterFilterSelect) return;
        const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
        const currObj = curriculumsData.find(c => c.key === currKey);

        chapterFilterSelect.innerHTML = `<option value="all">전체 대단원 목차</option>`;
        if (subChapterFilterSelect) subChapterFilterSelect.innerHTML = `<option value="all">전체 소단원</option>`;

        if (currObj && currObj.chapters) {
            currObj.chapters.forEach(ch => {
                const opt = document.createElement("option");
                const majorName = typeof ch === "object" ? (ch.major || ch) : ch;
                if (majorName && majorName !== "undefined") {
                    opt.value = majorName;
                    opt.textContent = majorName;
                    chapterFilterSelect.appendChild(opt);
                }
            });
        }
    }

    function updateSubChapterDropdown() {
        if (!subChapterFilterSelect) return;
        const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
        const currObj = curriculumsData.find(c => c.key === currKey);
        const selectedMajor = chapterFilterSelect ? chapterFilterSelect.value : "all";

        subChapterFilterSelect.innerHTML = `<option value="all">전체 소단원</option>`;
        if (selectedMajor === "all" || !currObj || !currObj.chapters) return;

        const majorObj = currObj.chapters.find(ch => (typeof ch === "object" ? ch.major : ch) === selectedMajor);
        if (majorObj && typeof majorObj === "object" && majorObj.subs) {
            majorObj.subs.forEach(subName => {
                const opt = document.createElement("option");
                opt.value = subName;
                opt.textContent = subName;
                subChapterFilterSelect.appendChild(opt);
            });
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
            const currParam = `&curriculum=${encodeURIComponent(currKey)}`;

            const res = await fetch(`/api/workspace/search_problems?q=${encodeURIComponent(q)}&limit=80${currParam}${chapterParam}${subParam}${displayIdParam}`);
            if (!res.ok) throw new Error("search failed");
            const data = await res.json();
            const problems = data.problems || [];

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
                    <span class="problem-status-icon" style="font-size:0.72rem;color:#86868b;flex-shrink:0;min-width:80px;">${statusIcon}${p.legacy_code}</span>
                    <span class="problem-title" style="font-size:0.87rem;">${p.title}</span>
                    <button class="btn-small btn-primary" style="flex-shrink:0;padding:3px 8px;font-size:0.78rem;${isSolved ? 'background:#34c759;' : ''}" onclick="event.stopPropagation(); addToBasket(${safeP})">${inBasket ? "✓" : "+"}</button>
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
        event.stopPropagation();
        if (basket.length === 0) {
            showToast("바구니가 비어 있습니다.", true);
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

    // Init
    loadCurriculums();
    loadStudents(currentWeekday);
    triggerCatalogSearch();
});
