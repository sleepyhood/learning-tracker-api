/**
 * workspace_2pane.js - Workspace 2-Pane Main Entry Point & Orchestrator
 * All feature domains have been refactored into modular components inside /static/js/modules/:
 *  - WorkspaceStudents: Student Board & Slot Management (Phase 1)
 *  - WorkspaceCatalog: Curriculum & Live Problem Search (Phase 2)
 *  - WorkspaceBasket: Homework Assignment Basket (Phase 3-1)
 *  - WorkspaceAccountModal: Domain Accounts & Notes Modal (Phase 3-2)
 *  - WorkspaceFeedbackUfm: UFM AI Feedback Generator (Phase 4-1)
 *  - WorkspaceCrawler: Problem Collector & Batch Registrar (Phase 4-2)
 *  - WorkspaceRegisterModal: Manual Student Registration Modal (Phase 5-1)
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    // 1. Initialize Sub-Modules
    if (window.WorkspaceStudents) {
        window.WorkspaceStudents.init();
        window.WorkspaceStudents.loadStudents();
    }
    if (window.WorkspaceCatalog) {
        window.WorkspaceCatalog.init();
    }
    if (window.WorkspaceBasket) {
        window.WorkspaceBasket.init();
    }
    if (window.WorkspaceAccountModal) {
        window.WorkspaceAccountModal.init();
    }
    if (window.WorkspaceFeedbackUfm) {
        window.WorkspaceFeedbackUfm.init();
    }
    if (window.WorkspaceCrawler) {
        window.WorkspaceCrawler.init();
    }
    if (window.WorkspaceRegisterModal) {
        window.WorkspaceRegisterModal.init();
    }

    // 2. Global Backward-Compatibility State & Method Wrappers
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
    Object.defineProperty(window, "curriculumsData", {
        get: () => (window.WorkspaceCatalog ? window.WorkspaceCatalog.curriculumsData : []),
        set: (val) => { if (window.WorkspaceCatalog) window.WorkspaceCatalog.curriculumsData = val; }
    });
    Object.defineProperty(window, "basket", {
        get: () => (window.WorkspaceBasket ? window.WorkspaceBasket.basket : []),
        set: (val) => { if (window.WorkspaceBasket) window.WorkspaceBasket.basket = val; }
    });

    // Delegate Functions
    window.loadStudents = (weekday = "all") => window.WorkspaceStudents && window.WorkspaceStudents.loadStudents(weekday);
    window.renderStudents = () => window.WorkspaceStudents && window.WorkspaceStudents.renderStudents();
    window.updateSlotDropdown = () => window.WorkspaceStudents && window.WorkspaceStudents.updateSlotDropdown();
    window.loadCurriculums = () => window.WorkspaceCatalog && window.WorkspaceCatalog.loadCurriculums();
    window.updateChapterDropdown = (tree) => window.WorkspaceCatalog && window.WorkspaceCatalog.updateChapterDropdown(tree);
    window.updateSubChapterDropdown = (tree) => window.WorkspaceCatalog && window.WorkspaceCatalog.updateSubChapterDropdown(tree);
    window.triggerCatalogSearch = () => window.WorkspaceCatalog && window.WorkspaceCatalog.triggerCatalogSearch();
    window.searchProblems = (q) => window.WorkspaceCatalog && window.WorkspaceCatalog.searchProblems(q);
    window.addToBasket = (problem) => window.WorkspaceBasket && window.WorkspaceBasket.addToBasket(problem);
    window.removeFromBasket = (idx) => window.WorkspaceBasket && window.WorkspaceBasket.removeFromBasket(idx);
    window.renderBasket = () => window.WorkspaceBasket && window.WorkspaceBasket.renderBasket();
    window.assignBasketToStudent = (displayId, ev) => window.WorkspaceBasket && window.WorkspaceBasket.assignBasketToStudent(displayId, ev);
    window.openAccountManageModal = (displayId, ev) => window.WorkspaceAccountModal && window.WorkspaceAccountModal.openAccountManageModal(displayId, ev);
    window.generateFeedback = (displayId, ev) => window.WorkspaceFeedbackUfm && window.WorkspaceFeedbackUfm.generateFeedback(displayId, ev);
    window.renderCurriculumManageList = () => window.WorkspaceCrawler && window.WorkspaceCrawler.renderCurriculumManageList();
    window.triggerChapterUpdate = (currKey, selectId, btnElem) => window.WorkspaceCrawler && window.WorkspaceCrawler.triggerChapterUpdate(currKey, selectId, btnElem);

    // Student selection callback bridge
    window.selectStudent = (displayId) => {
        if (window.WorkspaceStudents) {
            window.WorkspaceStudents.selectStudent(displayId);
        }
        if (window.WorkspaceBasket) {
            window.WorkspaceBasket.clearBasket();
        }
        const problemSearchInput = document.getElementById("problem-search");
        if (problemSearchInput) {
            problemSearchInput.focus();
        }
        if (window.WorkspaceCatalog) {
            window.WorkspaceCatalog.triggerCatalogSearch();
        }
    };

    // Global Toast Notification Helper
    window.showToast = function(message, isError = false) {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.textContent = message;
        toast.style.background = isError ? "var(--danger-color)" : "rgba(0,0,0,0.8)";
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 3000);
    };

    // Initial Trigger
    if (window.WorkspaceCatalog) window.WorkspaceCatalog.triggerCatalogSearch();
});
