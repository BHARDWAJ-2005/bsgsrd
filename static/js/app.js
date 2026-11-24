// BSG Sangareddy Interactive Client Script

document.addEventListener('DOMContentLoaded', function () {
    // 1. Cascading Mandal -> School Dropdown
    const mandalSelect = document.getElementById('mandal-select');
    const schoolSelect = document.getElementById('school-select');
    const schoolInfoBadge = document.getElementById('school-info-badge');

    if (mandalSelect && schoolSelect) {
        mandalSelect.addEventListener('change', function () {
            const mandalId = this.value;
            schoolSelect.innerHTML = '<option value="">Loading recognized schools...</option>';
            schoolSelect.disabled = true;
            if (schoolInfoBadge) schoolInfoBadge.classList.add('hidden');

            if (!mandalId) {
                schoolSelect.innerHTML = '<option value="">-- First Select a Mandal --</option>';
                schoolSelect.disabled = true;
                return;
            }

            fetch(`/api/schools-by-mandal/?mandal_id=${mandalId}`)
                .then(res => res.json())
                .then(data => {
                    schoolSelect.innerHTML = '<option value="">-- Select Your School --</option>';
                    if (data.schools && data.schools.length > 0) {
                        data.schools.forEach(sch => {
                            const opt = document.createElement('option');
                            opt.value = sch.udise_code;
                            opt.textContent = `${sch.display_name} (UDISE: ${sch.udise_code}) [${sch.school_type_display.split('(')[0].trim()}]`;
                            opt.dataset.type = sch.school_type_display;
                            opt.dataset.boysQ = sch.boys_quota;
                            opt.dataset.girlsQ = sch.girls_quota;
                            opt.dataset.enrolled = sch.enrolled;
                            schoolSelect.appendChild(opt);
                        });
                        schoolSelect.disabled = false;
                    } else {
                        schoolSelect.innerHTML = '<option value="">No schools found for this mandal</option>';
                    }
                })
                .catch(err => {
                    console.error('Error fetching schools:', err);
                    schoolSelect.innerHTML = '<option value="">Error loading schools</option>';
                });
        });

        schoolSelect.addEventListener('change', function () {
            const selectedOpt = this.options[this.selectedIndex];
            if (schoolInfoBadge && selectedOpt && selectedOpt.value) {
                schoolInfoBadge.classList.remove('hidden');
                document.getElementById('badge-school-type').textContent = selectedOpt.dataset.type || '';
                document.getElementById('badge-school-quota').textContent = `Quota: ${selectedOpt.dataset.boysQ} Boys · ${selectedOpt.dataset.girlsQ} Girls`;
            } else if (schoolInfoBadge) {
                schoolInfoBadge.classList.add('hidden');
            }
        });
    }

    // 2. Mode Toggle (SHORT vs BRIEF) & Remembered Preference
    const modeShortBtn = document.getElementById('mode-short-btn');
    const modeBriefBtn = document.getElementById('mode-brief-btn');
    const modeInput = document.getElementById('detail_level_input');
    const briefFields = document.querySelectorAll('.brief-field-group');

    function setFormMode(mode) {
        if (!modeInput) return;
        modeInput.value = mode;
        localStorage.setItem('bsg_enrollment_mode', mode);

        if (mode === 'BRIEF') {
            if (modeBriefBtn) {
                modeBriefBtn.classList.add('bg-blue-600', 'text-white', 'shadow');
                modeBriefBtn.classList.remove('bg-white', 'text-slate-700');
            }
            if (modeShortBtn) {
                modeShortBtn.classList.remove('bg-blue-600', 'text-white', 'shadow');
                modeShortBtn.classList.add('bg-white', 'text-slate-700');
            }
            briefFields.forEach(el => el.classList.remove('hidden'));
        } else {
            if (modeShortBtn) {
                modeShortBtn.classList.add('bg-blue-600', 'text-white', 'shadow');
                modeShortBtn.classList.remove('bg-white', 'text-slate-700');
            }
            if (modeBriefBtn) {
                modeBriefBtn.classList.remove('bg-blue-600', 'text-white', 'shadow');
                modeBriefBtn.classList.add('bg-white', 'text-slate-700');
            }
            briefFields.forEach(el => el.classList.add('hidden'));
        }
    }

    if (modeShortBtn && modeBriefBtn) {
        modeShortBtn.addEventListener('click', () => setFormMode('SHORT'));
        modeBriefBtn.addEventListener('click', () => setFormMode('BRIEF'));

        // Load saved mode or default to SHORT
        const savedMode = localStorage.getItem('bsg_enrollment_mode') || 'SHORT';
        setFormMode(savedMode);
    }

    // 3. Gender Toggle for Student Form (Boys vs Girls measurements)
    const genderSelect = document.getElementById('student_gender_select');
    const boysMeasContainer = document.getElementById('boys-measurements-container');
    const girlsMeasContainer = document.getElementById('girls-measurements-container');

    function toggleGenderMeasurements() {
        if (!genderSelect) return;
        const gender = genderSelect.value;
        if (gender === 'BOY') {
            if (boysMeasContainer) boysMeasContainer.classList.remove('hidden');
            if (girlsMeasContainer) girlsMeasContainer.classList.add('hidden');
        } else if (gender === 'GIRL') {
            if (girlsMeasContainer) girlsMeasContainer.classList.remove('hidden');
            if (boysMeasContainer) boysMeasContainer.classList.add('hidden');
        } else {
            if (boysMeasContainer) boysMeasContainer.classList.add('hidden');
            if (girlsMeasContainer) girlsMeasContainer.classList.add('hidden');
        }
    }

    if (genderSelect) {
        genderSelect.addEventListener('change', toggleGenderMeasurements);
        toggleGenderMeasurements();
    }

    // 4. Client-side Fast Table Filter
    const liveSearchInput = document.getElementById('table-live-search');
    if (liveSearchInput) {
        liveSearchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.student-table-row');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // 5. Real-time Live Stats Poller (pauses when server is down or tab is in background)
    let pollFailures = 0;
    let pollInterval = null;

    function refreshLiveStats() {
        if (pollFailures >= 3) return;
        fetch('/api/live-stats/')
            .then(res => {
                if (!res.ok) throw new Error('Network error');
                return res.json();
            })
            .then(data => {
                pollFailures = 0;
                const liveCountEnrolled = document.getElementById('live-count-enrolled');
                const liveCountSchools = document.getElementById('live-count-schools');
                const liveCountMandals = document.getElementById('live-count-mandals');
                if (liveCountEnrolled) liveCountEnrolled.textContent = data.enrolled_total;
                if (liveCountSchools) liveCountSchools.textContent = data.schools_count;
                if (liveCountMandals) liveCountMandals.textContent = data.mandals_count;
            })
            .catch(() => {
                pollFailures++;
                if (pollFailures >= 3 && pollInterval) {
                    clearInterval(pollInterval);
                }
            });
    }

    // Poll every 45 seconds only when page is visible
    pollInterval = setInterval(() => {
        if (!document.hidden) {
            refreshLiveStats();
        }
    }, 45000);
});

// Global Modal Handlers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

// Edit Student Modal Loader
function openEditStudentModal(studentId) {
    fetch(`/students/${studentId}/json/`)
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                alert('Could not load student data.');
                return;
            }
            const s = data.student;
            document.getElementById('edit_student_form').action = `/students/${s.id}/edit/`;
            document.getElementById('edit_student_id').value = s.id;
            document.getElementById('edit_name').value = s.name;
            document.getElementById('edit_father_name').value = s.father_name;
            document.getElementById('edit_class_level').value = s.class_level;
            document.getElementById('edit_height_cm').value = s.height_cm;
            document.getElementById('edit_uniform_size').value = s.uniform_size;
            document.getElementById('edit_shoe_size').value = s.shoe_size;
            document.getElementById('edit_dob').value = s.dob;
            document.getElementById('edit_parent_mobile').value = s.parent_mobile;
            document.getElementById('edit_gender_badge').textContent = s.gender === 'BOY' ? 'Boy (Scout/Cub)' : 'Girl (Guide/Bulbul)';

            if (s.gender === 'BOY') {
                document.getElementById('edit_boys_measurements').classList.remove('hidden');
                document.getElementById('edit_girls_measurements').classList.add('hidden');
                document.getElementById('edit_chest').value = s.chest;
                document.getElementById('edit_waist').value = s.waist;
                document.getElementById('edit_neck').value = s.neck;
                document.getElementById('edit_shoulder').value = s.shoulder;
                document.getElementById('edit_sleeve').value = s.sleeve;
                document.getElementById('edit_shirt_length').value = s.shirt_length;
                document.getElementById('edit_pant_length').value = s.pant_length;
            } else {
                document.getElementById('edit_boys_measurements').classList.add('hidden');
                document.getElementById('edit_girls_measurements').classList.remove('hidden');
                document.getElementById('edit_bust').value = s.bust;
                document.getElementById('edit_waist_g').value = s.waist;
                document.getElementById('edit_hip').value = s.hip;
                document.getElementById('edit_shoulder_g').value = s.shoulder;
                document.getElementById('edit_sleeve_g').value = s.sleeve;
                document.getElementById('edit_kameez_length').value = s.kameez_length;
                document.getElementById('edit_salwar_length').value = s.salwar_length;
            }

            openModal('editStudentModal');
        })
        .catch(err => {
            console.error('Error fetching student:', err);
            alert('Failed to load student details.');
        });
}

