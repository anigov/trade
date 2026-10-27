const form = document.querySelector('#login-form');
const status = document.querySelector('#login-status');

fetch('/api/auth/me', { credentials: 'same-origin' })
  .then((response) => response.ok ? response.json() : null)
  .then((payload) => {
    if (payload?.user) window.location.replace('/');
  })
  .catch(() => {});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const values = Object.fromEntries(new FormData(form).entries());
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  status.textContent = 'Signing in…';

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Sign-in failed.');
    window.location.replace('/');
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
  }
});
