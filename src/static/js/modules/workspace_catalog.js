// workspace_catalog.js - 문제 카탈로그 & 라이브 검색 전용 모듈
(function(window) {
    "use strict";

    window.WorkspaceCatalog = {
        curriculumsData: [],
        lastSearchTree: {},
        selectedTag: "",
        searchDebounceTimer: null,

        init: function() {
            this.bindEvents();
            this.loadCurriculums();
        },

        bindEvents: function() {
            const curriculumSelect = document.getElementById("curriculum-select");
            const chapterFilterSelect = document.getElementById("chapter-filter-select");
            const subChapterFilterSelect = document.getElementById("sub-chapter-filter-select");
            const quickTagChips = document.querySelectorAll("#quick-tag-chips button");
            const problemSearchInput = document.getElementById("problem-search");

            curriculumSelect?.addEventListener("change", () => {
                this.updateChapterDropdown();
                this.triggerCatalogSearch();
            });

            chapterFilterSelect?.addEventListener("change", () => {
                this.updateSubChapterDropdown();
                this.triggerCatalogSearch();
            });

            subChapterFilterSelect?.addEventListener("change", () => {
                this.triggerCatalogSearch();
            });

            quickTagChips.forEach(chip => {
                chip.addEventListener("click", (e) => {
                    quickTagChips.forEach(c => {
                        c.style.background = "";
                        c.style.color = "";
                    });
                    e.target.style.background = "var(--accent-color)";
                    e.target.style.color = "white";
                    this.selectedTag = e.target.getAttribute("data-tag") || "";

                    if (this.selectedTag) {
                        if (problemSearchInput) problemSearchInput.value = this.selectedTag;
                    } else {
                        if (problemSearchInput) problemSearchInput.value = "";
                    }
                    this.triggerCatalogSearch();
                });
            });

            if (problemSearchInput) {
                problemSearchInput.addEventListener("input", () => {
                    clearTimeout(this.searchDebounceTimer);
                    this.searchDebounceTimer = setTimeout(() => {
                        this.triggerCatalogSearch();
                    }, 300);
                });
                problemSearchInput.addEventListener("keydown", (e) => {
                    if (e.key === "Enter") {
                        clearTimeout(this.searchDebounceTimer);
                        this.searchProblems(problemSearchInput.value);
                    }
                });
            }
        },

        loadCurriculums: async function() {
            try {
                const res = await fetch("/api/workspace/curriculums");
                if (!res.ok) return;
                const data = await res.json();
                this.curriculumsData = data.curriculums || [];
                this.updateChapterDropdown();
                if (typeof window.renderCurriculumManageList === "function") {
                    window.renderCurriculumManageList();
                }
            } catch (e) {
                console.error("Failed to load curriculums", e);
            }
        },

        updateChapterDropdown: function(tree = this.lastSearchTree) {
            const curriculumSelect = document.getElementById("curriculum-select");
            const chapterFilterSelect = document.getElementById("chapter-filter-select");
            const subChapterFilterSelect = document.getElementById("sub-chapter-filter-select");
            if (!chapterFilterSelect) return;

            const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
            const currObj = this.curriculumsData.find(c => c.key === currKey);
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
        },

        subTypeFilterState: "all", // "all", "regular", "homework"

        init: function() {
            this.bindEvents();
        },

        bindEvents: function() {
            const subTypeGroup = document.getElementById("sub-type-filter-group");
            subTypeGroup?.addEventListener("click", (e) => {
                const btn = e.target.closest("button");
                if (!btn) return;
                const type = btn.getAttribute("data-type") || "all";
                this.subTypeFilterState = type;

                subTypeGroup.querySelectorAll("button").forEach(b => {
                    b.style.background = "";
                    b.style.color = "";
                    b.classList.remove("active-sub-type-btn");
                });
                btn.style.background = "var(--accent-color)";
                btn.style.color = "white";
                btn.classList.add("active-sub-type-btn");

                this.updateSubChapterDropdown();
                this.triggerCatalogSearch();
            });
        },

        updateSubChapterDropdown: function(tree = this.lastSearchTree) {
            const curriculumSelect = document.getElementById("curriculum-select");
            const chapterFilterSelect = document.getElementById("chapter-filter-select");
            const subChapterFilterSelect = document.getElementById("sub-chapter-filter-select");
            if (!subChapterFilterSelect) return;

            const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
            const currObj = this.curriculumsData.find(c => c.key === currKey);
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

            const naturalCompare = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
            const isHw = (s) => /^s{1,2}/i.test(s) || s.includes("숙제") || s.includes("기출");

            let subArr = Array.from(subSet).sort(naturalCompare);

            // Filter by subTypeFilterState
            if (this.subTypeFilterState === "regular") {
                subArr = subArr.filter(s => !isHw(s));
            } else if (this.subTypeFilterState === "homework") {
                subArr = subArr.filter(s => isHw(s));
            }

            const regSubs = subArr.filter(s => !isHw(s));
            const hwSubs = subArr.filter(s => isHw(s));

            if (this.subTypeFilterState === "all" && regSubs.length > 0 && hwSubs.length > 0) {
                const gReg = document.createElement("optgroup");
                gReg.label = "📖 일반 진도 단원";
                regSubs.forEach(s => {
                    const opt = document.createElement("option");
                    opt.value = s; opt.textContent = s;
                    gReg.appendChild(opt);
                });
                subChapterFilterSelect.appendChild(gReg);

                const gHw = document.createElement("optgroup");
                gHw.label = "🛒 숙제 & 특별 단원 (S/SS)";
                hwSubs.forEach(s => {
                    const opt = document.createElement("option");
                    opt.value = s; opt.textContent = s;
                    gHw.appendChild(opt);
                });
                subChapterFilterSelect.appendChild(gHw);
            } else {
                subArr.forEach(subName => {
                    const opt = document.createElement("option");
                    opt.value = subName;
                    opt.textContent = subName;
                    subChapterFilterSelect.appendChild(opt);
                });
            }

            if (Array.from(subChapterFilterSelect.options).some(o => o.value === savedSubVal)) {
                subChapterFilterSelect.value = savedSubVal;
            }
        },

        triggerCatalogSearch: function() {
            const problemSearchInput = document.getElementById("problem-search");
            const q = problemSearchInput ? problemSearchInput.value.trim() : "";
            this.searchProblems(q);
        },

        searchProblems: async function(query) {
            let q = query.trim();
            const curriculumSelect = document.getElementById("curriculum-select");
            const chapterFilterSelect = document.getElementById("chapter-filter-select");
            const subChapterFilterSelect = document.getElementById("sub-chapter-filter-select");
            const problemListContainer = document.getElementById("problem-list-container");

            const currKey = curriculumSelect ? curriculumSelect.value : "prog1";
            const chapterVal = chapterFilterSelect ? chapterFilterSelect.value : "all";
            const subVal = subChapterFilterSelect ? subChapterFilterSelect.value : "all";

            if (q.length < 2 && chapterVal === "all" && subVal === "all" && !q) {
                q = "ALL";
            }

            if (problemListContainer) {
                problemListContainer.innerHTML = `<div class='problem-empty-state'>검색 중...</div>`;
            }

            try {
                const selectedStudentId = window.selectedStudentId || null;
                const displayIdParam = selectedStudentId ? `&display_id=${encodeURIComponent(selectedStudentId)}` : "";
                const chapterParam = chapterVal !== "all" ? `&chapter=${encodeURIComponent(chapterVal)}` : "";
                const subParam = subVal !== "all" ? `&sub=${encodeURIComponent(subVal)}` : "";
                const currParam = `&curriculum=${encodeURIComponent(currKey)}&curr=${encodeURIComponent(currKey)}`;

                const res = await fetch(`/api/workspace/search_problems?q=${encodeURIComponent(q)}&limit=80${currParam}${chapterParam}${subParam}${displayIdParam}`);
                if (!res.ok) throw new Error("search failed");
                const data = await res.json();
                const problems = data.problems || [];

                if (data.tree) {
                    this.lastSearchTree = data.tree;
                    this.updateChapterDropdown(data.tree);
                    this.updateSubChapterDropdown(data.tree);
                }

                if (problemListContainer) {
                    problemListContainer.innerHTML = "";

                    if (problems.length === 0) {
                        problemListContainer.innerHTML = `<div class='problem-empty-state'>"${query}" 검색 결과 없음</div>`;
                        return;
                    }

                    const solvedCount = problems.filter(p => p.status === "solved").length;
                    const countBadge = document.createElement("div");
                    countBadge.style.cssText = "font-size:0.78rem;color:#86868b;padding:2px 4px 8px;";
                    countBadge.innerHTML = `${problems.length}개 목록${selectedStudentId ? ` · <span style='color:#34c759'>🟢 풀이완료 ${solvedCount}개</span>` : ""}`;
                    problemListContainer.appendChild(countBadge);

                    const currentBasket = window.basket || [];
                    problems.forEach(p => {
                        const inBasket = currentBasket.find(b => b.legacy_code === p.legacy_code);
                        const isSolved = p.status === "solved";
                        const isWrong  = p.status === "wrong";
                        const isPartial = p.status === "partial";

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
                        const goalDisplay = p.learning_goal || p.learning_goal_fallback || "";
                        const goalHTML = goalDisplay ? `<div style="font-size:0.7rem; color:#64748b; margin-top:2px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="학습목표: ${goalDisplay}">💡 ${goalDisplay}</div>` : "";

                        item.innerHTML = `
                            <div style="flex:1; min-width:0;">
                                <div style="display:flex; align-items:center; gap:4px;">
                                    <span class="problem-status-icon" style="flex-shrink:0;min-width:70px;font-size:0.75rem;">${statusIcon}${p.legacy_code}</span>
                                    <span class="problem-title" style="flex:1; min-width:0;">${p.title}</span>
                                </div>
                                ${goalHTML}
                            </div>
                            <button class="btn-small btn-primary" style="flex-shrink:0;padding:2px 7px;font-size:0.75rem;border-radius:4px;${isSolved ? 'background:#34c759;' : ''}" onclick="event.stopPropagation(); addToBasket(${safeP})">${inBasket ? "✓" : "+"}</button>
                        `;
                        item.onclick = () => {
                            if (typeof window.addToBasket === "function") {
                                window.addToBasket(p);
                            }
                        };
                        problemListContainer.appendChild(item);
                    });
                }
            } catch (e) {
                if (typeof showToast === "function") {
                    showToast("문제 검색에 실패했습니다.", true);
                }
            }
        }
    };
})(window);