function syncGenderFromRole(role) {
    const genderSelect = document.getElementById('lm_gender');
    if (!genderSelect) return;
    if (role === 'GUIDE_CAPTAIN' || role === 'FLOCK_LEADER') {
        genderSelect.value = 'FEMALE';
        handleGenderSwitch('FEMALE');
    } else if (role === 'SCOUT_MASTER' || role === 'CUB_MASTER') {
        genderSelect.value = 'MALE';
        handleGenderSwitch('MALE');
    }
}

function handleGenderSwitch(gender) {
    const chestBustLbl = document.getElementById('lm_chest_bust_lbl');
    const topLbl = document.getElementById('lm_top_lbl');
    const botLbl = document.getElementById('lm_bot_lbl');
    const neckBox = document.getElementById('lm_neck_box');
    const hipBox = document.getElementById('lm_hip_box');

    if (gender === 'FEMALE') {
        if (chestBustLbl) chestBustLbl.textContent = 'Bust';
        if (topLbl) topLbl.textContent = 'Kameez Length';
        if (botLbl) botLbl.textContent = 'Salwar Length';
        if (neckBox) neckBox.classList.add('hidden');
        if (hipBox) hipBox.classList.remove('hidden');
    } else {
        if (chestBustLbl) chestBustLbl.textContent = 'Chest';
        if (topLbl) topLbl.textContent = 'Shirt Length';
        if (botLbl) botLbl.textContent = 'Pant Length';
        if (neckBox) neckBox.classList.remove('hidden');
        if (hipBox) hipBox.classList.add('hidden');
    }
}

