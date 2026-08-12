(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const token = sessionStorage.getItem('niet_token');
  let user = JSON.parse(sessionStorage.getItem('niet_user') || 'null');
  const content = $('#page-content');
  const state = {
    page: '', subjects: [], departments: [], semesters: [], regulations: [], currentPaper: null,
    wizard: {
      step: 1, details: {exam_type: 'Model Examination', duration_minutes: 180, total_marks: 100, academic_year: '2026–2027', class_section: ''},
      sections: [
        {name: 'PART A', count: 10, marks: 2, question_type: 'Short Answer', instructions: 'Answer ALL questions', has_choice: false},
        {name: 'PART B', count: 5, marks: 13, question_type: 'Descriptive / Problem Solving', instructions: 'Answer ALL questions', has_choice: true},
        {name: 'PART C', count: 1, marks: 15, question_type: 'Application Based', instructions: 'Answer ONE question', has_choice: false}
      ],
      difficulty: {easy: 30, medium: 50, hard: 20}, bloom: {Remember: 15, Understand: 25, Apply: 25, Analyze: 20, Evaluate: 10, Create: 5}, unitWeightage: {}, topics: [], blueprint: null
    }
  };

  const navs = {
    teacher: [
      ['MAIN', 'dashboard', '⌂', 'Dashboard'], ['MAIN', 'generate', '✦', 'Generate paper'],
      ['ACADEMIC', 'subjects', '▤', 'My subjects'], ['ACADEMIC', 'documents', '▧', 'Document library'],
      ['PAPERS', 'papers', '▦', 'Question papers'], ['PAPERS', 'question-bank', '◫', 'Question bank'],
      ['ACCOUNT', 'profile', '◎', 'Profile']
    ],
    admin: [
      ['MAIN', 'admin-dashboard', '⌂', 'Dashboard'], ['MANAGEMENT', 'teachers', '♙', 'Teachers'],
      ['MANAGEMENT', 'departments', '◇', 'Departments'], ['MANAGEMENT', 'subjects-admin', '▤', 'Subjects'],
      ['MANAGEMENT', 'academic', '◫', 'Semesters & regulations'], ['CONTENT', 'patterns', '▦', 'Question patterns'],
      ['CONTENT', 'documents', '▧', 'Uploaded documents'], ['CONTENT', 'papers', '▦', 'Question papers'],
      ['GOVERNANCE', 'generation-history', '✦', 'AI generation history'], ['GOVERNANCE', 'activity', '≡', 'Activity logs'],
      ['GOVERNANCE', 'settings', '⚙', 'System settings'], ['ACCOUNT', 'profile', '◎', 'Profile']
    ]
  };

  const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char]));
  const pretty = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
  const dateText = value => value ? new Intl.DateTimeFormat('en-IN', {day: '2-digit', month: 'short', year: 'numeric'}).format(new Date(value)) : '—';
  const initials = name => String(name || 'NIET').split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase();
  const statusBadge = value => `<span class="status ${escapeHTML(value)}">${escapeHTML(pretty(value))}</span>`;
  const empty = (title, message, action = '') => `<div class="empty-state"><span>▱</span><h3>${escapeHTML(title)}</h3><p>${escapeHTML(message)}</p>${action}</div>`;
  const formatBytes = size => size < 1024 ? `${size} B` : size < 1048576 ? `${(size / 1024).toFixed(1)} KB` : `${(size / 1048576).toFixed(1)} MB`;

  async function api(path, options = {}) {
    const headers = {Authorization: `Bearer ${token}`, ...(options.headers || {})};
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers});
    if (response.status === 401) { sessionStorage.clear(); location.replace('/login.html'); throw new Error('Session expired'); }
    const type = response.headers.get('content-type') || '';
    const payload = type.includes('json') ? await response.json().catch(() => ({})) : await response.blob();
    if (!response.ok) {
      const validation = payload.errors?.map(item => `${item.field}: ${item.message}`).join(' · ');
      throw new Error(validation || payload.detail || 'The request could not be completed.');
    }
    return payload;
  }

  function toast(title, message = '', kind = 'success') {
    const item = document.createElement('div');
    item.className = `toast ${kind}`;
    item.innerHTML = `<span>${kind === 'error' ? '!' : '✓'}</span><p><strong>${escapeHTML(title)}</strong><small>${escapeHTML(message)}</small></p>`;
    $('#toast-region').append(item);
    setTimeout(() => item.remove(), 4200);
  }

  function confirmAction(title, message) {
    return new Promise(resolve => {
      const dialog = $('#confirm-dialog');
      $('#confirm-title').textContent = title;
      $('#confirm-message').textContent = message;
      dialog.showModal();
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once: true});
    });
  }

  async function download(path, filename) {
    try {
      const blob = await api(path);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      toast('Download ready', filename);
    } catch (error) { toast('Download failed', error.message, 'error'); }
  }

  function pageIntro(title, description, actions = '') {
    return `<div class="page-intro"><div><h2>${escapeHTML(title)}</h2><p>${escapeHTML(description)}</p></div><div class="page-actions">${actions}</div></div>`;
  }
  const statCard = (icon, value, label) => `<article class="stat-card"><span class="stat-icon">${icon}</span><p><strong>${value}</strong><small>${escapeHTML(label)}</small></p></article>`;

  async function loadMasters() {
    const calls = [api('/api/subjects'), api('/api/departments'), api('/api/semesters'), api('/api/regulations')];
    [state.subjects, state.departments, state.semesters, state.regulations] = await Promise.all(calls);
  }

  function buildNav() {
    const role = user.role === 'teacher' ? 'teacher' : 'admin';
    let lastLabel = '';
    $('#sidebar-nav').innerHTML = navs[role].map(([label, page, icon, text]) => {
      const heading = label !== lastLabel ? `<div class="nav-label">${label}</div>` : '';
      lastLabel = label;
      return `${heading}<button class="nav-item" data-page="${page}"><span>${icon}</span>${text}</button>`;
    }).join('');
  }

  async function navigate(page) {
    state.page = page;
    $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.page === page));
    $('#sidebar').classList.remove('open');
    const names = {'admin-dashboard': 'Admin dashboard', dashboard: 'Dashboard', generate: 'Generate question paper', subjects: 'My subjects', documents: 'Document library', papers: 'Question papers', 'question-bank': 'Question bank', teachers: 'Teacher management', academic: 'Semesters & regulations', departments: 'Departments', 'subjects-admin': 'Subjects', patterns: 'Question patterns', 'generation-history': 'AI generation history', settings: 'System settings', activity: 'Activity logs', profile: 'Profile'};
    $('#page-title').textContent = names[page] || pretty(page);
    $('#page-breadcrumb').textContent = names[page] || pretty(page);
    content.innerHTML = '<div class="empty-state"><div class="spinner"></div><p>Loading workspace…</p></div>';
    try {
      if (page === 'dashboard') await renderTeacherDashboard();
      else if (page === 'admin-dashboard') await renderAdminDashboard();
      else if (page === 'teachers') await renderTeachers();
      else if (['academic', 'departments', 'subjects-admin'].includes(page)) await renderAcademic(page);
      else if (page === 'patterns') await renderPatterns();
      else if (page === 'generation-history') await renderGenerationHistory();
      else if (page === 'settings') await renderSettings();
      else if (page === 'subjects') renderSubjects();
      else if (page === 'documents') await renderDocuments();
      else if (page === 'papers') await renderPapers();
      else if (page === 'question-bank') await renderQuestionBank();
      else if (page === 'activity') await renderActivity();
      else if (page === 'generate') await renderWizard();
      else if (page === 'profile') renderProfile();
    } catch (error) { content.innerHTML = empty('Unable to load this page', error.message, '<button class="btn btn-primary" data-action="retry-page">Try again</button>'); }
  }

  async function renderTeacherDashboard() {
    const data = await api('/api/teacher/dashboard');
    content.innerHTML = `${pageIntro(`Welcome, ${data.welcome.split(' ')[0]}`, 'Your private academic question paper workspace.', '<button class="btn btn-primary" data-page="generate">✦ Generate question paper</button>')}
      <div class="stats-grid">${statCard('▤', data.cards.assigned_subjects, 'Assigned subjects')}${statCard('▧', data.cards.uploaded_materials, 'Uploaded materials')}${statCard('▦', data.cards.generated_papers, 'Generated papers')}${statCard('◫', data.cards.draft_papers, 'Draft papers')}</div>
      <div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h3>Recent question papers</h3><p>Continue reviewing your latest work</p></div><button class="text-button" data-page="papers">View all →</button></div>${papersTable(data.recent_papers, true)}</section>
      <aside class="panel quick-generate"><span class="kicker light">Syllabus-grounded workflow</span><h3>Ready to prepare your next examination?</h3><p>Start with an assigned subject, upload its syllabus, and verify the blueprint before generation.</p><button class="btn btn-gold" data-page="generate">Start generating →</button></aside></div>
      <section class="panel" style="margin-top:16px"><div class="panel-head"><div><h3>Assigned subjects</h3><p>Subjects available to your staff account</p></div></div><div class="subject-cards">${data.subjects.map(subjectCard).join('')}</div></section>`;
  }

  async function renderAdminDashboard() {
    const data = await api('/api/admin/dashboard');
    const c = data.cards;
    content.innerHTML = `${pageIntro('Academic control center', 'Live operational data across the question paper system.', '<button class="btn btn-primary" data-page="teachers">+ Add teacher</button>')}
      <div class="stats-grid">${statCard('♙', c.teachers, 'Active teachers')}${statCard('▤', c.subjects, 'Active subjects')}${statCard('▧', c.documents, 'Private documents')}${statCard('▦', c.generated_papers, 'Generated papers')}</div>
      <div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h3>Recent papers</h3><p>${c.papers_this_month} generated in the last 30 days</p></div><button class="text-button" data-page="papers">View all →</button></div>${papersTable(data.recent_papers)}</section>
      <section class="panel"><div class="panel-head"><div><h3>Governance snapshot</h3><p>Approval and academic setup</p></div></div><div class="activity-list"><div class="activity-item"><span>✓</span><p><strong>Pending approvals</strong><small>Awaiting administrator review</small></p><b>${c.pending_approvals}</b></div><div class="activity-item"><span>◇</span><p><strong>Departments</strong><small>Active academic departments</small></p><b>${c.departments}</b></div>${data.most_used_subjects.slice(0, 3).map(item => `<div class="activity-item"><span>▤</span><p><strong>${escapeHTML(item.name)}</strong><small>Generated paper usage</small></p><b>${item.count}</b></div>`).join('')}</div></section></div>`;
  }

  function subjectCard(subject) { return `<article class="subject-card"><span class="subject-code">${escapeHTML(subject.code)}</span><p><strong>${escapeHTML(subject.name)}</strong><small>${escapeHTML(subject.semester || '')}</small></p></article>`; }
  function papersTable(papers, compact = false) {
    if (!papers?.length) return empty('No question papers yet', 'Generated papers will appear here.');
    return `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Paper</th><th>Subject</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody>${papers.map(p => `<tr><td><div class="table-primary"><span>QP</span><p><b>${escapeHTML(p.code || p.paper_code)}</b><small>${escapeHTML(p.title)}</small></p></div></td><td>${escapeHTML(p.subject || '—')}</td><td>${statusBadge(p.status)}</td><td>${dateText(p.updated_at || p.created_at)}</td><td><div class="table-actions"><button data-action="view-paper" data-id="${p.id}">View</button></div></td></tr>`).join('')}</tbody></table></div>`;
  }

  async function renderTeachers() {
    const teachers = await api('/api/admin/teachers');
    content.innerHTML = `${pageIntro('Teacher management', 'Create staff accounts, assign departments and subjects, and manage access.', '<button class="btn btn-primary" data-action="toggle-teacher-form">+ Add teacher</button>')}
      <section class="panel form-card" id="teacher-form-card" hidden><div class="panel-head"><div><h3>Create teacher account</h3><p>A temporary password must be changed by the teacher</p></div></div><form id="teacher-create-form"><div class="form-grid cols-3"><label>Full name<input name="full_name" required minlength="2"></label><label>Employee ID<input name="employee_id" required></label><label>Institutional email<input name="email" type="email" required></label><label>Username<input name="username" required minlength="3"></label><label>Phone<input name="phone"></label><label>Designation<input name="designation" value="Assistant Professor"></label><label>Department<select name="department_id" required><option value="">Select</option>${state.departments.map(item => `<option value="${item.id}">${escapeHTML(item.name)}</option>`).join('')}</select></label><label>Temporary password<input name="temporary_password" type="password" required minlength="10" value="Welcome@123"></label></div><label>Assigned subjects<select name="subject_ids" multiple size="4">${state.subjects.map(item => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join('')}</select></label><div class="form-footer"><button type="button" class="btn btn-outline" data-action="toggle-teacher-form">Cancel</button><button class="btn btn-primary">Create teacher</button></div></form></section>
      <section class="panel"><div class="toolbar"><div class="search-box"><span>⌕</span><input id="teacher-search" placeholder="Search name, employee ID, or email"></div><select id="teacher-department-filter"><option value="">All departments</option>${state.departments.map(item => `<option value="${item.id}">${escapeHTML(item.code)}</option>`).join('')}</select></div>${teachers.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Teacher</th><th>Employee ID</th><th>Designation</th><th>Status</th><th>Last login</th><th>Actions</th></tr></thead><tbody id="teacher-table-body">${teachers.map(teacherRow).join('')}</tbody></table></div>` : empty('No teachers found', 'Create the first authorized staff account.')}</section>`;
  }
  function teacherRow(t) { return `<tr data-search="${escapeHTML(`${t.full_name} ${t.email} ${t.employee_id}`.toLowerCase())}" data-department="${t.department_id || ''}"><td><div class="table-primary"><span>${initials(t.full_name)}</span><p><b>${escapeHTML(t.full_name)}</b><small>${escapeHTML(t.email)}</small></p></div></td><td>${escapeHTML(t.employee_id)}</td><td>${escapeHTML(t.designation || '—')}</td><td>${statusBadge(t.is_active ? 'active' : 'inactive')}</td><td>${dateText(t.last_login_at)}</td><td><div class="table-actions"><button data-action="teacher-reset" data-id="${t.id}">Reset password</button>${t.is_active ? `<button data-action="teacher-deactivate" data-id="${t.id}">Deactivate</button>` : ''}</div></td></tr>`; }

  async function renderAcademic(view = 'academic') {
    const heading = view === 'departments' ? 'Department management' : view === 'subjects-admin' ? 'Subject management' : 'Semesters & regulations';
    content.innerHTML = `${pageIntro(heading, 'Manage extensible departments, semesters, regulations, and subjects.')}
      <div class="academic-layout"><section class="panel"><div class="panel-head"><div><h3>Departments</h3><p>${state.departments.length} active departments</p></div></div><form class="compact-form" id="department-form"><input name="code" placeholder="Code" required maxlength="20"><input name="name" placeholder="Department name" required><button class="btn btn-primary">Add</button></form><div class="tag-list">${state.departments.map(item => `<span class="tag-item"><b>${escapeHTML(item.code)}</b>${escapeHTML(item.name)}<button data-action="delete-department" data-id="${item.id}" aria-label="Deactivate ${escapeHTML(item.name)}">×</button></span>`).join('')}</div></section>
      <section class="panel"><div class="panel-head"><div><h3>Regulations &amp; semesters</h3><p>Available academic structures</p></div></div><div class="tag-list">${state.regulations.map(item => `<span class="tag-item"><b>${item.year}</b>${escapeHTML(item.name)}</span>`).join('')}${state.semesters.map(item => `<span class="tag-item"><b>${item.ordinal}</b>${escapeHTML(item.name)}</span>`).join('')}</div></section></div>
      <section class="panel" style="margin-top:16px"><div class="panel-head"><div><h3>Subjects</h3><p>Not limited to a single department or discipline</p></div></div><form id="subject-form" class="form-grid cols-3"><label>Subject code<input name="code" required></label><label>Subject name<input name="name" required></label><label>Credits<input name="credits" type="number" value="3" min="0" max="20"></label><label>Department<select name="department_id" required>${state.departments.map(item => `<option value="${item.id}">${escapeHTML(item.code)}</option>`).join('')}</select></label><label>Semester<select name="semester_id" required>${state.semesters.map(item => `<option value="${item.id}">${escapeHTML(item.name)}</option>`).join('')}</select></label><label>Regulation<select name="regulation_id" required>${state.regulations.map(item => `<option value="${item.id}">${escapeHTML(item.name)}</option>`).join('')}</select></label><div class="form-footer" style="grid-column:1/-1"><button class="btn btn-primary">Add subject</button></div></form><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Code</th><th>Subject</th><th>Credits</th><th>Status</th><th></th></tr></thead><tbody>${state.subjects.map(s => `<tr><td><b>${escapeHTML(s.code)}</b></td><td>${escapeHTML(s.name)}</td><td>${s.credits}</td><td>${statusBadge(s.is_active ? 'active' : 'inactive')}</td><td><button class="text-button" data-action="delete-subject" data-id="${s.id}">Deactivate</button></td></tr>`).join('')}</tbody></table></div></section>`;
  }

  function renderSubjects() {
    content.innerHTML = `${pageIntro('My assigned subjects', 'Only administrators can change subject assignments.', '<button class="btn btn-primary" data-page="generate">Generate paper</button>')}<div class="subject-cards">${state.subjects.map(subject => `<article class="subject-card"><span class="subject-code">${escapeHTML(subject.code)}</span><p><strong>${escapeHTML(subject.name)}</strong><small>${escapeHTML(state.semesters.find(s => s.id === subject.semester_id)?.name || '')} · ${subject.credits} credits</small></p><button class="text-button" style="margin-left:auto" data-action="generate-subject" data-id="${subject.id}">Use →</button></article>`).join('')}</div>`;
  }

  async function renderDocuments() {
    const docs = await api('/api/documents');
    const hasProcessing = docs.some(doc => ['uploaded', 'queued', 'processing'].includes(doc.processing_status));
    content.innerHTML = `${pageIntro('Private document library', 'Files remain restricted to their owner; administrators have audited oversight.', user.role === 'teacher' ? '<button class="btn btn-primary" data-action="toggle-doc-upload">↑ Upload documents</button>' : '')}
      ${user.role === 'teacher' ? `<section class="panel" id="doc-upload-panel" hidden><form id="library-upload-form"><div class="form-grid"><label>Subject<select name="subject_id" required>${state.subjects.map(item => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join('')}</select></label><label>Document category<select name="category">${['syllabus','portion','previous_paper','sample_paper','question_bank','notes','reference','assignment'].map(item => `<option value="${item}">${pretty(item)}</option>`).join('')}</select></label></div><label>Choose one or more files<input name="files" type="file" multiple required accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"></label><div class="form-footer"><button class="btn btn-primary">Upload &amp; analyze</button></div></form></section>` : ''}
      <section class="panel">${docs.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Document</th><th>Category</th><th>Size</th><th>Processing</th><th>Uploaded</th><th>Actions</th></tr></thead><tbody>${docs.map(doc => `<tr><td><div class="table-primary"><span>${escapeHTML(doc.extension.replace('.', '').slice(0, 3).toUpperCase())}</span><p><b>${escapeHTML(doc.original_name)}</b><small>${doc.page_count || 0} page/sheet/slide sections · ${doc.metadata_json?.chunk_count || 0} chunks</small></p></div></td><td>${pretty(doc.category)}</td><td>${formatBytes(doc.size_bytes)}</td><td>${statusBadge(doc.analysis_status)}<small style="display:block;color:var(--muted);margin-top:4px">${escapeHTML(doc.processing_stage)}</small>${doc.error_message ? `<small style="display:block;color:var(--danger)">${escapeHTML(doc.error_message)}</small>` : ''}</td><td>${dateText(doc.created_at)}</td><td><div class="table-actions"><button data-action="download-document" data-id="${doc.id}" data-name="${escapeHTML(doc.original_name)}">Download</button><button data-action="reanalyze-document" data-id="${doc.id}">Re-analyze</button><button data-action="delete-document" data-id="${doc.id}">Delete</button></div></td></tr>`).join('')}</tbody></table></div>` : empty('No private documents', 'Upload a syllabus, previous paper, note, or reference document to begin.')}</section>`;
    if (hasProcessing) setTimeout(() => { if (state.page === 'documents') renderDocuments(); }, 1600);
  }

  async function renderPapers() {
    const papers = await api('/api/question-papers');
    content.innerHTML = `${pageIntro('Question paper history', 'View versions, review status, duplicate, edit, and export private papers.', user.role === 'teacher' ? '<button class="btn btn-primary" data-page="generate">✦ Generate new paper</button>' : '')}<section class="panel">${papers.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Paper</th><th>Teacher</th><th>Subject</th><th>Examination</th><th>Marks</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead><tbody>${papers.map(p => `<tr><td><div class="table-primary"><span>QP</span><p><b>${escapeHTML(p.paper_code)}</b><small>${escapeHTML(p.title)} · v${p.version}</small></p></div></td><td>${escapeHTML(p.teacher)}</td><td>${escapeHTML(p.subject)}</td><td>${escapeHTML(p.exam_type)}</td><td>${p.total_marks}</td><td>${statusBadge(p.status)}</td><td>${dateText(p.created_at)}</td><td><div class="table-actions"><button data-action="view-paper" data-id="${p.id}">View</button><button data-action="duplicate-paper" data-id="${p.id}">Duplicate</button><button data-action="export-paper" data-id="${p.id}" data-format="pdf">PDF</button></div></td></tr>`).join('')}</tbody></table></div>` : empty('No papers found', 'Papers will appear here after grounded generation.')}</section>`;
  }

  async function renderQuestionBank() {
    const items = await api('/api/question-bank');
    content.innerHTML = `${pageIntro('Question bank', 'Curate approved reference questions without bypassing syllabus grounding.', '<button class="btn btn-primary" data-action="toggle-qb-form">+ Add question</button>')}
      <section class="panel" id="qb-form-panel" hidden><form id="question-bank-form"><div class="form-grid"><label>Subject<select name="subject_id">${state.subjects.map(s => `<option value="${s.id}">${escapeHTML(s.code)} · ${escapeHTML(s.name)}</option>`).join('')}</select></label><label>Unit<input name="unit" required placeholder="UNIT I"></label><label>Topic<input name="topic" required></label><label>Marks<input name="marks" type="number" min="1" value="5"></label><label>Difficulty<select name="difficulty"><option>Easy</option><option selected>Medium</option><option>Hard</option></select></label><label>Bloom level<select name="bloom_level">${['Remember','Understand','Apply','Analyze','Evaluate','Create'].map(x => `<option>${x}</option>`).join('')}</select></label></div><label>Question<textarea name="question" required minlength="5"></textarea></label><label>Source reference<input name="source"></label><div class="form-footer"><button class="btn btn-primary">Add to question bank</button></div></form></section>
      <section class="panel">${items.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Question</th><th>Unit / Topic</th><th>Difficulty</th><th>Bloom</th><th>Marks</th><th>Usage</th></tr></thead><tbody>${items.map(q => `<tr><td style="white-space:normal;max-width:450px">${escapeHTML(q.question)}</td><td>${escapeHTML(q.unit)}<small style="display:block;color:var(--muted)">${escapeHTML(q.topic)}</small></td><td>${q.difficulty}</td><td>${q.bloom_level}</td><td>${q.marks}</td><td>${q.usage_count}</td></tr>`).join('')}</tbody></table></div>` : empty('Question bank is empty', 'Add curated questions for future academic reference.')}</section>`;
  }

  async function renderPatterns() {
    const patterns = await api('/api/question-patterns');
    content.innerHTML = `${pageIntro('Question patterns', 'Teacher-defined section structures saved from real blueprint requests.')}<section class="panel">${patterns.length ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Pattern</th><th>Total marks</th><th>Sections</th><th>Created</th><th></th></tr></thead><tbody>${patterns.map(pattern => `<tr><td><b>${escapeHTML(pattern.name)}</b></td><td>${pattern.total_marks}</td><td>${pattern.sections.map(s => `${escapeHTML(s.name)}: ${s.count} × ${s.marks}`).join('<br>')}</td><td>${dateText(pattern.created_at)}</td><td><button class="text-button" data-action="delete-pattern" data-id="${pattern.id}">Delete</button></td></tr>`).join('')}</tbody></table></div>` : empty('No saved patterns', 'Patterns are saved automatically when teachers create blueprints.')}</section>`;
  }

  async function renderGenerationHistory() {
    const logs = await api('/api/admin/generation-history');
    content.innerHTML = `${pageIntro('AI generation history', 'Actual queued, retrieval, generation, validation, failure, and completion stages.')}<section class="panel"><div class="activity-list">${logs.map(log => `<div class="activity-item"><span>${log.status === 'failed' ? '×' : log.progress === 100 ? '✓' : '●'}</span><p><strong>${escapeHTML(log.stage)}</strong><small>Operation ${escapeHTML(log.operation_id)} · ${log.progress}%${log.detail ? ` · ${escapeHTML(log.detail)}` : ''}</small></p><time>${dateText(log.created_at)}</time></div>`).join('') || empty('No generation activity', 'Real pipeline stage logs will appear here.')}</div></section>`;
  }

  async function renderSettings() {
    const settings = await api('/api/admin/settings');
    content.innerHTML = `${pageIntro('System settings', 'Non-secret academic workflow controls. Provider keys remain environment-only.')}<div class="academic-layout"><section class="panel"><div class="panel-head"><div><h3>Approval workflow</h3><p>Require administrative review before final approval</p></div></div><label class="choice-label"><input id="approval-enabled" type="checkbox" ${settings.approval_workflow.enabled ? 'checked' : ''}> Enable teacher → admin approval workflow</label><div class="form-footer"><button class="btn btn-primary" data-action="save-approval-setting">Save setting</button></div></section><section class="panel"><div class="panel-head"><div><h3>Security posture</h3><p>Environment-enforced safeguards</p></div></div><div class="activity-list">${Object.entries(settings.security).map(([key,value]) => `<div class="activity-item"><span>${value ? '✓' : '!'}</span><p><strong>${escapeHTML(pretty(key))}</strong><small>${value ? 'Enforced' : 'Attention required'}</small></p></div>`).join('')}</div></section></div><section class="panel" style="margin-top:16px"><div class="inline-warning">AI provider keys, database credentials, JWT secrets, storage paths, and origin controls are intentionally configurable only through server environment variables.</div></section>`;
  }

  async function renderActivity() {
    const logs = await api('/api/admin/activity-logs');
    content.innerHTML = `${pageIntro('Activity logs', 'Audited authentication, document, generation, edit, and governance events.')}<section class="panel"><div class="activity-list">${logs.map(log => `<div class="activity-item"><span>≡</span><p><strong>${escapeHTML(pretty(log.action.replace('.', ' · ')))}</strong><small>${escapeHTML(log.resource_type || 'system')} ${escapeHTML(log.resource_id || '')}</small></p><time>${dateText(log.created_at)}</time></div>`).join('') || empty('No activity yet', 'Audited system events appear here.')}</div></section>`;
  }

  function renderProfile() {
    const department = state.departments.find(item => item.id === user.department_id)?.name || 'Institution-wide';
    content.innerHTML = `${pageIntro('Profile & security', 'Your authorized NIET account and current access scope.')}<div class="academic-layout"><section class="panel"><div class="table-primary"><span style="width:58px;height:58px;font-size:14px">${initials(user.full_name)}</span><p><b style="font-size:16px">${escapeHTML(user.full_name)}</b><small>${escapeHTML(user.email)}</small></p></div><div class="activity-list" style="margin-top:18px"><div class="activity-item"><span>◎</span><p><strong>Role</strong><small>${pretty(user.role)}</small></p></div><div class="activity-item"><span>▤</span><p><strong>Access scope</strong><small>${escapeHTML(department)}</small></p></div><div class="activity-item"><span>⌾</span><p><strong>Session</strong><small>JWT session with immediate logout invalidation</small></p></div></div></section><section class="panel"><div class="panel-head"><div><h3>Change password</h3><p>Use at least 10 characters</p></div></div><form id="password-form"><label>Current password<input name="current_password" type="password" required minlength="8"></label><label>New password<input name="new_password" type="password" required minlength="10"></label><div class="form-footer"><button class="btn btn-primary">Change password</button></div></form></section></div>`;
  }

  async function renderWizard() {
    const w = state.wizard;
    if (!w.details.subject_id && state.subjects.length) w.details.subject_id = state.subjects[0].id;
    const steps = [['1','Exam details'],['2','Materials'],['3','Select portion'],['4','Paper pattern'],['5','Blueprint']];
    let pane = '';
    if (w.step === 1) pane = wizardDetails();
    if (w.step === 2) pane = await wizardMaterials();
    if (w.step === 3) pane = await wizardTopics();
    if (w.step === 4) pane = wizardPattern();
    if (w.step === 5) pane = wizardBlueprint();
    content.innerHTML = `${pageIntro('Generate question paper', 'A guided syllabus-first workflow. Every question must pass source and portion checks.')}
      <div class="wizard-shell"><aside class="panel wizard-steps">${steps.map(([n,label], i) => `<button class="wizard-step ${w.step === i+1 ? 'active' : ''} ${w.step > i+1 ? 'done' : ''}" data-action="wizard-goto" data-step="${i+1}" ${i+1 > w.step ? 'disabled' : ''}><span>${w.step > i+1 ? '✓' : n}</span><p><b>${label}</b><small>${['Subject & examination','Upload & analyze','Unit-wise topics','Sections & controls','Verify & generate'][i]}</small></p></button>`).join('')}</aside><section class="panel wizard-main">${pane}</section></div>`;
    setupUploadDropzone();
    if (w.step === 2 && w.hasProcessing) setTimeout(() => { if (state.page === 'generate' && state.wizard.step === 2) renderWizard(); }, 1600);
  }

  function wizardDetails() {
    const d = state.wizard.details;
    return `<div class="wizard-heading"><span class="kicker">Step 1 of 5</span><h2>Examination details</h2><p>Select an assigned subject and define the official paper header.</p></div><form id="wizard-details" class="form-grid"><label>Subject<select name="subject_id" required>${state.subjects.map(s => `<option value="${s.id}" ${s.id===d.subject_id?'selected':''}>${escapeHTML(s.code)} · ${escapeHTML(s.name)}</option>`).join('')}</select></label><label>Examination type<select name="exam_type">${['Internal Assessment','Internal Test','Model Examination','Semester Examination','Unit Test','Assignment','Practical Examination'].map(x => `<option ${x===d.exam_type?'selected':''}>${x}</option>`).join('')}</select></label><label>Exam duration (minutes)<input name="duration_minutes" type="number" min="15" max="600" value="${d.duration_minutes}"></label><label>Total marks<input name="total_marks" type="number" min="1" max="500" value="${d.total_marks}"></label><label>Exam date<input name="exam_date" type="date" value="${d.exam_date || ''}"></label><label>Academic year<input name="academic_year" required value="${escapeHTML(d.academic_year)}"></label><label>Class / Section<input name="class_section" value="${escapeHTML(d.class_section || '')}" placeholder="III CSE A"></label></form><div class="wizard-footer"><span></span><button class="btn btn-primary" data-action="wizard-next">Continue to materials →</button></div>`;
  }

  async function wizardMaterials() {
    const w = state.wizard;
    const docs = await api(`/api/documents?subject_id=${encodeURIComponent(w.details.subject_id)}`);
    w.documents = docs;
    w.hasProcessing = docs.some(d => ['uploaded','queued','processing'].includes(d.processing_status));
    return `<div class="wizard-heading"><span class="kicker">Step 2 of 5</span><h2>Academic materials</h2><p>Upload the official syllabus first, then add previous papers, notes, and references.</p></div><div class="form-grid"><label>Document category<select id="wizard-category">${['syllabus','portion','previous_paper','sample_paper','question_bank','notes','reference','assignment'].map(item => `<option value="${item}">${pretty(item)}</option>`).join('')}</select></label></div><label class="upload-zone" id="upload-zone"><input id="wizard-files" type="file" multiple accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"><span>↑</span><h3>Drop academic files here or click to browse</h3><p>PDF, Office, CSV, TXT, images, and scanned documents · max 25 MB each</p></label><div class="link-input"><input id="wizard-url" type="url" placeholder="Paste a public document or Google Drive link"><button class="btn btn-outline" data-action="add-document-url">Add public link</button></div><p class="upload-note">Private links are rejected. The system never bypasses authentication controls.</p><div class="file-list">${docs.map(docFileRow).join('') || empty('No materials for this subject', 'Upload the official syllabus to unlock unit extraction.')}</div><div class="wizard-footer"><button class="btn btn-outline" data-action="wizard-back">← Back</button><button class="btn btn-primary" data-action="wizard-next">Continue to portion →</button></div>`;
  }
  function docFileRow(doc) { const running = ['uploaded','queued','processing'].includes(doc.processing_status); return `<div class="file-row"><span class="file-chip ${doc.extension === '.pdf' ? 'pdf' : 'text'}">${escapeHTML(doc.extension.replace('.','').slice(0,3).toUpperCase())}</span><p><strong>${escapeHTML(doc.original_name)}</strong><small>${pretty(doc.category)} · ${formatBytes(doc.size_bytes)} · ${escapeHTML(doc.processing_stage)}</small>${doc.error_message ? `<small style="color:var(--danger)">${escapeHTML(doc.error_message)}</small>`:''}</p><div>${statusBadge(doc.analysis_status)}${running ? '<div class="file-progress"><div class="progress-track"><i class="indeterminate"></i></div></div>' : ''}</div></div>`; }

  async function wizardTopics() {
    const w = state.wizard;
    const result = await api(`/api/documents/subject/${w.details.subject_id}/topics`);
    if (!w.topics.length || w.topicSubject !== w.details.subject_id) {
      w.topics = result.units.flatMap(unit => unit.topics.map(topic => ({unit: unit.unit, title: unit.title, topic: topic.topic, selected: true})));
      const units = [...new Set(w.topics.map(topic => topic.unit))];
      w.unitWeightage = {};
      units.forEach((unit, index) => w.unitWeightage[unit] = Math.floor(100 / units.length) + (index < 100 % units.length ? 1 : 0));
      w.topicSubject = w.details.subject_id;
    }
    const grouped = Object.groupBy ? Object.groupBy(w.topics, item => item.unit) : w.topics.reduce((acc,item)=>((acc[item.unit] ||= []).push(item),acc),{});
    return `<div class="wizard-heading"><span class="kicker">Step 3 of 5</span><h2>Select examination portion</h2><p>Only checked topics are allowed during retrieval and generation. Review AI-extracted structure carefully.</p></div>${w.topics.length ? `<div class="topic-units">${Object.entries(grouped).map(([unit,topics]) => `<article class="unit-card"><div class="unit-head"><p><strong>${escapeHTML(unit)} — ${escapeHTML(topics[0].title || '')}</strong><small>${topics.filter(t=>t.selected).length} of ${topics.length} topics selected</small></p><label style="margin-left:auto">Weight % <input type="number" data-unit-weight="${escapeHTML(unit)}" min="0" max="100" value="${w.unitWeightage[unit] ?? 0}" style="width:64px;height:30px"></label><label style="margin-left:10px"><input type="checkbox" data-action="toggle-unit" data-unit="${escapeHTML(unit)}" ${topics.every(t=>t.selected)?'checked':''}> Select all</label></div><div class="topic-list">${topics.map((topic,idx) => `<label class="topic-check"><input type="checkbox" data-topic-unit="${escapeHTML(unit)}" data-topic-name="${escapeHTML(topic.topic)}" ${topic.selected?'checked':''}><span>${escapeHTML(topic.topic)}</span><button type="button" class="text-button" data-action="edit-topic" data-unit="${escapeHTML(unit)}" data-topic="${escapeHTML(topic.topic)}" aria-label="Edit topic">Edit</button></label>`).join('')}</div></article>`).join('')}</div>` : '<div class="inline-warning">No unit/topic structure was detected. Re-check the syllabus processing status or add the permitted topics manually below.</div>'}<div class="manual-topic"><input id="manual-unit" placeholder="Unit (e.g., UNIT II)"><input id="manual-topic" placeholder="Manual permitted topic"><button class="btn btn-outline" data-action="add-manual-topic">+ Add topic</button></div><div class="wizard-footer"><button class="btn btn-outline" data-action="wizard-back">← Back</button><button class="btn btn-primary" data-action="wizard-next">Continue to pattern →</button></div>`;
  }

  function wizardPattern() {
    const w = state.wizard; const total = w.sections.reduce((sum,s)=>sum+s.count*s.marks,0);
    return `<div class="wizard-heading"><span class="kicker">Step 4 of 5</span><h2>Question paper pattern</h2><p>Build sections and control difficulty. Drag section handles to reorder.</p></div><div class="pattern-builder" id="pattern-builder">${w.sections.map((s,i) => `<div class="pattern-row" draggable="true" data-index="${i}"><span class="drag-handle">⋮⋮</span><label>Section<input data-field="name" value="${escapeHTML(s.name)}"></label><label>Questions<input data-field="count" type="number" min="1" value="${s.count}"></label><label>Marks each<input data-field="marks" type="number" min="1" value="${s.marks}"></label><label>Question type<select data-field="question_type">${['MCQ','Fill in the blanks','True/False','One-word answer','Short Answer','Definition','Explain','Compare','Differentiate','Descriptive / Problem Solving','Essay','Numerical','Programming','Debugging','Output Prediction','Code Completion','Case Study','Scenario Based','Application Based','Diagram Based','Formula Based','Proof','Derivation'].map(x => `<option ${x===s.question_type?'selected':''}>${x}</option>`).join('')}</select></label><label>Choice<span class="choice-label"><input data-field="has_choice" type="checkbox" ${s.has_choice?'checked':''}> Either / or</span></label><button class="remove-row" data-action="remove-section" data-index="${i}" aria-label="Remove section">×</button></div>`).join('')}</div><button class="btn btn-outline btn-sm" style="margin-top:9px" data-action="add-section">+ Add section</button><div class="pattern-total"><span>Configured paper:</span><strong id="pattern-total">${total} marks</strong><span>Required: ${w.details.total_marks} marks</span></div><div class="distribution-grid"><section class="range-panel"><h3>Difficulty distribution</h3><div class="range-fields">${['easy','medium','hard'].map(x => `<label>${pretty(x)} %<input class="difficulty-input" data-level="${x}" type="number" min="0" max="100" value="${w.difficulty[x]}"></label>`).join('')}</div></section><section class="range-panel"><h3>Generation safeguards</h3><label>Previous paper influence<input id="previous-influence" type="number" min="0" max="100" value="20"></label><label>Novel questions<input id="novelty" type="number" min="0" max="100" value="80"></label></section><section class="range-panel"><h3>Bloom's taxonomy (optional)</h3><div class="range-fields">${Object.entries(w.bloom).map(([level,value]) => `<label>${level} %<input class="bloom-input" data-bloom="${level}" type="number" min="0" max="100" value="${value}"></label>`).join('')}</div></section></div><div class="wizard-footer"><button class="btn btn-outline" data-action="wizard-back">← Back</button><button class="btn btn-primary" data-action="build-blueprint">Generate blueprint →</button></div>`;
  }

  function wizardBlueprint() {
    const b = state.wizard.blueprint?.allocation_json;
    if (!b) return `<div class="wizard-heading"><h2>Blueprint unavailable</h2><p>Return to the paper pattern and generate a validated allocation.</p></div><button class="btn btn-outline" data-action="wizard-back">← Back</button>`;
    const block = (title,obj) => `<div class="blueprint-block"><h4>${title}</h4>${Object.entries(obj).map(([k,v])=>`<p><span>${escapeHTML(k)}</span><b>${v} question${v===1?'':'s'}</b></p>`).join('')}</div>`;
    return `<div class="wizard-heading"><span class="kicker">Step 5 of 5</span><h2>Verify question paper blueprint</h2><p>Review allocation before any questions are generated.</p></div><div class="blueprint-summary"><div class="blueprint-header"><h3>${b.total_questions} questions across ${b.sections.length} sections</h3><span>${b.total_marks} marks</span></div><div class="blueprint-body">${block('Unit distribution',b.unit_distribution)}${block('Difficulty',b.difficulty_distribution)}${block("Bloom's taxonomy",b.bloom_distribution)}</div></div><div class="grounding-notice">✓ Generation will retrieve only analyzed documents owned by you, for this assigned subject and selected portion. Previous questions influence style and duplicate checks—not allowed content.</div><div class="wizard-footer"><button class="btn btn-outline" data-action="wizard-back">← Revise pattern</button><button class="btn btn-primary" data-action="generate-paper">✦ Generate validated paper</button></div>`;
  }

  function collectWizardDetails() {
    const form = $('#wizard-details'); if (!form || !form.reportValidity()) return false;
    const values = Object.fromEntries(new FormData(form));
    const previousSubject = state.wizard.details.subject_id;
    values.duration_minutes = Number(values.duration_minutes); values.total_marks = Number(values.total_marks);
    state.wizard.details = values;
    if (previousSubject && previousSubject !== values.subject_id) { state.wizard.topics=[]; state.wizard.blueprint=null; }
    return true;
  }
  function collectPattern() {
    state.wizard.sections = $$('.pattern-row').map(row => ({
      name: $('[data-field="name"]',row).value.trim(), count:Number($('[data-field="count"]',row).value), marks:Number($('[data-field="marks"]',row).value),
      question_type:$('[data-field="question_type"]',row).value, instructions: 'Answer ALL questions', has_choice:$('[data-field="has_choice"]',row).checked
    }));
    $$('.difficulty-input').forEach(input => state.wizard.difficulty[input.dataset.level] = Number(input.value));
    $$('.bloom-input').forEach(input => state.wizard.bloom[input.dataset.bloom] = Number(input.value));
  }
  function collectTopics() {
    $$('[data-topic-unit]').forEach(input => { const found=state.wizard.topics.find(t=>t.unit===input.dataset.topicUnit&&t.topic===input.dataset.topicName); if(found) found.selected=input.checked; });
    $$('[data-unit-weight]').forEach(input => state.wizard.unitWeightage[input.dataset.unitWeight] = Number(input.value));
  }

  async function createBlueprint() {
    collectPattern();
    const w=state.wizard, patternTotal=w.sections.reduce((sum,s)=>sum+s.count*s.marks,0), diffTotal=Object.values(w.difficulty).reduce((a,b)=>a+b,0), bloomTotal=Object.values(w.bloom).reduce((a,b)=>a+b,0);
    if(patternTotal!==Number(w.details.total_marks)) throw new Error(`Section pattern totals ${patternTotal}; required total is ${w.details.total_marks}.`);
    if(diffTotal!==100) throw new Error(`Difficulty percentages total ${diffTotal}; they must total 100.`);
    if(bloomTotal!==100) throw new Error(`Bloom percentages total ${bloomTotal}; they must total 100.`);
    const payload={...w.details, sections:w.sections, selected_topics:w.topics.map(t=>({unit:t.unit,topic:t.topic,selected:t.selected})), difficulty:w.difficulty, bloom_distribution:w.bloom, unit_weightage:w.unitWeightage, previous_paper_influence:Number($('#previous-influence')?.value||20), novelty:Number($('#novelty')?.value||80)};
    w.blueprint=await api('/api/question-paper/blueprint',{method:'POST',body:JSON.stringify(payload)}); w.step=5; await renderWizard(); toast('Blueprint ready','Verify allocation before generation.');
  }

  function showProcessing(title='Processing academic materials') { const o=$('#processing-overlay');o.hidden=false;$('#processing-title').textContent=title;$('#processing-stage').textContent='Queued';$('#processing-bar').style.width='0%';$('#processing-percent').textContent='0%';$('#processing-steps').innerHTML='';$('#processing-close').hidden=true; }
  async function pollGeneration(operationId) {
    showProcessing('Generating grounded question paper');
    for (let attempt=0;attempt<240;attempt++) {
      const result=await api(`/api/question-paper/operations/${operationId}`);
      $('#processing-stage').textContent=result.detail||result.stage;$('#processing-bar').style.width=`${result.progress}%`;$('#processing-percent').textContent=`${result.progress}%`;
      $('#processing-steps').innerHTML=result.stages.map(s=>`<li class="${s.status==='failed'?'failed':s.status==='completed'?'done':''}">${s.status==='completed'?'✓':s.status==='failed'?'×':'●'} ${escapeHTML(s.stage)}</li>`).join('');
      if(result.status==='failed'){ $('#processing-close').hidden=false; throw new Error(result.detail||'Generation failed.'); }
      if(result.progress===100&&result.paper_id){ $('#processing-overlay').hidden=true; await viewPaper(result.paper_id); toast('Question paper generated','Every displayed question passed grounding and constraint checks.'); return; }
      await new Promise(resolve=>setTimeout(resolve,900));
    } throw new Error('Generation is still running. Check question paper history shortly.');
  }

  async function viewPaper(id) { const paper=await api(`/api/question-papers/${id}`);state.currentPaper=paper;state.page='paper';$('#page-title').textContent=paper.paper_code;$('#page-breadcrumb').textContent='Paper preview';renderPaper(paper); }
  function renderPaper(p) {
    const sections={};p.questions.forEach(q=>(sections[q.section]||=[]).push(q));
    const cfg=Object.fromEntries((p.settings.sections||[]).map(s=>[s.name,s]));
    const examDate=p.exam_date?dateText(p.exam_date):'—'; const c=p.coverage||{};
    content.innerHTML=`${pageIntro(p.title,`${p.paper_code} · Version ${p.version}`, '<button class="btn btn-outline" data-page="papers">← History</button>')}
      <div class="paper-workspace"><article class="paper-sheet" id="print-paper"><header class="exam-header"><h2>NEHRU INSTITUTE OF ENGINEERING AND TECHNOLOGY</h2><p>Coimbatore, Tamil Nadu</p><h3>${escapeHTML(String(p.subject.department).toUpperCase())}</h3><p>${escapeHTML(String(p.exam_type).toUpperCase())} — ${escapeHTML(p.academic_year)}</p><div class="exam-meta"><div><b>Subject:</b> ${escapeHTML(p.subject.name)}</div><div><b>Subject Code:</b> ${escapeHTML(p.subject.code)}</div><div><b>Semester:</b> ${escapeHTML(p.subject.semester)}</div><div><b>Regulation:</b> ${escapeHTML(p.subject.regulation)}</div><div><b>Date:</b> ${examDate}</div><div><b>Duration:</b> ${Math.floor(p.duration_minutes/60)} Hours</div><div><b>Class / Section:</b> ${escapeHTML(p.class_section||'—')}</div><div><b>Maximum Marks:</b> ${p.total_marks}</div></div></header>${Object.entries(sections).map(([name,questions])=>`<section><div class="paper-section-title"><h3>${escapeHTML(name)}</h3><p>${escapeHTML(cfg[name]?.instructions||'Answer ALL questions')}</p><p>${questions.length} × ${questions[0]?.marks||0} = ${questions.reduce((s,q)=>s+q.marks,0)} Marks</p></div>${questions.map(q=>`<div class="paper-question"><strong>${escapeHTML(q.question_number)}.</strong>${escapeHTML(q.text)}<span class="qmarks">[${q.marks}]</span><div class="question-actions"><button data-action="source-question" data-id="${q.id}">Source</button><button data-action="edit-question" data-id="${q.id}">Edit</button><button data-action="regenerate-question" data-id="${q.id}">Regenerate</button><button data-action="duplicate-question" data-id="${q.id}">Duplicate</button><button data-action="delete-question" data-id="${q.id}">Delete</button></div>${q.alternative_text?`<div class="or-label">OR</div><div class="alternative">${escapeHTML(q.alternative_text)}</div>`:''}</div>`).join('')}</section>`).join('')}<div class="paper-end">— END OF QUESTION PAPER —</div></article>
      <aside class="paper-side"><section class="panel coverage-score"><div class="large-ring" style="--score:${c.syllabus_coverage||0}"><strong>${c.syllabus_coverage||0}%</strong></div><h3>Syllabus coverage</h3><div class="coverage-list">${Object.entries(c.unit_coverage||{}).map(([u,v])=>`<p><span>${escapeHTML(u)}</span><b>${v}%</b></p>`).join('')}<p><span>Portion compliance</span><b>${c.portion_compliance||0}%</b></p><p><span>Pattern compliance</span><b>${c.pattern_compliance||0}%</b></p><p><span>Duplicate risk</span><b class="risk-low">${c.duplicate_risk||'Review'}</b></p></div><p class="upload-note">${escapeHTML(c.indicator_note||'Confidence indicator; teacher review required.')}</p></section><section class="panel side-actions">${user.role==='teacher'?`<button class="btn btn-outline" data-action="add-manual-question" data-id="${p.id}">+ Add manual question</button>`:''}<button class="btn btn-primary" data-action="export-paper" data-id="${p.id}" data-format="pdf">↓ Download PDF</button><button class="btn btn-outline" data-action="export-paper" data-id="${p.id}" data-format="docx">Download editable DOCX</button><button class="btn btn-outline" data-action="export-paper" data-id="${p.id}" data-format="txt">Download TXT</button><button class="btn btn-outline" data-action="export-answers" data-id="${p.id}" data-format="pdf">Question paper + key</button><button class="btn btn-outline" data-action="print-paper">Print paper</button>${user.role==='teacher'?`<button class="btn btn-gold" data-action="submit-paper" data-id="${p.id}">Submit for admin review</button>`:p.status==='admin_review'?`<button class="btn btn-gold" data-action="approve-paper" data-id="${p.id}">Approve</button><button class="btn btn-outline" data-action="request-changes" data-id="${p.id}">Request changes</button>`:''}<span class="version-badge">${statusBadge(p.status)} · ${p.paper_code}</span></section></aside></div>`;
  }

  function setupUploadDropzone() { const zone=$('#upload-zone'),input=$('#wizard-files');if(!zone||!input)return;zone.addEventListener('click',()=>input.click());input.addEventListener('change',()=>uploadWizardFiles(input.files));['dragenter','dragover'].forEach(type=>zone.addEventListener(type,e=>{e.preventDefault();zone.classList.add('dragover')}));['dragleave','drop'].forEach(type=>zone.addEventListener(type,e=>{e.preventDefault();zone.classList.remove('dragover')}));zone.addEventListener('drop',e=>uploadWizardFiles(e.dataTransfer.files)); }
  async function uploadWizardFiles(files) { if(!files.length)return;const form=new FormData();[...files].forEach(file=>form.append('files',file));form.append('subject_id',state.wizard.details.subject_id);form.append('category',$('#wizard-category').value);try{await api('/api/documents/upload',{method:'POST',body:form});toast('Upload complete','Real extraction and analysis has started.');renderWizard();}catch(e){toast('Upload failed',e.message,'error')} }

  document.addEventListener('click', async event => {
    const pageButton=event.target.closest('[data-page]'); if(pageButton){navigate(pageButton.dataset.page);return;}
    const button=event.target.closest('[data-action]'); if(!button)return; const action=button.dataset.action;
    try {
      if(action==='retry-page') return navigate(state.page);
      if(action==='toggle-teacher-form') { const el=$('#teacher-form-card');el.hidden=!el.hidden;return; }
      if(action==='toggle-doc-upload') { const el=$('#doc-upload-panel');el.hidden=!el.hidden;return; }
      if(action==='toggle-qb-form') { const el=$('#qb-form-panel');el.hidden=!el.hidden;return; }
      if(action==='teacher-deactivate' && await confirmAction('Deactivate teacher?','The account will be signed out. Academic records are retained.')) { await api(`/api/admin/teachers/${button.dataset.id}`,{method:'DELETE'});toast('Teacher deactivated');return renderTeachers(); }
      if(action==='teacher-reset'){const password=prompt('Enter a temporary password (minimum 10 characters):','Welcome@123');if(password){await api(`/api/admin/teachers/${button.dataset.id}/reset-password`,{method:'POST',body:JSON.stringify({temporary_password:password})});toast('Temporary password set','Teacher must change it after sign-in.')}return;}
      if(action==='delete-department' && await confirmAction('Deactivate department?','Existing academic records will be retained.')){await api(`/api/departments/${button.dataset.id}`,{method:'DELETE'});await loadMasters();return renderAcademic(state.page);}
      if(action==='delete-subject' && await confirmAction('Deactivate subject?','Existing papers remain available.')){await api(`/api/subjects/${button.dataset.id}`,{method:'DELETE'});await loadMasters();return renderAcademic(state.page);}
      if(action==='delete-pattern' && await confirmAction('Delete question pattern?','Generated papers that used this structure are retained.')){await api(`/api/question-patterns/${button.dataset.id}`,{method:'DELETE'});toast('Pattern deleted');return renderPatterns();}
      if(action==='save-approval-setting'){await api('/api/admin/settings/approval_workflow',{method:'PUT',body:JSON.stringify({enabled:$('#approval-enabled').checked})});toast('Approval setting saved');return renderSettings();}
      if(action==='download-document')return download(`/api/documents/${button.dataset.id}/download`,button.dataset.name);
      if(action==='reanalyze-document'){await api(`/api/documents/${button.dataset.id}/analyze`,{method:'POST'});toast('Re-analysis queued');return renderDocuments();}
      if(action==='delete-document' && await confirmAction('Delete document?','Its extracted chunks and private index will be removed.')){await api(`/api/documents/${button.dataset.id}`,{method:'DELETE'});toast('Document deleted');return renderDocuments();}
      if(action==='view-paper')return viewPaper(button.dataset.id);
      if(action==='duplicate-paper'){const paper=await api(`/api/question-papers/${button.dataset.id}/duplicate`,{method:'POST'});toast('Draft copy created',paper.paper_code);return renderPapers();}
      if(action==='export-paper')return download(`/api/question-papers/${button.dataset.id}/export/${button.dataset.format}`,`question-paper.${button.dataset.format}`);
      if(action==='export-answers')return download(`/api/question-papers/${button.dataset.id}/export/${button.dataset.format}?include_answers=true`,`paper-with-answer-key.${button.dataset.format}`);
      if(action==='print-paper'){window.print();return;}
      if(action==='generate-subject'){state.wizard.details.subject_id=button.dataset.id;state.wizard.step=1;return navigate('generate');}
      if(action==='wizard-next'){if(state.wizard.step===1&&!collectWizardDetails())return;if(state.wizard.step===2){const syllabus=state.wizard.documents?.some(d=>d.category==='syllabus'&&d.analysis_status==='completed');if(!syllabus)throw new Error('Wait for at least one syllabus to complete analysis.');}if(state.wizard.step===3){collectTopics();if(!state.wizard.topics.some(t=>t.selected))throw new Error('Select at least one examination portion topic.');const weightTotal=Object.values(state.wizard.unitWeightage).reduce((sum,value)=>sum+value,0);if(weightTotal!==100)throw new Error(`Unit weightages total ${weightTotal}; they must total 100.`);}state.wizard.step++;return renderWizard();}
      if(action==='wizard-back'){if(state.wizard.step>1)state.wizard.step--;return renderWizard();}
      if(action==='wizard-goto'){if(state.wizard.step===3)collectTopics();state.wizard.step=Number(button.dataset.step);return renderWizard();}
      if(action==='add-document-url'){const url=$('#wizard-url').value.trim();if(!url)throw new Error('Enter a public document URL.');await api('/api/documents/url',{method:'POST',body:JSON.stringify({url,subject_id:state.wizard.details.subject_id,category:$('#wizard-category').value})});toast('Link accessible','Content extraction has started.');return renderWizard();}
      if(action==='toggle-unit'){collectTopics();state.wizard.topics.filter(t=>t.unit===button.dataset.unit).forEach(t=>t.selected=button.checked);return renderWizard();}
      if(action==='edit-topic'){collectTopics();const item=state.wizard.topics.find(t=>t.unit===button.dataset.unit&&t.topic===button.dataset.topic);const revised=prompt('Edit the extracted topic label:',item?.topic||'');if(item&&revised?.trim()){item.topic=revised.trim();state.wizard.blueprint=null;return renderWizard();}return;}
      if(action==='add-manual-topic'){collectTopics();const unit=$('#manual-unit').value.trim(),topic=$('#manual-topic').value.trim();if(!unit||!topic)throw new Error('Enter both a unit and a permitted topic.');state.wizard.topics.push({unit,topic,title:'Teacher-defined portion',selected:true});return renderWizard();}
      if(action==='add-section'){collectPattern();state.wizard.sections.push({name:`PART ${String.fromCharCode(65+state.wizard.sections.length)}`,count:1,marks:5,question_type:'Descriptive / Problem Solving',instructions:'Answer ALL questions',has_choice:false});return renderWizard();}
      if(action==='remove-section'){collectPattern();state.wizard.sections.splice(Number(button.dataset.index),1);return renderWizard();}
      if(action==='build-blueprint')return createBlueprint();
      if(action==='generate-paper'){const result=await api('/api/question-paper/generate',{method:'POST',body:JSON.stringify({blueprint_id:state.wizard.blueprint.id,title:`${state.wizard.details.exam_type} Question Paper`})});return pollGeneration(result.operation_id).catch(e=>toast('Generation stopped',e.message,'error'));}
      if(action==='source-question'){const q=state.currentPaper.questions.find(x=>x.id===button.dataset.id);$('#source-content').innerHTML=`<div class="source-meta"><span>${escapeHTML(q.unit)}</span><span>${escapeHTML(q.topic)}</span><span>${q.difficulty}</span><span>Bloom: ${q.bloom_level}</span><span>Pattern: ${escapeHTML(q.section)} · ${escapeHTML(q.question_type)} · ${q.marks} marks</span><span>${Math.round(q.confidence_score*100)}% confidence</span></div><p>${escapeHTML(q.validation.rationale||'Grounded in selected-portion retrieval.')}</p>${q.sources.map(s=>`<div class="source-card"><strong>${escapeHTML(s.document_name)}</strong><small> · ${escapeHTML(s.location||'Document')}</small><p>${escapeHTML(s.excerpt)}</p></div>`).join('')||'<p>Manual question: no automated source mapping.</p>'}`;$('#source-dialog').showModal();return;}
      if(action==='edit-question'){const q=state.currentPaper.questions.find(x=>x.id===button.dataset.id);$('#edit-question-id').value=q.id;$('#edit-question-text').value=q.text;$('#edit-question-marks').value=q.marks;$('#edit-question-position').value=q.position;$('#edit-question-difficulty').value=q.difficulty;$('#edit-question-type').value=q.question_type;$('#edit-question-unit').value=q.unit;$('#edit-question-topic').value=q.topic;$('#edit-dialog').showModal();return;}
      if(action==='regenerate-question'){button.disabled=true;const p=await api(`/api/questions/${button.dataset.id}/regenerate`,{method:'POST'});state.currentPaper=p;renderPaper(p);toast('Different grounded question generated');return;}
      if(action==='duplicate-question'){const p=await api(`/api/questions/${button.dataset.id}/duplicate`,{method:'POST'});state.currentPaper=p;renderPaper(p);toast('Question duplicated','The intentional duplicate is marked for manual review.');return;}
      if(action==='add-manual-question'){const section=prompt('Section name:','PART A'),text=section&&prompt('Manual question text:');if(!text)return;const marks=Number(prompt('Marks:','2')),unit=prompt('Unit:','UNIT I'),topic=prompt('Topic:');if(!marks||!unit||!topic)throw new Error('Section, text, marks, unit, and topic are required.');const p=await api(`/api/question-papers/${button.dataset.id}/questions`,{method:'POST',body:JSON.stringify({section,text,marks,unit,topic,difficulty:'Medium',bloom_level:'Understand',question_type:'Descriptive'})});state.currentPaper=p;renderPaper(p);toast('Manual question added','Teacher review is required.');return;}
      if(action==='delete-question'&&await confirmAction('Delete question?','The paper mark total may no longer match its pattern.')){await api(`/api/questions/${button.dataset.id}`,{method:'DELETE'});return viewPaper(state.currentPaper.id);}
      if(action==='submit-paper'){await api(`/api/question-papers/${button.dataset.id}/approval`,{method:'POST',body:JSON.stringify({action:'submit',comment:'Submitted after teacher review.'})});toast('Submitted for admin review');return viewPaper(button.dataset.id);}
      if(action==='approve-paper'){await api(`/api/question-papers/${button.dataset.id}/approval`,{method:'POST',body:JSON.stringify({action:'approve',comment:'Approved by academic administrator.'})});toast('Question paper approved');return viewPaper(button.dataset.id);}
      if(action==='request-changes'){const comment=prompt('Describe the required changes:');if(comment){await api(`/api/question-papers/${button.dataset.id}/approval`,{method:'POST',body:JSON.stringify({action:'request_changes',comment})});toast('Changes requested');return viewPaper(button.dataset.id);}return;}
    } catch(error){toast('Action could not be completed',error.message,'error');}
  });

  document.addEventListener('submit', async event => {
    const form=event.target; event.preventDefault(); if(!form.reportValidity())return;
    try {
      if(form.id==='teacher-create-form'){const fd=new FormData(form),payload=Object.fromEntries(fd);payload.subject_ids=[...form.elements.subject_ids.selectedOptions].map(o=>o.value);payload.is_active=true;await api('/api/admin/teachers',{method:'POST',body:JSON.stringify(payload)});toast('Teacher account created');return renderTeachers();}
      if(form.id==='department-form'){await api('/api/departments',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});toast('Department added');await loadMasters();return renderAcademic(state.page);}
      if(form.id==='subject-form'){const payload=Object.fromEntries(new FormData(form));payload.credits=Number(payload.credits);payload.units_json=[];await api('/api/subjects',{method:'POST',body:JSON.stringify(payload)});toast('Subject added');await loadMasters();return renderAcademic(state.page);}
      if(form.id==='library-upload-form'){const fd=new FormData(form),files=form.elements.files.files;fd.delete('files');[...files].forEach(file=>fd.append('files',file));await api('/api/documents/upload',{method:'POST',body:fd});toast('Upload complete','Analysis has started.');return renderDocuments();}
      if(form.id==='question-bank-form'){const payload=Object.fromEntries(new FormData(form));payload.marks=Number(payload.marks);await api('/api/question-bank',{method:'POST',body:JSON.stringify(payload)});toast('Question added');return renderQuestionBank();}
      if(form.id==='password-form'){await api('/api/auth/change-password',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});sessionStorage.clear();location.replace('/login.html');}
    } catch(error){toast('Form could not be saved',error.message,'error');}
  });

  $('#edit-question-form').addEventListener('submit',async event=>{event.preventDefault();try{const id=$('#edit-question-id').value,payload={text:$('#edit-question-text').value,marks:Number($('#edit-question-marks').value),position:Number($('#edit-question-position').value),difficulty:$('#edit-question-difficulty').value,question_type:$('#edit-question-type').value,unit:$('#edit-question-unit').value,topic:$('#edit-question-topic').value};const paper=await api(`/api/questions/${id}`,{method:'PUT',body:JSON.stringify(payload)});$('#edit-dialog').close();state.currentPaper=paper;renderPaper(paper);toast('Question updated','Manual review is now required.');}catch(e){toast('Edit failed',e.message,'error')}});
  document.addEventListener('input',event=>{if(event.target.id==='teacher-search'||event.target.id==='teacher-department-filter'){const term=($('#teacher-search')?.value||'').toLowerCase(),dept=$('#teacher-department-filter')?.value||'';$$('#teacher-table-body tr').forEach(row=>row.hidden=!(row.dataset.search.includes(term)&&(!dept||row.dataset.department===dept)));}if(event.target.closest('.pattern-row')){const rows=$$('.pattern-row'),total=rows.reduce((s,row)=>s+Number($('[data-field="count"]',row).value||0)*Number($('[data-field="marks"]',row).value||0),0);if($('#pattern-total'))$('#pattern-total').textContent=`${total} marks`;}});
  let draggedSection = null;
  document.addEventListener('dragstart', event => {
    const row = event.target.closest('.pattern-row');
    if (row) { draggedSection = Number(row.dataset.index); event.dataTransfer.effectAllowed = 'move'; }
  });
  document.addEventListener('dragover', event => { if (event.target.closest('.pattern-row')) event.preventDefault(); });
  document.addEventListener('drop', event => {
    const row = event.target.closest('.pattern-row');
    if (!row || draggedSection === null) return;
    event.preventDefault(); collectPattern();
    const destination = Number(row.dataset.index);
    const [moved] = state.wizard.sections.splice(draggedSection, 1);
    state.wizard.sections.splice(destination, 0, moved);
    draggedSection = null; renderWizard();
  });

  $('#logout-button').addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'});}catch{}sessionStorage.clear();location.replace('/login.html');});
  $('#menu-button').addEventListener('click',()=>$('#sidebar').classList.add('open'));$('#sidebar-close').addEventListener('click',()=>$('#sidebar').classList.remove('open'));
  $('#theme-button').addEventListener('click',()=>{document.body.classList.toggle('dark');localStorage.setItem('niet_theme',document.body.classList.contains('dark')?'dark':'light');});
  $('#processing-close').addEventListener('click',()=>$('#processing-overlay').hidden=true);

  async function init() {
    if(!token){location.replace('/login.html');return;}
    if(localStorage.getItem('niet_theme')==='dark')document.body.classList.add('dark');
    try{user=await api('/api/auth/me');sessionStorage.setItem('niet_user',JSON.stringify(user));await loadMasters();buildNav();const name=user.full_name;$('#sidebar-name').textContent=name;$('#sidebar-role').textContent=pretty(user.role);$('#user-avatar').textContent=$('#top-avatar').textContent=initials(name);const health=await fetch('/api/health').then(r=>r.json()).catch(()=>null);if(health)$('#provider-badge').textContent=health.ai_provider==='local'?'Local grounded engine':health.ai_provider;$('#app-loader').hidden=true;navigate(user.role==='teacher'?'dashboard':'admin-dashboard');}catch(error){sessionStorage.clear();location.replace('/login.html');}
  }
  init();
})();
