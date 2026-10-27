const logoutButton = document.querySelector('#logout-button');
const currentUserLabel = document.querySelector('#current-user');

fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' })
  .then(async (response) => {
    if (response.status === 401) {
      window.location.replace('/login.html');
      return null;
    }
    if (!response.ok) throw new Error('Unable to verify the current session.');
    return response.json();
  })
  .then((payload) => {
    if (payload?.user && currentUserLabel) currentUserLabel.textContent = payload.user.username;
  })
  .catch(() => {
    if (currentUserLabel) currentUserLabel.textContent = 'Session check failed';
  });

logoutButton?.addEventListener('click', async () => {
  logoutButton.disabled = true;
  try {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    if (!response.ok) throw new Error('Sign out failed.');
    window.location.replace('/login.html');
  } catch {
    logoutButton.disabled = false;
  }
});
