/**
 * Swile Enroll Bookmarklet
 *
 * Copies the Swile refresh token (the lunchr:rt cookie) to the clipboard so it
 * can be pasted into Budget Forecaster → Settings → Swile. Must be run from
 * team.swile.co while logged in.
 *
 * Usage:
 * 1. Log in to https://team.swile.co/
 * 2. Run this bookmarklet
 * 3. Paste the copied token into the Swile enroll form
 */

(function swileEnroll() {
  'use strict';

  if (!window.location.hostname.includes('swile.co')) {
    alert('Run this from team.swile.co while logged in.');
    return;
  }

  const match = document.cookie.match(/lunchr:rt=([^;]+)/);
  if (!match) {
    alert('Swile refresh token not found. Make sure you are logged in to team.swile.co.');
    return;
  }

  const token = decodeURIComponent(match[1]);
  const done = () => alert('Swile token copied. Paste it into Budget Forecaster → Settings → Swile.');

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(token).then(done, () => prompt('Copy this Swile token:', token));
  } else {
    prompt('Copy this Swile token:', token);
  }
})();