function openSchoolLeaderEditModal(id, name, role, gender, designation, mobile, email, uniform_size, shoe_size, height_cm, chest_bust, waist, neck, shoulder, sleeve, top_length, bottom_length, hip) {
    const title = document.getElementById('leader_meas_title');
    if (title) title.textContent = `Edit Unit Leader: ${name}`;

    const sub = document.getElementById('leader_meas_subtitle');
    if (sub) sub.textContent = `Update official details and tailoring measurements for ${name}`;

    const setVal = (elemId, val) => {
        const el = document.getElementById(elemId);
        if (el) el.value = (val !== undefined && val !== null && val !== 'None') ? val : '';
    };

    setVal('lm_leader_id', id);
    setVal('lm_name', name);
    setVal('lm_role', role);
    setVal('lm_gender', gender);
    setVal('lm_designation', designation);
    setVal('lm_mobile', mobile);
    setVal('lm_email', email);
    setVal('lm_uniform_size', uniform_size);
    setVal('lm_shoe_size', shoe_size);
    setVal('lm_height_cm', height_cm);
    setVal('lm_chest_bust', chest_bust);
    setVal('lm_waist', waist);
    setVal('lm_neck', neck);
    setVal('lm_shoulder', shoulder);
    setVal('lm_sleeve', sleeve);
    setVal('lm_top_length', top_length);
    setVal('lm_bottom_length', bottom_length);
    setVal('lm_hip', hip);

    handleGenderSwitch(gender || 'MALE');
    openModal('leaderMeasurementModal');
}

function openAppointLeaderModal() {
    const title = document.getElementById('leader_meas_title');
    if (title) title.textContent = 'Appoint Designated Unit Leader';

    const sub = document.getElementById('leader_meas_subtitle');
    if (sub) sub.textContent = 'Enter new teacher leader details and uniform measurements';

    const clearField = (elemId) => {
        const el = document.getElementById(elemId);
        if (el) el.value = '';
    };

    clearField('lm_leader_id');
    clearField('lm_name');
    clearField('lm_designation');
    clearField('lm_mobile');
    clearField('lm_email');
    clearField('lm_uniform_size');
    clearField('lm_shoe_size');
    clearField('lm_height_cm');
    clearField('lm_chest_bust');
    clearField('lm_waist');
    clearField('lm_neck');
    clearField('lm_shoulder');
    clearField('lm_sleeve');
    clearField('lm_top_length');
    clearField('lm_bottom_length');
    clearField('lm_hip');

    const roleSelect = document.getElementById('lm_role');
    if (roleSelect && roleSelect.options.length > 0) {
        roleSelect.selectedIndex = 0;
        syncGenderFromRole(roleSelect.value);
    } else {
        handleGenderSwitch('MALE');
    }

    openModal('leaderMeasurementModal');
}

function openLeaderMeasurementModal(id, name, gender, uniform_size, shoe_size, height_cm, chest_bust, waist, neck, shoulder, sleeve, top_length, bottom_length, hip) {
    openSchoolLeaderEditModal(id, name, '', gender, '', '', '', uniform_size, shoe_size, height_cm, chest_bust, waist, neck, shoulder, sleeve, top_length, bottom_length, hip);
}
