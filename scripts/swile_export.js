/**
 * Swile Export Bookmarklet
 *
 * This script exports Swile operations and wallets to JSON files.
 * It must be executed from https://team.swile.co/ while logged in.
 *
 * Usage:
 * 1. Log in to https://team.swile.co/
 * 2. Run this script via the bookmarklet or browser console
 * 3. The operations.json and wallets.json files will be downloaded automatically
 */

(async function swileExport() {
  'use strict';

  // Configuration
  const CONFIG = {
    // API endpoints
    OPERATIONS_URL: 'https://neobank-api.swile.co/api/v3/user/operations',
    WALLETS_URL: 'https://employee-bff-api.swile.co/api/wallets/get-wallets',

    // Static API key from Swile web application
    API_KEY: '393e1b0abfebf6da88aa57cfa1a126f97bf0b818',

    // Pagination settings
    ITEMS_PER_PAGE: 100,
    MAX_PAGES: 50, // Safety limit (~5000 operations max)
  };

  /**
   * Retrieves the JWT from cookies
   * @returns {string|null} The JWT or null if not found
   */
  function getJWT() {
    const match = document.cookie.match(/lunchr:jwt=([^;]+)/);
    return match ? match[1] : null;
  }

  /**
   * Builds headers for API requests
   * @param {string} jwt - The authentication JWT
   * @param {object} extra - Additional headers
   * @returns {object} The headers object
   */
  function buildHeaders(jwt, extra = {}) {
    return {
      Authorization: `Bearer ${jwt}`,
      'X-API-Key': CONFIG.API_KEY,
      'X-Lunchr-Platform': 'web',
      'Content-Type': 'application/json',
      ...extra,
    };
  }

  /**
   * Fetches wallet data
   * @param {string} jwt - The authentication JWT
   * @returns {Promise<object>} The wallets data
   */
  async function fetchWallets(jwt) {
    const response = await fetch(CONFIG.WALLETS_URL, {
      headers: buildHeaders(jwt, { 'X-API-Version': '0' }),
    });

    if (!response.ok) {
      throw new Error(`Wallets error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Fetches all operations with pagination
   * @param {string} jwt - The authentication JWT
   * @param {function} onProgress - Progress callback (page, totalItems)
   * @returns {Promise<object>} Operations in the format expected by SwileBankAdapter
   */
  async function fetchAllOperations(jwt, onProgress = () => {}) {
    const allItems = [];
    let cursor = new Date().toISOString();
    let page = 0;
    let hasMore = true;

    while (hasMore && page < CONFIG.MAX_PAGES) {
      const url = `${CONFIG.OPERATIONS_URL}?before=${encodeURIComponent(cursor)}&per=${CONFIG.ITEMS_PER_PAGE}`;

      const response = await fetch(url, {
        headers: buildHeaders(jwt),
      });

      if (!response.ok) {
        throw new Error(`Operations error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      if (data.items && data.items.length > 0) {
        allItems.push(...data.items);
      }

      hasMore = data.has_more === true;
      cursor = data.next_cursor;
      page++;

      onProgress(page, allItems.length);

      // 100ms pause between requests to avoid rate limiting
      if (hasMore) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }

    // Return in format expected by SwileBankAdapter
    return {
      items_count: allItems.length,
      has_more: false,
      next_cursor: null,
      items: allItems,
    };
  }

  /**
   * Triggers download of a JSON file
   * @param {object} data - The data to download
   * @param {string} filename - The filename
   */
  function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  /**
   * Displays a progress notification
   * @param {string} message - The message to display
   */
  function showNotification(message) {
    // Remove previous notification if exists
    const existing = document.getElementById('swile-export-notification');
    if (existing) {
      existing.remove();
    }

    const notification = document.createElement('div');
    notification.id = 'swile-export-notification';
    notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background: #1a1a2e;
            color: white;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 14px;
            z-index: 999999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;
    notification.textContent = message;
    document.body.appendChild(notification);
  }

  /**
   * Removes the notification
   */
  function hideNotification() {
    const notification = document.getElementById('swile-export-notification');
    if (notification) {
      notification.remove();
    }
  }

  // === Main execution ===

  try {
    // Page verification
    if (!window.location.hostname.includes('swile.co')) {
      alert('This script must be run from team.swile.co');
      return;
    }

    // JWT retrieval
    const jwt = getJWT();
    if (!jwt) {
      alert('Swile session not found.\n\nMake sure you are logged in to team.swile.co');
      return;
    }

    showNotification('Swile export in progress...');

    // Fetch wallets
    showNotification('Fetching wallets...');
    const wallets = await fetchWallets(jwt);

    // Fetch operations
    const operations = await fetchAllOperations(jwt, (page, total) => {
      showNotification(`Fetching operations... (page ${page}, ${total} operations)`);
    });

    // Download files
    showNotification(`Export complete! ${operations.items_count} operations`);

    downloadJSON(operations, 'operations.json');

    // Small delay to prevent download overlap
    await new Promise((resolve) => setTimeout(resolve, 500));

    downloadJSON(wallets, 'wallets.json');

    // Final notification
    setTimeout(() => {
      hideNotification();
      alert(
        `Swile export complete!\n\n${operations.items_count} operations exported.\n\nDownloaded files:\n- operations.json\n- wallets.json`,
      );
    }, 1000);
  } catch (error) {
    hideNotification();
    console.error('Swile export error:', error);
    alert(`Swile export error:\n\n${error.message}\n\nCheck the console for more details.`);
  }
})();
