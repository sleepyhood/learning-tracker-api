// workspace_crawler.js - 문제 수집 크롤러 & 엑셀 일괄 등록 & 메타데이터 관리 모듈
(function(window) {
    "use strict";

    window.WorkspaceCrawler = {
        crawlPollInterval: null,
        currentMetaProblems: [],
        currentMetaTree: {},
        isFullscreen: false,

        init: function() {
            this.bindEvents();
        },

        bindEvents: function() {
            const btnOpenCatalogManage = document.getElementById("btn-open-catalog-manage");
            const btnCloseCatalogManage = document.getElementById("btn-close-catalog-manage");
            const btnToggleCatalogFullscreen = document.getElementById("btn-toggle-catalog-fullscreen");
            const catalogManageModal = document.getElementById("catalog-manage-modal");
            const modalContent = catalogManageModal?.querySelector(".modal-content");
            const tabCatCrawl = document.getElementById("tab-cat-crawl");
            const tabCatBatch = document.getElementById("tab-cat-batch");
            const tabCatMeta = document.getElementById("tab-cat-meta");
            const manageTabContentCrawl = document.getElementById("manage-tab-content-crawl");
            const manageTabContentBatch = document.getElementById("manage-tab-content-batch");
            const manageTabContentMeta = document.getElementById("manage-tab-content-meta");
            const btnSubmitBatchAdd = document.getElementById("btn-submit-batch-add");

            const metaCurrSelect = document.getElementById("meta-curr-select");
            const metaMajorSelect = document.getElementById("meta-major-select");
            const metaSubSelect = document.getElementById("meta-sub-select");
            const chkMetaMissingOnly = document.getElementById("chk-meta-missing-only");
            const btnExportMetaTsv = document.getElementById("btn-export-meta-tsv");
            const btnImportMetaTsv = document.getElementById("btn-import-meta-tsv");
            const metaTsvImportBox = document.getElementById("meta-tsv-import-box");
            const btnCancelTsvImport = document.getElementById("btn-cancel-tsv-import");
            const btnSubmitTsvImport = document.getElementById("btn-submit-tsv-import");
            const btnSaveAllTableMeta = document.getElementById("btn-save-all-table-meta");
            const metaProblemsTableContainer = document.getElementById("meta-problems-table-container");

            btnOpenCatalogManage?.addEventListener("click", () => {
                catalogManageModal?.classList.add("show");
                if (typeof window.loadCurriculums === "function") {
                    window.loadCurriculums();
                }
                this.loadMetaTable();
            });

            btnCloseCatalogManage?.addEventListener("click", () => {
                catalogManageModal?.classList.remove("show");
            });

            // ⛶ 전체화면 토글
            btnToggleCatalogFullscreen?.addEventListener("click", () => {
                this.isFullscreen = !this.isFullscreen;
                if (modalContent) {
                    if (this.isFullscreen) {
                        modalContent.style.maxWidth = "98vw";
                        modalContent.style.width = "98vw";
                        modalContent.style.height = "94vh";
                        if (metaProblemsTableContainer) metaProblemsTableContainer.style.maxHeight = "calc(94vh - 210px)";
                        if (btnToggleCatalogFullscreen) btnToggleCatalogFullscreen.textContent = "🗗 팝업창";
                    } else {
                        modalContent.style.maxWidth = "860px";
                        modalContent.style.width = "94%";
                        modalContent.style.height = "";
                        if (metaProblemsTableContainer) metaProblemsTableContainer.style.maxHeight = "340px";
                        if (btnToggleCatalogFullscreen) btnToggleCatalogFullscreen.textContent = "⛶ 전체화면";
                    }
                }
            });

            const resetTabs = () => {
                [tabCatCrawl, tabCatBatch, tabCatMeta].forEach(t => {
                    if (t) { t.style.background = ""; t.style.color = ""; }
                });
                if (manageTabContentCrawl) manageTabContentCrawl.style.display = "none";
                if (manageTabContentBatch) manageTabContentBatch.style.display = "none";
                if (manageTabContentMeta) manageTabContentMeta.style.display = "none";
            };

            tabCatMeta?.addEventListener("click", () => {
                resetTabs();
                if (tabCatMeta) { tabCatMeta.style.background = "var(--accent-color)"; tabCatMeta.style.color = "white"; }
                if (manageTabContentMeta) manageTabContentMeta.style.display = "flex";
                this.loadMetaTable(metaCurrSelect?.value || "prog1");
            });

            tabCatCrawl?.addEventListener("click", () => {
                resetTabs();
                if (tabCatCrawl) { tabCatCrawl.style.background = "var(--accent-color)"; tabCatCrawl.style.color = "white"; }
                if (manageTabContentCrawl) manageTabContentCrawl.style.display = "flex";
            });

            tabCatBatch?.addEventListener("click", () => {
                resetTabs();
                if (tabCatBatch) { tabCatBatch.style.background = "var(--accent-color)"; tabCatBatch.style.color = "white"; }
                if (manageTabContentBatch) manageTabContentBatch.style.display = "flex";
            });

            const metaSubTypeGroup = document.getElementById("meta-sub-type-filter-group");
            metaSubTypeGroup?.addEventListener("click", (e) => {
                const btn = e.target.closest("button");
                if (!btn) return;
                const type = btn.getAttribute("data-type") || "all";
                this.metaSubTypeFilterState = type;

                metaSubTypeGroup.querySelectorAll("button").forEach(b => {
                    b.style.background = "";
                    b.style.color = "";
                    b.classList.remove("active-meta-sub-type-btn");
                });
                btn.style.background = "var(--accent-color)";
                btn.style.color = "white";
                btn.classList.add("active-meta-sub-type-btn");

                this.updateMetaSubDropdown(metaMajorSelect?.value || "all");
                this.loadMetaTable(metaCurrSelect?.value || "prog1", metaMajorSelect?.value || "all", metaSubSelect?.value || "all");
            });

            metaCurrSelect?.addEventListener("change", () => {
                this.loadMetaTable(metaCurrSelect.value, "all", "all");
            });

            metaMajorSelect?.addEventListener("change", () => {
                this.updateMetaSubDropdown(metaMajorSelect.value);
                this.loadMetaTable(metaCurrSelect?.value || "prog1", metaMajorSelect.value, "all");
            });

            metaSubSelect?.addEventListener("change", () => {
                this.loadMetaTable(metaCurrSelect?.value || "prog1", metaMajorSelect?.value || "all", metaSubSelect.value);
            });

            chkMetaMissingOnly?.addEventListener("change", () => {
                this.renderMetaTable();
            });

            btnExportMetaTsv?.addEventListener("click", async () => {
                let tsvText = "ID\t학습목표\t개념\t과정/단원\n";
                this.currentMetaProblems.forEach(p => {
                    const goal = p.learning_goal || p.learning_goal_fallback || "";
                    tsvText += `${p.id}\t${goal}\t${p.concept || ""}\t[${p.major}] ${p.sub}\n`;
                });
                try {
                    await navigator.clipboard.writeText(tsvText);
                    if (typeof showToast === "function") {
                        showToast("📋 엑셀 붙여넣기용 TSV 텍스트가 클립보드에 복사되었습니다!\n엑셀 셀에 Ctrl+V 하세요.");
                    }
                } catch (e) {
                    if (typeof showToast === "function") showToast("복사 실패", true);
                }
            });

            btnImportMetaTsv?.addEventListener("click", () => {
                if (metaTsvImportBox) {
                    metaTsvImportBox.style.display = metaTsvImportBox.style.display === "none" ? "block" : "none";
                }
            });

            btnCancelTsvImport?.addEventListener("click", () => {
                if (metaTsvImportBox) metaTsvImportBox.style.display = "none";
            });

            btnSubmitTsvImport?.addEventListener("click", async () => {
                const rawText = document.getElementById("meta-tsv-text")?.value || "";
                if (!rawText.trim()) {
                    if (typeof showToast === "function") showToast("붙여넣을 TSV 텍스트를 입력하세요.", true);
                    return;
                }

                try {
                    const res = await fetch("/api/workspace/import_problem_metadata", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ raw_text: rawText })
                    });
                    const data = await res.json();
                    if (data.ok) {
                        if (typeof showToast === "function") showToast(`✅ ${data.updated_count}개 문제의 학습목표가 업데이트되었습니다!`);
                        if (metaTsvImportBox) metaTsvImportBox.style.display = "none";
                        const textElem = document.getElementById("meta-tsv-text");
                        if (textElem) textElem.value = "";
                        this.loadMetaTable(metaCurrSelect?.value || "prog1", metaMajorSelect?.value || "all", metaSubSelect?.value || "all");
                    } else {
                        if (typeof showToast === "function") showToast(`❌ ${data.error || "적용 실패"}`, true);
                    }
                } catch (e) {
                    if (typeof showToast === "function") showToast("일괄 적용 중 오류가 발생했습니다.", true);
                }
            });

            btnSaveAllTableMeta?.addEventListener("click", async () => {
                const container = document.getElementById("meta-problems-table-container");
                if (!container) return;
                const rows = container.querySelectorAll(".meta-prob-row");
                const itemsToSave = [];

                rows.forEach(row => {
                    const pid = row.getAttribute("data-pid");
                    const goalInput = row.querySelector(".meta-goal-input");
                    const conceptInput = row.querySelector(".meta-concept-input");
                    if (pid && goalInput) {
                        itemsToSave.push({
                            id: pid,
                            learning_goal: goalInput.value.trim(),
                            concept: conceptInput ? conceptInput.value.trim() : ""
                        });
                    }
                });

                if (itemsToSave.length === 0) return;

                try {
                    const res = await fetch("/api/workspace/update_problem_metadata", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ problems: itemsToSave })
                    });
                    const data = await res.json();
                    if (data.ok) {
                        if (typeof showToast === "function") showToast(`💾 ${data.updated_count}개 문제 학습목표 저장 완료!`);
                        this.loadMetaTable(metaCurrSelect?.value || "prog1", metaMajorSelect?.value || "all", metaSubSelect?.value || "all");
                    } else {
                        if (typeof showToast === "function") showToast("저장 실패", true);
                    }
                } catch (e) {
                    if (typeof showToast === "function") showToast("저장 중 오류 발생", true);
                }
            });

            btnSubmitBatchAdd?.addEventListener("click", async () => {
                this.submitBatchAdd();
            });
        },

        metaSubTypeFilterState: "all", // "all", "regular", "homework"

        updateMetaMajorDropdown: function(tree) {
            const metaMajorSelect = document.getElementById("meta-major-select");
            if (!metaMajorSelect) return;
            const currentVal = metaMajorSelect.value || "all";

            metaMajorSelect.innerHTML = `<option value="all">전체 대단원 목차</option>`;
            if (!tree) return;

            Object.keys(tree).forEach(majName => {
                const opt = document.createElement("option");
                opt.value = majName;
                opt.textContent = majName;
                metaMajorSelect.appendChild(opt);
            });

            if (Array.from(metaMajorSelect.options).some(o => o.value === currentVal)) {
                metaMajorSelect.value = currentVal;
            }
        },

        updateMetaSubDropdown: function(selectedMajor = "all") {
            const metaSubSelect = document.getElementById("meta-sub-select");
            if (!metaSubSelect) return;
            const currentSubVal = metaSubSelect.value || "all";

            metaSubSelect.innerHTML = `<option value="all">전체 소단원</option>`;
            if (selectedMajor === "all" || !this.currentMetaTree[selectedMajor]) return;

            let subs = this.currentMetaTree[selectedMajor] || [];
            const naturalCompare = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
            const isHw = (s) => /^s{1,2}/i.test(s) || s.includes("숙제") || s.includes("기출");

            subs = subs.slice().sort(naturalCompare);

            if (this.metaSubTypeFilterState === "regular") {
                subs = subs.filter(s => !isHw(s));
            } else if (this.metaSubTypeFilterState === "homework") {
                subs = subs.filter(s => isHw(s));
            }

            const regSubs = subs.filter(s => !isHw(s));
            const hwSubs = subs.filter(s => isHw(s));

            if (this.metaSubTypeFilterState === "all" && regSubs.length > 0 && hwSubs.length > 0) {
                const gReg = document.createElement("optgroup");
                gReg.label = "📖 일반 진도 단원";
                regSubs.forEach(s => {
                    const opt = document.createElement("option"); opt.value = s; opt.textContent = s;
                    gReg.appendChild(opt);
                });
                metaSubSelect.appendChild(gReg);

                const gHw = document.createElement("optgroup");
                gHw.label = "🛒 숙제 & 특별 단원 (S/SS)";
                hwSubs.forEach(s => {
                    const opt = document.createElement("option"); opt.value = s; opt.textContent = s;
                    gHw.appendChild(opt);
                });
                metaSubSelect.appendChild(gHw);
            } else {
                subs.forEach(subName => {
                    const opt = document.createElement("option");
                    opt.value = subName;
                    opt.textContent = subName;
                    metaSubSelect.appendChild(opt);
                });
            }

            if (Array.from(metaSubSelect.options).some(o => o.value === currentSubVal)) {
                metaSubSelect.value = currentSubVal;
            }
        },

        loadMetaTable: async function(currKey = "prog1", majorVal = "all", subVal = "all") {
            const container = document.getElementById("meta-problems-table-container");
            if (container) container.innerHTML = "<div style='padding:12px; font-size:0.85rem; color:#64748b;'>불러오는 중...</div>";

            try {
                const res = await fetch(`/api/workspace/export_problem_metadata?curr=${currKey}&major=${encodeURIComponent(majorVal)}&sub=${encodeURIComponent(subVal)}`);
                if (!res.ok) throw new Error("Load meta failed");
                const data = await res.json();
                this.currentMetaProblems = data.problems || [];
                if (data.tree) {
                    this.currentMetaTree = data.tree;
                    this.updateMetaMajorDropdown(data.tree);
                    this.updateMetaSubDropdown(majorVal);
                }
                this.renderMetaTable();
            } catch (e) {
                if (container) container.innerHTML = "<div style='padding:12px; font-size:0.85rem; color:red;'>불러오기 실패</div>";
            }
        },

        renderMetaTable: function() {
            const container = document.getElementById("meta-problems-table-container");
            const chkMissingOnly = document.getElementById("chk-meta-missing-only");
            if (!container) return;

            let problems = this.currentMetaProblems;
            if (chkMissingOnly && chkMissingOnly.checked) {
                problems = problems.filter(p => !p.learning_goal);
            }

            if (problems.length === 0) {
                container.innerHTML = "<div style='padding:16px; text-align:center; font-size:0.85rem; color:#94a3b8;'>해당하는 문제 항목이 없습니다.</div>";
                return;
            }

            let html = `
                <table style="width:100%; border-collapse:collapse; font-size:0.8rem; text-align:left;">
                    <thead>
                        <tr style="background:#f1f5f9; border-bottom:1px solid var(--panel-border);">
                            <th style="padding:6px 8px; width:90px;">문제 ID</th>
                            <th style="padding:6px 8px; width:130px;">단원</th>
                            <th style="padding:6px 8px; width:160px;">문제 제목</th>
                            <th style="padding:6px 8px;">💡 학습 목표 (인라인 편집 가능)</th>
                            <th style="padding:6px 8px; width:110px;">개념</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            problems.forEach(p => {
                const goalVal = p.learning_goal || "";
                const placeholderVal = p.learning_goal_fallback ? `자동상속: ${p.learning_goal_fallback}` : "학습목표 입력...";
                html += `
                    <tr class="meta-prob-row" data-pid="${p.id}" style="border-bottom:1px solid #e2e8f0;">
                        <td style="padding:6px 8px; font-weight:700; font-family:monospace; color:#334155;">${p.id}</td>
                        <td style="padding:6px 8px; color:#64748b;">${p.sub || p.major}</td>
                        <td style="padding:6px 8px; font-weight:600; color:#1e293b;">${p.title}</td>
                        <td style="padding:4px 6px;">
                            <input type="text" class="meta-goal-input" value="${goalVal}" placeholder="${placeholderVal}" style="width:100%; padding:4px 6px; font-size:0.8rem; border:1px solid var(--panel-border); border-radius:4px; ${!goalVal ? 'background:#fffbebf0;' : ''}">
                        </td>
                        <td style="padding:4px 6px;">
                            <input type="text" class="meta-concept-input" value="${p.concept || ''}" placeholder="개념" style="width:100%; padding:4px 6px; font-size:0.8rem; border:1px solid var(--panel-border); border-radius:4px;">
                        </td>
                    </tr>
                `;
            });

            html += `</tbody></table>`;
            container.innerHTML = html;
        },

        renderCurriculumManageList: function() {
            const curriculumManageList = document.getElementById("curriculum-manage-list");
            if (!curriculumManageList) return;
            curriculumManageList.innerHTML = "";

            const curriculumsData = window.curriculumsData || [];
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
                    <div style="display:flex; justify-space-between; align-items:center;">
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
        },

        startCrawlProgressPolling: function() {
            if (this.crawlPollInterval) clearInterval(this.crawlPollInterval);
            this.crawlPollInterval = setInterval(async () => {
                try {
                    const res = await fetch("/api/workspace/crawl_status");
                    if (!res.ok) return;
                    const data = await res.json();
                    if (data.ok && data.status) {
                        const st = data.status;
                        if (st.active) {
                            const pctStr = st.percent > 0 ? ` (${st.percent}%)` : "";
                            const stepStr = st.total_steps > 0 ? `[${st.current_step}/${st.total_steps}] ` : "";
                            if (typeof showToast === "function") {
                                showToast(`⏳ ${stepStr}${st.current_name || st.message}${pctStr}`);
                            }
                        } else if (st.percent === 100) {
                            clearInterval(this.crawlPollInterval);
                            this.crawlPollInterval = null;
                        }
                    }
                } catch (e) {}
            }, 1000);
        },

        triggerChapterUpdate: async function(currKey, selectId, btnElem) {
            const selectElem = document.getElementById(selectId);
            const chapterVal = selectElem ? selectElem.value : "all";
            const chapterLabel = selectElem && selectElem.selectedIndex >= 0 ? selectElem.options[selectElem.selectedIndex].text : "전체";

            const originalText = btnElem ? btnElem.textContent : "🔄 선택 갱신";
            if (btnElem) {
                btnElem.disabled = true;
                btnElem.textContent = "갱신 중...";
            }

            if (typeof showToast === "function") {
                showToast(`🚀 ${chapterLabel} 문제 목록 갱신을 시작합니다...`);
            }
            this.startCrawlProgressPolling();

            try {
                let res, data;
                if (currKey === "prog1" && chapterVal !== "all") {
                    res = await fetch("/update_problems", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ chapter: chapterVal })
                    });
                } else {
                    res = await fetch("/api/workspace/trigger_crawl", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ curriculum_key: currKey, chapter: chapterVal })
                    });
                }

                data = await res.json().catch(() => ({}));
                if (res.ok && (data.ok || data.message)) {
                    if (typeof showToast === "function") {
                        showToast(`✅ ${data.message || `${chapterLabel} 문제 목록을 갱신했습니다.`}`);
                    }
                    if (typeof window.loadCurriculums === "function") await window.loadCurriculums();
                    if (typeof window.triggerCatalogSearch === "function") window.triggerCatalogSearch();
                } else {
                    if (typeof showToast === "function") {
                        showToast(`❌ ${data.error || "갱신에 실패했습니다."}`, true);
                    }
                }
            } catch (e) {
                if (typeof showToast === "function") {
                    showToast("요청 중 오류가 발생했습니다.", true);
                }
            } finally {
                if (this.crawlPollInterval) {
                    clearInterval(this.crawlPollInterval);
                    this.crawlPollInterval = null;
                }
                if (btnElem) {
                    btnElem.disabled = false;
                    btnElem.textContent = originalText;
                }
            }
        },

        submitBatchAdd: async function() {
            const catalogManageModal = document.getElementById("catalog-manage-modal");
            const currKey = document.getElementById("batch-curr-select")?.value || "prog1";
            const major = document.getElementById("batch-major-input")?.value || "기타 단원";
            const sub = document.getElementById("batch-sub-input")?.value || "일반";
            const rawText = document.getElementById("batch-raw-text")?.value || "";

            if (!rawText.trim()) {
                if (typeof showToast === "function") {
                    showToast("붙여넣을 문제 텍스트를 입력하세요.", true);
                }
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
                    if (typeof showToast === "function") {
                        showToast("✅ " + data.message);
                    }
                    const rawElem = document.getElementById("batch-raw-text");
                    if (rawElem) rawElem.value = "";
                    catalogManageModal?.classList.remove("show");
                    if (typeof window.loadCurriculums === "function") await window.loadCurriculums();
                    if (typeof window.triggerCatalogSearch === "function") window.triggerCatalogSearch();
                } else {
                    if (typeof showToast === "function") {
                        showToast("❌ " + (data.error || "일괄 등록 실패"), true);
                    }
                }
            } catch (e) {
                if (typeof showToast === "function") {
                    showToast("일괄 등록 중 오류가 발생했습니다.", true);
                }
            }
        }
    };
})(window);

