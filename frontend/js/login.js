(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const form = $('#login-form');
  const error = $('#login-error');
  const button = $('#login-button');
  let selectedRole = new URLSearchParams(location.search).get('role') === 'admin' ? 'admin' : 'teacher';

  function selectRole(role) {
    selectedRole = role;
    document.querySelectorAll('.role-toggle button').forEach(item => item.classList.toggle('active', item.dataset.role === role));
    $('#auth-title').textContent = role === 'admin' ? 'Administrator sign in' : 'Welcome back';
    $('#auth-subtitle').textContent = role === 'admin'
      ? 'Access academic operations and approval controls.'
      : 'Sign in with credentials provided by the administrator.';
    $('#username').placeholder = role === 'admin' ? 'admin@niet.edu' : 'name@niet.edu';
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {headers: {'Content-Type': 'application/json', ...(options.headers || {})}, ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Unable to complete the request.');
    return data;
  }

  document.querySelectorAll('.role-toggle button').forEach(item => item.addEventListener('click', () => selectRole(item.dataset.role)));
  selectRole(selectedRole);

  $('.password-toggle').addEventListener('click', (event) => {
    const password = $('#password');
    const visible = password.type === 'text';
    password.type = visible ? 'password' : 'text';
    event.currentTarget.textContent = visible ? 'Show' : 'Hide';
    event.currentTarget.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    error.textContent = '';
    if (!form.reportValidity()) return;
    button.disabled = true;
    button.querySelector('span').textContent = 'Verifying credentials…';
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({username: $('#username').value.trim(), password: $('#password').value})
      });
      if (data.user.role !== selectedRole && !(selectedRole === 'admin' && data.user.role === 'super_admin')) {
        // Role tabs are contextual, not an authorization mechanism; explain a mismatch clearly.
        await fetch('/api/auth/logout', {method: 'POST', headers: {Authorization: `Bearer ${data.access_token}`}});
        throw new Error(`This is a ${data.user.role} account. Choose the matching sign-in tab.`);
      }
      sessionStorage.setItem('niet_token', data.access_token);
      sessionStorage.setItem('niet_user', JSON.stringify(data.user));
      location.replace('/portal.html');
    } catch (err) {
      error.textContent = err.message;
      button.disabled = false;
      button.querySelector('span').textContent = 'Sign in securely';
    }
  });

  const forgotDialog = $('#forgot-dialog');
  $('#forgot-link').addEventListener('click', () => {
    $('#forgot-email').value = $('#username').value.includes('@') ? $('#username').value : '';
    $('#forgot-message').textContent = '';
    forgotDialog.showModal();
  });
  $('#forgot-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = $('#forgot-email');
    if (!input.reportValidity()) return;
    try {
      const data = await api('/api/auth/forgot-password', {method: 'POST', body: JSON.stringify({email: input.value})});
      $('#forgot-message').textContent = data.message;
    } catch (err) { $('#forgot-message').textContent = err.message; }
  });

  const token = sessionStorage.getItem('niet_token');
  if (token) {
    fetch('/api/auth/me', {headers: {Authorization: `Bearer ${token}`}}).then(response => {
      if (response.ok) location.replace('/portal.html');
      else sessionStorage.clear();
    }).catch(() => {});
  }
})();
