/**
 * seating_map.js - 좌석별 체류 시간 시각화 & 그리드 커스텀 모듈
 * (타임라인 시간대 슬라이더, 빈자리/체류중 실시간 시각화 & 타임라인 자동재생 지원)
 */

(function () {
  'use strict';

  // Global State
  let currentDate = new Date().toISOString().split('T')[0];
  let isEditMode = false;
  let layout = { rows: 8, cols: 7, cells: [] };
  let sessions = {};
  let studentsList = [];
  let currentTargetSeat = null;
  let currentEditCell = null;
  let activeAssignTab = 'auto';
  let selectedStudentObj = null;
  let editingSessionId = null;

  // Time Filter State
  let filterTimeMode = 'all'; // 'all' or 'specific'
  let filterMins = 840; // 14:00 default in minutes
  let animationInterval = null;

  // Time Slots (30-min increments from 13:00 to 22:00)
  const TIME_SLOTS = [];
  for (let h = 13; h <= 21; h++) {
    const hStr = h < 10 ? '0' + h : '' + h;
    TIME_SLOTS.push(`${hStr}:00`);
    TIME_SLOTS.push(`${hStr}:30`);
  }

  // DOM Elements
  const datePicker = document.getElementById('datePicker');
  const btnToggleEdit = document.getElementById('btnToggleEdit');
  const editToolbar = document.getElementById('editToolbar');
  const inputRows = document.getElementById('inputRows');
  const inputCols = document.getElementById('inputCols');
  const btnApplyGridSize = document.getElementById('btnApplyGridSize');
  const btnResetDefaultLayout = document.getElementById('btnResetDefaultLayout');
  const seatingCanvas = document.getElementById('seatingCanvas');
  const seatCountMeta = document.getElementById('seatCountMeta');
  const btnCopyLayoutSummary = document.getElementById('btnCopyLayoutSummary');

  // Time Slider Elements
  const timeSlider = document.getElementById('timeSlider');
  const sliderTimeBadge = document.getElementById('sliderTimeBadge');
  const btnTimeModeAll = document.getElementById('btnTimeModeAll');
  const btnTimeModeNow = document.getElementById('btnTimeModeNow');
  const btnPlayTimeAnimation = document.getElementById('btnPlayTimeAnimation');

  // Import / Export Elements
  const btnExportJson = document.getElementById('btnExportJson');
  const btnExportCsv = document.getElementById('btnExportCsv');
  const btnImportJson = document.getElementById('btnImportJson');
  const jsonFileInput = document.getElementById('jsonFileInput');

  // Analytics Elements
  const chipTotalOccupied = document.getElementById('chipTotalOccupied');
  const chipAttentionCount = document.getElementById('chipAttentionCount');
  const chipAvgDuration = document.getElementById('chipAvgDuration');
  const timelineHeadRow = document.getElementById('timelineHeadRow');
  const timelineBody = document.getElementById('timelineBody');

  // Assign Modal Elements
  const assignModal = document.getElementById('assignModal');
  const modalSeatTitle = document.getElementById('modalSeatTitle');
  const assignedSessionsWrap = document.getElementById('assignedSessionsWrap');
  const assignedSessionsList = document.getElementById('assignedSessionsList');
  const btnAddNewSessionSlot = document.getElementById('btnAddNewSessionSlot');
  const conflictWarningBox = document.getElementById('conflictWarningBox');
  const btnCloseAssignModal = document.getElementById('btnCloseAssignModal');
  const btnCancelAssign = document.getElementById('btnCancelAssign');
  const selectStudent = document.getElementById('selectStudent');
  const studentSearchInput = document.getElementById('studentSearchInput');
  const selectStudentVal = document.getElementById('selectStudentVal');
  const studentSearchResults = document.getElementById('studentSearchResults');
  const selectedStudentBadge = document.getElementById('selectedStudentBadge');
  const selectedStudentText = document.getElementById('selectedStudentText');
  const btnUnselectStudent = document.getElementById('btnUnselectStudent');

  const inputManualName = document.getElementById('inputManualName');
  const inputStartTime = document.getElementById('inputStartTime');
  const btnSetNowTime = document.getElementById('btnSetNowTime');
  const inputDurationHours = document.getElementById('inputDurationHours');
  const inputMemo = document.getElementById('inputMemo');
  const btnSaveAssignment = document.getElementById('btnSaveAssignment');
  const btnClearAssignment = document.getElementById('btnClearAssignment');

  // Cell Editor Modal Elements
  const cellEditorModal = document.getElementById('cellEditorModal');
  const btnCloseCellModal = document.getElementById('btnCloseCellModal');
  const cellTypeSelect = document.getElementById('cellTypeSelect');
  const cellLabelInput = document.getElementById('cellLabelInput');
  const btnSaveCellProps = document.getElementById('btnSaveCellProps');
  const btnClearCellModalBtn = document.getElementById('btnClearCellModalBtn');

  // Helper: Minutes <-> Time String Conversion
  function minsToTimeStr(mins) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    const hStr = h < 10 ? '0' + h : '' + h;
    const mStr = m < 10 ? '0' + m : '' + m;
    return `${hStr}:${mStr}`;
  }

  function timeStrToMins(timeStr) {
    try {
      const parts = timeStr.trim().split(':');
      return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
    } catch (e) {
      return 14 * 60;
    }
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    datePicker.value = currentDate;
    initTimelineHead();
    bindEvents();
    fetchSeatingData();
  });

  function initTimelineHead() {
    timelineHeadRow.innerHTML = '<th style="width:110px; text-align:left; padding-left:8px;">좌석 & 수강생</th>';
    TIME_SLOTS.forEach(slot => {
      const th = document.createElement('th');
      th.textContent = slot;
      th.dataset.timeSlot = slot;
      timelineHeadRow.appendChild(th);
    });
  }

  function bindEvents() {
    datePicker.addEventListener('change', (e) => {
      currentDate = e.target.value;
      fetchSeatingData();
    });

    btnToggleEdit.addEventListener('click', () => {
      isEditMode = !isEditMode;
      if (isEditMode) {
        btnToggleEdit.classList.add('btn-edit-active');
        btnToggleEdit.innerHTML = '✅ 편집 완료';
        editToolbar.classList.add('is-active');
      } else {
        btnToggleEdit.classList.remove('btn-edit-active');
        btnToggleEdit.innerHTML = '🛠️ 좌석 구조 편집';
        editToolbar.classList.remove('is-active');
      }
      renderCanvas();
    });

    btnApplyGridSize.addEventListener('click', () => {
      const newRows = parseInt(inputRows.value, 10) || 8;
      const newCols = parseInt(inputCols.value, 10) || 7;
      updateGridDimensions(newRows, newCols);
    });

    btnResetDefaultLayout.addEventListener('click', () => {
      if (confirm('기존 아스키 아트 교실 기본 배치로 복원하시겠습니까?')) {
        resetLayoutToDefault();
      }
    });

    // Time Slider Event Listeners
    if (timeSlider) {
      timeSlider.addEventListener('input', (e) => {
        stopTimeAnimation();
        filterTimeMode = 'specific';
        filterMins = parseInt(e.target.value, 10);
        updateSliderBadge();
        renderCanvas();
        renderTimeline();
        renderAnalytics();
      });
    }

    if (btnTimeModeAll) {
      btnTimeModeAll.addEventListener('click', () => {
        stopTimeAnimation();
        filterTimeMode = 'all';
        updateSliderBadge();
        renderCanvas();
        renderTimeline();
        renderAnalytics();
      });
    }

    if (btnTimeModeNow) {
      btnTimeModeNow.addEventListener('click', () => {
        stopTimeAnimation();
        filterTimeMode = 'specific';
        const now = new Date();
        const currentMins = now.getHours() * 60 + (now.getMinutes() < 30 ? 0 : 30);
        filterMins = Math.max(600, Math.min(1320, currentMins));
        if (timeSlider) timeSlider.value = filterMins;
        updateSliderBadge();
        renderCanvas();
        renderTimeline();
        renderAnalytics();
      });
    }

    if (btnPlayTimeAnimation) {
      btnPlayTimeAnimation.addEventListener('click', toggleTimeAnimation);
    }

    // Student Live Search Autocomplete Events
    if (studentSearchInput) {
      studentSearchInput.addEventListener('focus', () => {
        filterAndShowStudentResults(studentSearchInput.value);
      });
      studentSearchInput.addEventListener('input', (e) => {
        filterAndShowStudentResults(e.target.value);
      });
    }

    if (btnUnselectStudent) {
      btnUnselectStudent.addEventListener('click', clearSelectedStudentBadge);
    }

    // Hide search results dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (studentSearchResults && !e.target.closest('.student-autocomplete-wrap')) {
        studentSearchResults.classList.remove('is-open');
      }
    });

    // Copy Summary
    if (btnCopyLayoutSummary) {
      btnCopyLayoutSummary.addEventListener('click', copyLayoutSummary);
    }

    // Export & Import
    if (btnExportJson) btnExportJson.addEventListener('click', exportJson);
    if (btnExportCsv) btnExportCsv.addEventListener('click', exportCsv);
    if (btnImportJson && jsonFileInput) {
      btnImportJson.addEventListener('click', () => jsonFileInput.click());
      jsonFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          importJsonFile(e.target.files[0]);
          e.target.value = '';
        }
      });
    }

    // Now Time Button
    if (btnSetNowTime) {
      btnSetNowTime.addEventListener('click', () => {
        const now = new Date();
        const h = now.getHours().toString().padStart(2, '0');
        const m = now.getMinutes() < 30 ? '00' : '30';
        inputStartTime.value = `${h}:${m}`;
      });
    }

    // Assign Modal Close & Reset
    if (btnAddNewSessionSlot) {
      btnAddNewSessionSlot.addEventListener('click', () => {
        resetAssignModalForm();
        studentSearchInput.focus();
      });
    }

    btnCloseAssignModal.addEventListener('click', closeAssignModal);
    btnCancelAssign.addEventListener('click', closeAssignModal);

    // Save Assignment
    btnSaveAssignment.addEventListener('click', saveAssignment);
    btnClearAssignment.addEventListener('click', clearAllAssignmentsOnSeat);

    // Cell Editor Modal Close & Save & Clear
    btnCloseCellModal.addEventListener('click', closeCellModal);
    btnSaveCellProps.addEventListener('click', saveCellProps);
    if (btnClearCellModalBtn) {
      btnClearCellModalBtn.addEventListener('click', clearCellProps);
    }
  }

  function updateSliderBadge() {
    if (!sliderTimeBadge) return;
    if (filterTimeMode === 'all') {
      sliderTimeBadge.textContent = '모든 시간대 (종합 요약)';
      sliderTimeBadge.style.background = 'var(--accent-soft)';
      sliderTimeBadge.style.borderColor = 'var(--accent)';
      sliderTimeBadge.style.color = 'var(--accent)';
    } else {
      const timeStr = minsToTimeStr(filterMins);
      sliderTimeBadge.textContent = `⏱️ ${timeStr} 좌석 점유 탐색 중`;
      sliderTimeBadge.style.background = 'rgba(16, 185, 129, 0.2)';
      sliderTimeBadge.style.borderColor = 'var(--green)';
      sliderTimeBadge.style.color = '#6ee7b7';
    }
  }

  function toggleTimeAnimation() {
    if (animationInterval) {
      stopTimeAnimation();
    } else {
      filterTimeMode = 'specific';
      btnPlayTimeAnimation.innerHTML = '⏹️ 재생 중지';
      btnPlayTimeAnimation.classList.add('btn-danger');

      animationInterval = setInterval(() => {
        filterMins += 30;
        if (filterMins > 1320) {
          filterMins = 600; // Loop back to 10:00
        }
        if (timeSlider) timeSlider.value = filterMins;
        updateSliderBadge();
        renderCanvas();
        renderTimeline();
        renderAnalytics();
      }, 700);
    }
  }

  function stopTimeAnimation() {
    if (animationInterval) {
      clearInterval(animationInterval);
      animationInterval = null;
    }
    if (btnPlayTimeAnimation) {
      btnPlayTimeAnimation.innerHTML = '▶️ 타임라인 재생';
      btnPlayTimeAnimation.classList.remove('btn-danger');
    }
  }

  // Fetch API
  function fetchSeatingData() {
    fetch(`/api/seating?date=${currentDate}`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          layout = data.layout || { rows: 8, cols: 7, cells: [] };
          
          const rawSessions = data.sessions || {};
          sessions = {};
          Object.keys(rawSessions).forEach(seat => {
            const item = rawSessions[seat];
            if (Array.isArray(item)) {
              sessions[seat] = item;
            } else if (typeof item === 'object' && item !== null) {
              sessions[seat] = [item];
            } else {
              sessions[seat] = [];
            }
          });

          const rawStudents = data.students || {};
          if (Array.isArray(rawStudents)) {
            studentsList = rawStudents;
          } else if (typeof rawStudents === 'object' && rawStudents !== null) {
            studentsList = Object.values(rawStudents);
          } else {
            studentsList = [];
          }

          inputRows.value = layout.rows;
          inputCols.value = layout.cols;

          populateStudentDropdown();
          renderCanvas();
          renderTimeline();
          renderAnalytics();
        }
      })
      .catch(err => console.error('[Seating] Fetch error:', err));
  }

  function populateStudentDropdown() {
    if (!selectStudent) return;
    selectStudent.innerHTML = '<option value="">-- 수강생 선택 --</option>';
    studentsList.forEach(st => {
      if (!st) return;
      const opt = document.createElement('option');
      opt.value = st.user_uuid || st.username || st.name || '';
      const displayTag = st.username ? `@${st.username}` : (st.display_id ? `@${st.display_id}` : '');
      opt.textContent = `${st.name || '미상'} ${displayTag}`.trim();
      opt.dataset.name = st.name || st.display_id || '미상';
      selectStudent.appendChild(opt);
    });
  }

  // --- Student Live Search Autocomplete Logic ---
  function filterAndShowStudentResults(queryText) {
    if (!studentSearchResults) return;

    const query = (queryText || '').trim().toLowerCase();
    const matches = studentsList.filter(st => {
      if (!st) return false;
      const name = (st.name || '').toLowerCase();
      const username = (st.username || '').toLowerCase();
      const displayId = (st.display_id || '').toLowerCase();
      return !query || name.includes(query) || username.includes(query) || displayId.includes(query);
    });

    studentSearchResults.innerHTML = '';
    if (matches.length === 0) {
      studentSearchResults.innerHTML = '<div class="search-result-item" style="color:var(--muted); cursor:default;">일치하는 수강생이 없습니다.</div>';
    } else {
      matches.slice(0, 15).forEach(st => {
        const item = document.createElement('div');
        item.className = 'search-result-item';
        const displayTag = st.username ? `@${st.username}` : (st.display_id ? `@${st.display_id}` : '');
        item.innerHTML = `
          <span style="font-weight:700;">${st.name || '이름없음'}</span>
          <span style="font-size:0.75rem; color:var(--muted);">${displayTag}</span>
        `;
        item.addEventListener('click', () => {
          selectStudentItem(st);
        });
        studentSearchResults.appendChild(item);
      });
    }

    studentSearchResults.classList.add('is-open');
  }

  function selectStudentItem(st) {
    selectedStudentObj = st;
    const stId = st.user_uuid || st.username || st.name || '';
    const stName = st.name || st.display_id || '미상';
    const displayTag = st.username ? `@${st.username}` : (st.display_id ? `@${st.display_id}` : '');

    selectStudentVal.value = stId;
    if (selectStudent) selectStudent.value = stId;

    selectedStudentText.textContent = `✅ ${stName} (${displayTag})`;
    selectedStudentBadge.style.display = 'flex';

    studentSearchInput.value = '';
    studentSearchResults.classList.remove('is-open');
  }

  function clearSelectedStudentBadge() {
    selectedStudentObj = null;
    selectStudentVal.value = '';
    if (selectStudent) selectStudent.value = '';
    selectedStudentBadge.style.display = 'none';
    studentSearchInput.value = '';
    studentSearchInput.focus();
  }

  // --- Render 2D Canvas with Time Filter (Vacant vs Occupied) ---
  function renderCanvas() {
    seatingCanvas.style.gridTemplateColumns = `repeat(${layout.cols}, minmax(110px, 1fr))`;
    seatingCanvas.innerHTML = '';
    if (isEditMode) {
      seatingCanvas.classList.add('edit-mode');
    } else {
      seatingCanvas.classList.remove('edit-mode');
    }

    const cellMap = {};
    (layout.cells || []).forEach(c => {
      cellMap[`${c.r}_${c.c}`] = c;
    });

    let seatCount = 0;
    let occupiedAtFilterTimeCount = 0;

    for (let r = 0; r < layout.rows; r++) {
      for (let c = 0; c < layout.cols; c++) {
        const cellKey = `${r}_${c}`;
        const cellData = cellMap[cellKey] || { r, c, type: 'aisle', label: '' };

        const div = document.createElement('div');
        div.className = `seat-cell cell-type-${cellData.type}`;
        div.dataset.row = r;
        div.dataset.col = c;

        if (isEditMode && cellData.type !== 'aisle') {
          const deleteBtn = document.createElement('span');
          deleteBtn.className = 'cell-delete-btn';
          deleteBtn.innerHTML = '✕';
          deleteBtn.title = '삭제 (통로로 변환)';
          deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            quickDeleteCell(r, c);
          });
          div.appendChild(deleteBtn);
        }

        if (cellData.type === 'seat') {
          seatCount++;
          const label = cellData.label || `STD_${r}_${c}`;
          const seatSessions = sessions[label] || [];

          if (filterTimeMode === 'specific') {
            // Check if any student is occupying at filterMins
            const activeSess = seatSessions.find(sess => {
              const startM = timeStrToMins(sess.start_time || '14:00');
              const durM = Math.round(parseFloat(sess.duration_hours || 1.5) * 60);
              return startM <= filterMins && filterMins < (startM + durM);
            });

            if (activeSess) {
              occupiedAtFilterTimeCount++;
              const statusClass = `status-${activeSess.help_status || 'normal'}`;
              div.classList.add(statusClass);

              const startM = timeStrToMins(activeSess.start_time || '14:00');
              const durM = Math.round(parseFloat(activeSess.duration_hours || 1.5) * 60);
              const remMins = (startM + durM) - filterMins;

              const statusText = activeSess.help_status === 'urgent' ? '🔴 손많이감' : (activeSess.help_status === 'caution' ? '🟡 주의' : '🟢 원활');
              const conflictBadge = activeSess.has_conflict ? '<span class="badge" style="background:rgba(239,68,68,0.3); color:#fca5a5; border:1px solid var(--red);">⚠️시간충돌</span>' : '';

              div.innerHTML += `
                <div class="seat-label">${label} <span style="color:#6ee7b7; font-weight:700;">🟢 체류중</span></div>
                <div class="seat-student-name">${activeSess.student_name}</div>
                <div class="seat-badges">
                  <span class="badge badge-time">⏱️ 남은시간 ${remMins}분</span>
                  ${conflictBadge}
                </div>
                <div style="font-size:0.7rem; font-weight:700; margin-top:4px;">${statusText}</div>
              `;
            } else {
              // Seat is Vacant at filterMins
              div.classList.add('status-vacant');
              div.innerHTML += `
                <div class="seat-label">${label}</div>
                <div class="seat-student-name" style="color:var(--muted); font-size:0.82rem;">⚪ 빈자리</div>
                <div style="font-size:0.7rem; color:rgba(148,163,184,0.5); margin-top:4px;">${minsToTimeStr(filterMins)} 이용가능</div>
              `;
            }
          } else {
            // Mode 'all' (Summary Mode)
            if (seatSessions.length > 0) {
              let highestStatus = 'normal';
              let hasAnyConflict = false;

              seatSessions.forEach(sess => {
                if (sess.help_status === 'urgent') highestStatus = 'urgent';
                else if (sess.help_status === 'caution' && highestStatus !== 'urgent') highestStatus = 'caution';
                if (sess.has_conflict) hasAnyConflict = true;
              });

              const statusClass = `status-${highestStatus}`;
              div.classList.add(statusClass);

              const conflictBadge = hasAnyConflict ? '<span class="badge" style="background:rgba(239,68,68,0.3); color:#fca5a5; border:1px solid var(--red);">⚠️시간충돌</span>' : '';

              if (seatSessions.length === 1) {
                const sess = seatSessions[0];
                const statusText = sess.help_status === 'urgent' ? '🔴 손많이감' : (sess.help_status === 'caution' ? '🟡 주의' : '🟢 원활');
                const typeBadge = sess.student_type === 'manual' ? '<span class="badge badge-manual">수동</span>' : '';

                div.innerHTML += `
                  <div class="seat-label">${label}</div>
                  <div class="seat-student-name">${sess.student_name || '이름 없음'}</div>
                  <div class="seat-badges">
                    <span class="badge badge-time">⏱️ ${sess.start_time} (${sess.duration_hours}h)</span>
                    ${typeBadge}
                    ${conflictBadge}
                  </div>
                  <div style="font-size:0.7rem; font-weight:700; margin-top:4px;">${statusText}</div>
                `;
              } else {
                const timeChips = seatSessions.map(s => `<span class="badge badge-time">${s.start_time}~</span>`).join(' ');
                div.innerHTML += `
                  <div class="seat-label">${label}</div>
                  <div class="seat-student-name" style="color:#dbeafe;">👥 ${seatSessions.length}명 배정</div>
                  <div class="seat-badges">
                    ${timeChips}
                    ${conflictBadge}
                  </div>
                  <div style="font-size:0.7rem; font-weight:700; color:var(--muted); margin-top:4px;">다중 시간대 착석</div>
                `;
              }
            } else {
              div.innerHTML += `
                <div class="seat-label">${label}</div>
                <div class="seat-student-name" style="color:var(--muted); font-weight:500; font-size:0.8rem;">(빈 좌석)</div>
                <div style="font-size:0.7rem; color:rgba(148,163,184,0.6); margin-top:4px;">클릭하여 배정</div>
              `;
            }
          }

          div.addEventListener('click', () => {
            if (isEditMode) {
              openCellModal(cellData);
            } else {
              openAssignModal(label, cellData);
            }
          });
        } else if (cellData.type === 'monitor') {
          div.innerHTML += `<div>🖥️</div><div>${cellData.label || '선생님 모니터'}</div>`;
          div.addEventListener('click', () => {
            if (isEditMode) openCellModal(cellData);
          });
        } else if (cellData.type === 'door') {
          div.innerHTML += `<div>🚪</div><div>${cellData.label || '출입문'}</div>`;
          div.addEventListener('click', () => {
            if (isEditMode) openCellModal(cellData);
          });
        } else {
          if (cellData.label) {
            div.innerHTML += `<div style="font-size:0.75rem; color:var(--muted); text-align:center;">${cellData.label}</div>`;
          }
          div.addEventListener('click', () => {
            if (isEditMode) openCellModal(cellData);
          });
        }

        seatingCanvas.appendChild(div);
      }
    }

    if (filterTimeMode === 'specific') {
      const vacantCount = seatCount - occupiedAtFilterTimeCount;
      seatCountMeta.textContent = `[${minsToTimeStr(filterMins)}] 체류중 ${occupiedAtFilterTimeCount}개 / 빈자리 ${vacantCount}개`;
    } else {
      seatCountMeta.textContent = `총 좌석 ${seatCount}개`;
    }
  }

  function quickDeleteCell(r, c) {
    let cellObj = layout.cells.find(cell => cell.r === r && cell.c === c);
    if (cellObj) {
      cellObj.type = 'aisle';
      cellObj.label = '';
    } else {
      layout.cells.push({ r, c, type: 'aisle', label: '' });
    }
    saveLayoutToServer();
  }

  // --- Render 30-min Timeline ---
  function renderTimeline() {
    timelineBody.innerHTML = '';
    const activeSeats = Object.keys(sessions).filter(seat => (sessions[seat] || []).length > 0);

    // Highlight active time slot column if filterTimeMode is 'specific'
    const curTimeStr = filterTimeMode === 'specific' ? minsToTimeStr(filterMins) : null;
    document.querySelectorAll('#timelineHeadRow th').forEach(th => {
      if (curTimeStr && th.dataset.timeSlot === curTimeStr) {
        th.style.color = 'var(--green)';
        th.style.fontWeight = '800';
        th.style.background = 'rgba(16, 185, 129, 0.25)';
      } else {
        th.style.color = '';
        th.style.fontWeight = '';
        th.style.background = '';
      }
    });

    if (activeSeats.length === 0) {
      timelineBody.innerHTML = `
        <tr>
          <td colspan="${TIME_SLOTS.length + 1}" style="padding:20px; color:var(--muted); text-align:center;">
            오늘 날짜에 배정된 체류 수강생이 없습니다.
          </td>
        </tr>
      `;
      return;
    }

    activeSeats.forEach(seatLabel => {
      const seatSessions = sessions[seatLabel] || [];
      seatSessions.forEach(sess => {
        const tr = document.createElement('tr');

        const tdSeat = document.createElement('td');
        tdSeat.style.fontWeight = '700';
        tdSeat.style.textAlign = 'left';
        tdSeat.style.paddingLeft = '6px';
        const conflictMark = sess.has_conflict ? '<span style="color:var(--yellow); font-size:0.7rem;">⚠️시간충돌</span>' : '';
        tdSeat.innerHTML = `
          <span style="color:var(--accent);">${seatLabel}</span> ${conflictMark}<br/>
          <span style="font-size:0.78rem; color:#fff;">${sess.student_name}</span>
        `;
        tr.appendChild(tdSeat);

        const startTime = sess.start_time || '14:00';
        const durationHours = parseFloat(sess.duration_hours) || 1.5;
        const durationSlots = Math.round(durationHours * 2);

        const startIdx = TIME_SLOTS.indexOf(startTime);

        TIME_SLOTS.forEach((slot, idx) => {
          const td = document.createElement('td');
          if (curTimeStr && slot === curTimeStr) {
            td.style.background = 'rgba(16, 185, 129, 0.15)';
          }

          if (startIdx !== -1 && idx >= startIdx && idx < startIdx + durationSlots) {
            let statusColor = sess.help_status === 'urgent' ? 'var(--red)' : (sess.help_status === 'caution' ? 'var(--yellow)' : 'var(--green)');
            if (sess.has_conflict) {
              statusColor = 'linear-gradient(45deg, var(--red) 25%, var(--yellow) 25%, var(--yellow) 50%, var(--red) 50%, var(--red) 75%, var(--yellow) 75%)';
            }
            td.innerHTML = `<div class="timeline-slot-filled" style="background:${statusColor}; opacity:0.85;"></div>`;
            td.title = `${seatLabel} ${sess.student_name} (${sess.start_time} ~ ${durationHours}시간)${sess.has_conflict ? ' ⚠️충돌: ' + sess.conflict_message : ''}`;
          }
          tr.appendChild(td);
        });

        timelineBody.appendChild(tr);
      });
    });
  }

  function renderAnalytics() {
    const activeSeats = Object.keys(sessions).filter(seat => (sessions[seat] || []).length > 0);
    let totalSessions = 0;
    let attentionCount = 0;
    let totalDuration = 0;

    activeSeats.forEach(seatLabel => {
      const seatSessions = sessions[seatLabel] || [];
      seatSessions.forEach(sess => {
        totalSessions++;
        if (sess.help_status === 'caution' || sess.help_status === 'urgent' || sess.has_conflict) {
          attentionCount++;
        }
        totalDuration += parseFloat(sess.duration_hours) || 0;
      });
    });

    const avgDuration = totalSessions > 0 ? (totalDuration / totalSessions).toFixed(1) : '0.0';

    chipTotalOccupied.textContent = `${totalSessions}건`;
    chipAttentionCount.textContent = `${attentionCount}건`;
    chipAvgDuration.textContent = `${avgDuration}h`;
  }

  // --- Export JSON ---
  function exportJson() {
    const dataObj = {
      date: currentDate,
      layout: layout,
      sessions: sessions,
      exported_at: new Date().toISOString()
    };
    const jsonStr = JSON.stringify(dataObj, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `seating_config_${currentDate}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --- Export CSV (Excel Compatible) ---
  function exportCsv() {
    const activeSeats = Object.keys(sessions).filter(seat => (sessions[seat] || []).length > 0);
    if (activeSeats.length === 0) {
      alert('오늘 배정된 체류 수강생이 없어 CSV를 내보낼 수 없습니다.');
      return;
    }

    const headers = ['좌석번호', '수강생이름', '수강생ID', '구분', '입실시각', '체류시간(시간)', '도움상태', '시간충돌여부', '메모'];
    const rows = [headers];

    activeSeats.forEach(seatLabel => {
      const seatSessions = sessions[seatLabel] || [];
      seatSessions.forEach(sess => {
        const statusText = sess.help_status === 'urgent' ? '손많이감' : (sess.help_status === 'caution' ? '주의' : '원활');
        const conflictText = sess.has_conflict ? `⚠️충돌(${sess.conflict_message})` : '정상';
        rows.push([
          `"${seatLabel}"`,
          `"${sess.student_name || ''}"`,
          `"${sess.student_id || ''}"`,
          `"${sess.student_type || 'auto'}"`,
          `"${sess.start_time || ''}"`,
          `"${sess.duration_hours || 1.5}"`,
          `"${statusText}"`,
          `"${conflictText}"`,
          `"${(sess.memo || '').replace(/"/g, '""')}"`
        ]);
      });
    });

    const csvContent = '\uFEFF' + rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `seating_schedule_${currentDate}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --- Import JSON File ---
  function importJsonFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const parsed = JSON.parse(e.target.result);
        if (!parsed || (typeof parsed !== 'object')) {
          alert('올바른 JSON 파일 형식이 아닙니다.');
          return;
        }

        const payload = {
          date: currentDate,
          layout: parsed.layout || null,
          sessions: parsed.sessions || (parsed.date ? parsed : null)
        };

        fetch('/api/seating/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
          .then(res => res.json())
          .then(data => {
            if (data.status === 'success') {
              layout = data.layout;
              
              const rawSessions = data.sessions || {};
              sessions = {};
              Object.keys(rawSessions).forEach(seat => {
                const item = rawSessions[seat];
                if (Array.isArray(item)) sessions[seat] = item;
                else if (typeof item === 'object' && item !== null) sessions[seat] = [item];
              });

              inputRows.value = layout.rows;
              inputCols.value = layout.cols;
              renderCanvas();
              renderTimeline();
              renderAnalytics();
              alert('JSON 좌석 및 체류 데이터를 성공적으로 불러왔습니다!');
            } else {
              alert('불러오기 실패: ' + (data.message || '오류 발생'));
            }
          })
          .catch(err => console.error('[Seating] Import error:', err));
      } catch (err) {
        alert('JSON 파싱 실패: ' + err.message);
      }
    };
    reader.readAsText(file);
  }

  // --- Summary Clipboard Copy ---
  function copyLayoutSummary() {
    const activeSeats = Object.keys(sessions).filter(seat => (sessions[seat] || []).length > 0);
    if (activeSeats.length === 0) {
      alert('오늘 배정된 체류 수강생이 없습니다.');
      return;
    }

    let lines = [`[🪑 좌석 체류 현황 - ${currentDate}]`];

    activeSeats.forEach(seatLabel => {
      const seatSessions = sessions[seatLabel] || [];
      seatSessions.forEach(sess => {
        const statusIcon = sess.help_status === 'urgent' ? '🔴' : (sess.help_status === 'caution' ? '🟡' : '🟢');
        const conflictTag = sess.has_conflict ? ' ⚠️시간충돌' : '';
        const memoText = sess.memo ? ` (${sess.memo})` : '';
        lines.push(`${statusIcon} [${seatLabel}] ${sess.student_name} | 입실: ${sess.start_time} (${sess.duration_hours}시간 체류)${conflictTag}${memoText}`);
      });
    });

    const textToCopy = lines.join('\n');
    navigator.clipboard.writeText(textToCopy)
      .then(() => alert('📋 오늘 좌석 체류 요약이 클립보드에 복사되었습니다!'))
      .catch(err => console.error('Copy error:', err));
  }

  // --- Assign Modal & Multi-Session Logic ---
  function openAssignModal(seatLabel, cellData) {
    currentTargetSeat = { seatLabel, cellData };
    editingSessionId = null;
    modalSeatTitle.textContent = `🪑 [${seatLabel}] 좌석 수강생 배정`;

    renderSeatSessionsListInModal(seatLabel);
    resetAssignModalForm();

    assignModal.classList.add('is-open');
  }

  function renderSeatSessionsListInModal(seatLabel) {
    const seatSessions = sessions[seatLabel] || [];
    assignedSessionsList.innerHTML = '';
    conflictWarningBox.style.display = 'none';

    if (seatSessions.length > 0) {
      assignedSessionsWrap.style.display = 'block';
      let hasAnyConflict = false;
      let conflictMsgs = [];

      seatSessions.forEach(sess => {
        if (sess.has_conflict) {
          hasAnyConflict = true;
          conflictMsgs.push(`[${sess.start_time}] ${sess.student_name}: ${sess.conflict_message}`);
        }

        const div = document.createElement('div');
        div.className = `session-item-row ${sess.has_conflict ? 'is-conflict' : ''}`;
        const statusIcon = sess.help_status === 'urgent' ? '🔴' : (sess.help_status === 'caution' ? '🟡' : '🟢');
        const conflictBadge = sess.has_conflict ? '<span style="color:var(--red); font-weight:700;"> ⚠️시간충돌</span>' : '';

        div.innerHTML = `
          <div>
            ${statusIcon} <strong style="color:#fff;">${sess.student_name}</strong>
            <span style="color:var(--muted); font-size:0.78rem;">(${sess.start_time} ~ ${sess.duration_hours}h)</span>
            ${conflictBadge}
          </div>
          <div style="display:flex; gap:4px;">
            <button type="button" class="btn btn-secondary" style="padding:2px 6px; font-size:0.72rem;">✏️ 수정</button>
            <button type="button" class="btn btn-danger" style="padding:2px 6px; font-size:0.72rem;">🗑️</button>
          </div>
        `;

        const btnEdit = div.querySelectorAll('button')[0];
        const btnDel = div.querySelectorAll('button')[1];

        btnEdit.addEventListener('click', () => editSessionItem(sess));
        btnDel.addEventListener('click', () => deleteSessionItem(sess.id));

        assignedSessionsList.appendChild(div);
      });

      if (hasAnyConflict) {
        conflictWarningBox.style.display = 'block';
        conflictWarningBox.innerHTML = `⚠️ <strong>시간대 충돌 경고:</strong><br/>${conflictMsgs.join('<br/>')}`;
      }

      btnClearAssignment.style.display = 'inline-flex';
    } else {
      assignedSessionsWrap.style.display = 'none';
      btnClearAssignment.style.display = 'none';
    }
  }

  function editSessionItem(sess) {
    editingSessionId = sess.id;
    if (sess.student_type === 'manual') {
      window.switchAssignTab('manual');
      inputManualName.value = sess.student_name || '';
      clearSelectedStudentBadge();
    } else {
      window.switchAssignTab('auto');
      const stObj = studentsList.find(st => (st.user_uuid === sess.student_id || st.username === sess.student_id || st.name === sess.student_name));
      if (stObj) {
        selectStudentItem(stObj);
      } else {
        selectedStudentObj = { name: sess.student_name, user_uuid: sess.student_id };
        selectStudentVal.value = sess.student_id;
        selectedStudentText.textContent = `✅ ${sess.student_name}`;
        selectedStudentBadge.style.display = 'flex';
      }
    }
    inputStartTime.value = sess.start_time || '14:00';
    inputDurationHours.value = sess.duration_hours || 1.5;
    window.setDurationPreset(sess.duration_hours || 1.5);
    window.setStatusPreset(sess.help_status || 'normal');
    inputMemo.value = sess.memo || '';
  }

  function deleteSessionItem(sessionId) {
    if (!currentTargetSeat) return;
    if (!confirm('해당 시간대 수강생 배정을 삭제하시겠습니까?')) return;

    const payload = {
      date: currentDate,
      seat_label: currentTargetSeat.seatLabel,
      action: 'delete',
      session_id: sessionId
    };

    fetch('/api/seating/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          sessions[currentTargetSeat.seatLabel] = (sessions[currentTargetSeat.seatLabel] || []).filter(s => s.id !== sessionId);
          renderCanvas();
          renderTimeline();
          renderAnalytics();
          renderSeatSessionsListInModal(currentTargetSeat.seatLabel);
          resetAssignModalForm();
        }
      })
      .catch(err => console.error('[Seating] Delete session error:', err));
  }

  function resetAssignModalForm() {
    editingSessionId = null;
    window.switchAssignTab('auto');
    clearSelectedStudentBadge();
    inputManualName.value = '';
    inputStartTime.value = '14:00';
    inputDurationHours.value = 1.5;
    window.setDurationPreset(1.5);
    window.setStatusPreset('normal');
    inputMemo.value = '';
  }

  function closeAssignModal() {
    assignModal.classList.remove('is-open');
    if (studentSearchResults) studentSearchResults.classList.remove('is-open');
    currentTargetSeat = null;
    editingSessionId = null;
  }

  window.switchAssignTab = function (type) {
    activeAssignTab = type;
    const tabAuto = document.getElementById('tabAuto');
    const tabManual = document.getElementById('tabManual');
    const formAuto = document.getElementById('formAuto');
    const formManual = document.getElementById('formManual');

    if (type === 'auto') {
      tabAuto.classList.add('is-active');
      tabManual.classList.remove('is-active');
      formAuto.style.display = 'block';
      formManual.style.display = 'none';
    } else {
      tabManual.classList.add('is-active');
      tabAuto.classList.remove('is-active');
      formManual.style.display = 'block';
      formAuto.style.display = 'none';
    }
  };

  window.setDurationPreset = function (val) {
    inputDurationHours.value = val;
    document.querySelectorAll('.duration-chip').forEach(chip => {
      if (parseFloat(chip.textContent) === val) {
        chip.classList.add('is-selected');
      } else {
        chip.classList.remove('is-selected');
      }
    });
  };

  window.setStatusPreset = function (val) {
    document.querySelectorAll('.status-option').forEach(opt => {
      if (opt.dataset.val === val) {
        opt.classList.add('is-selected');
      } else {
        opt.classList.remove('is-selected');
      }
    });
  };

  function saveAssignment() {
    if (!currentTargetSeat) return;

    let studentName = '';
    let studentId = '';

    if (activeAssignTab === 'auto') {
      studentId = selectStudentVal.value || (selectStudent ? selectStudent.value : '');
      studentName = selectedStudentObj ? (selectedStudentObj.name || selectedStudentObj.display_id) : '';

      if (!studentId && selectedStudentText.textContent.includes('✅')) {
        studentName = selectedStudentText.textContent.replace('✅', '').trim();
      }

      if (!studentId) {
        alert('검색어를 입력하고 수강생을 선택해주세요. (예: 홍 검색 후 클릭)');
        return;
      }
    } else {
      studentName = inputManualName.value.trim();
      if (!studentName) {
        alert('수강생 이름을 입력해주세요.');
        return;
      }
      studentId = 'manual_' + Date.now();
    }

    const selectedStatusOpt = document.querySelector('.status-option.is-selected');
    const helpStatus = selectedStatusOpt ? selectedStatusOpt.dataset.val : 'normal';

    const payload = {
      date: currentDate,
      seat_label: currentTargetSeat.seatLabel,
      action: 'assign',
      session_id: editingSessionId,
      student_type: activeAssignTab,
      student_id: studentId,
      student_name: studentName,
      start_time: inputStartTime.value || '14:00',
      duration_hours: parseFloat(inputDurationHours.value) || 1.5,
      help_status: helpStatus,
      memo: inputMemo.value.trim()
    };

    fetch('/api/seating/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          sessions[currentTargetSeat.seatLabel] = data.seat_sessions;
          renderCanvas();
          renderTimeline();
          renderAnalytics();

          if (data.has_conflict) {
            alert(`⚠️ 시간대 충돌 주의!\n${data.conflict_message}\n경고가 포함된 채로 배정되었습니다.`);
          }

          renderSeatSessionsListInModal(currentTargetSeat.seatLabel);
          resetAssignModalForm();
        } else {
          alert('저장 실패: ' + (data.message || '오류 발생'));
        }
      })
      .catch(err => console.error('[Seating] Save session error:', err));
  }

  function clearAllAssignmentsOnSeat() {
    if (!currentTargetSeat) return;
    if (!confirm(`[${currentTargetSeat.seatLabel}] 좌석의 모든 시간대 수강생 배정을 해제하시겠습니까?`)) return;

    const payload = {
      date: currentDate,
      seat_label: currentTargetSeat.seatLabel,
      action: 'clear'
    };

    fetch('/api/seating/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          delete sessions[currentTargetSeat.seatLabel];
          renderCanvas();
          renderTimeline();
          renderAnalytics();
          closeAssignModal();
        }
      })
      .catch(err => console.error('[Seating] Clear session error:', err));
  }

  // --- Layout Cell Editor Modal ---
  function openCellModal(cellData) {
    currentEditCell = cellData;
    cellTypeSelect.value = cellData.type || 'seat';
    cellLabelInput.value = cellData.label || '';
    cellEditorModal.classList.add('is-open');
  }

  function closeCellModal() {
    cellEditorModal.classList.remove('is-open');
    currentEditCell = null;
  }

  function saveCellProps() {
    if (!currentEditCell) return;

    const newType = cellTypeSelect.value;
    const newLabel = cellLabelInput.value.trim();

    let cellObj = layout.cells.find(c => c.r === currentEditCell.r && c.c === currentEditCell.c);
    if (cellObj) {
      cellObj.type = newType;
      cellObj.label = newLabel;
    } else {
      cellObj = { r: currentEditCell.r, c: currentEditCell.c, type: newType, label: newLabel };
      layout.cells.push(cellObj);
    }

    saveLayoutToServer();
    closeCellModal();
  }

  function clearCellProps() {
    if (!currentEditCell) return;
    let cellObj = layout.cells.find(c => c.r === currentEditCell.r && c.c === currentEditCell.c);
    if (cellObj) {
      cellObj.type = 'aisle';
      cellObj.label = '';
    } else {
      layout.cells.push({ r: currentEditCell.r, c: currentEditCell.c, type: 'aisle', label: '' });
    }
    saveLayoutToServer();
    closeCellModal();
  }

  function updateGridDimensions(newRows, newCols) {
    layout.rows = newRows;
    layout.cols = newCols;

    layout.cells = (layout.cells || []).filter(c => c.r < newRows && c.c < newCols);

    saveLayoutToServer();
  }

  function saveLayoutToServer() {
    fetch('/api/seating/layout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(layout)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          layout = data.layout;
          renderCanvas();
        }
      })
      .catch(err => console.error('[Seating] Save layout error:', err));
  }

  function resetLayoutToDefault() {
    fetch('/api/seating/layout/reset', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          layout = data.layout;
          inputRows.value = layout.rows;
          inputCols.value = layout.cols;
          renderCanvas();
        }
      })
      .catch(err => console.error('[Seating] Reset layout error:', err));
  }

})();
