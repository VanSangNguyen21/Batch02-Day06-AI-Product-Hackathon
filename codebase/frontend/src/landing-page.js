'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('next') === 'main') {
    window.location.href = 'auth.html?mode=login';
  }
});
