/**
 * Swile Export Bookmarklet
 *
 * This script exports Swile operations and wallets to a single zip archive.
 * It must be executed from https://team.swile.co/ while logged in.
 *
 * Usage:
 * 1. Log in to https://team.swile.co/
 * 2. Run this script via the bookmarklet or browser console
 * 3. A swile-export-YYYY-MM-DD.zip file will be downloaded automatically
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
   * Computes CRC-32 for a Uint8Array
   * @param {Uint8Array} data - Input bytes
   * @returns {number} The CRC-32 value (unsigned 32-bit integer)
   */
  function crc32(data) {
    // Build lookup table on first call
    if (!crc32.table) {
      crc32.table = new Uint32Array(256);
      for (let i = 0; i < 256; i++) {
        let c = i;
        for (let j = 0; j < 8; j++) {
          c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        }
        crc32.table[i] = c;
      }
    }
    let crc = 0xffffffff;
    for (let i = 0; i < data.length; i++) {
      crc = crc32.table[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  /**
   * Builds a ZIP archive (STORE method, no compression) from named entries.
   * Implements the minimal subset of the ZIP specification (PKZIP APPNOTE 6.3.3):
   * - Local file headers + uncompressed data for each entry
   * - Central directory headers
   * - End of central directory record
   *
   * @param {Array<{name: string, data: Uint8Array}>} entries - Files to include
   * @returns {Blob} The ZIP archive as a Blob
   */
  function buildZip(entries) {
    const localParts = [];
    const centralParts = [];
    let offset = 0;

    for (const entry of entries) {
      const nameBytes = new TextEncoder().encode(entry.name);
      const crc = crc32(entry.data);

      // Local file header (30 bytes + filename)
      const local = new ArrayBuffer(30 + nameBytes.length);
      const lv = new DataView(local);
      lv.setUint32(0, 0x04034b50, true); // Local file header signature
      lv.setUint16(4, 20, true); // Version needed to extract (2.0)
      lv.setUint16(6, 0, true); // General purpose bit flag
      lv.setUint16(8, 0, true); // Compression method: STORE
      lv.setUint16(10, 0, true); // Last mod file time
      lv.setUint16(12, 0, true); // Last mod file date
      lv.setUint32(14, crc, true); // CRC-32
      lv.setUint32(18, entry.data.length, true); // Compressed size
      lv.setUint32(22, entry.data.length, true); // Uncompressed size
      lv.setUint16(26, nameBytes.length, true); // File name length
      lv.setUint16(28, 0, true); // Extra field length
      new Uint8Array(local).set(nameBytes, 30);

      localParts.push(new Uint8Array(local), entry.data);
      const localSize = local.byteLength + entry.data.length;

      // Central directory header (46 bytes + filename)
      const central = new ArrayBuffer(46 + nameBytes.length);
      const cv = new DataView(central);
      cv.setUint32(0, 0x02014b50, true); // Central directory header signature
      cv.setUint16(4, 20, true); // Version made by
      cv.setUint16(6, 20, true); // Version needed to extract
      cv.setUint16(8, 0, true); // General purpose bit flag
      cv.setUint16(10, 0, true); // Compression method: STORE
      cv.setUint16(12, 0, true); // Last mod file time
      cv.setUint16(14, 0, true); // Last mod file date
      cv.setUint32(16, crc, true); // CRC-32
      cv.setUint32(20, entry.data.length, true); // Compressed size
      cv.setUint32(24, entry.data.length, true); // Uncompressed size
      cv.setUint16(28, nameBytes.length, true); // File name length
      cv.setUint16(30, 0, true); // Extra field length
      cv.setUint16(32, 0, true); // File comment length
      cv.setUint16(34, 0, true); // Disk number start
      cv.setUint16(36, 0, true); // Internal file attributes
      cv.setUint32(38, 0, true); // External file attributes
      cv.setUint32(42, offset, true); // Relative offset of local header
      new Uint8Array(central).set(nameBytes, 46);

      centralParts.push(new Uint8Array(central));
      offset += localSize;
    }

    const centralOffset = offset;
    let centralSize = 0;
    for (const part of centralParts) {
      centralSize += part.length;
    }

    // End of central directory record (22 bytes)
    const eocd = new ArrayBuffer(22);
    const ev = new DataView(eocd);
    ev.setUint32(0, 0x06054b50, true); // End of central dir signature
    ev.setUint16(4, 0, true); // Number of this disk
    ev.setUint16(6, 0, true); // Disk where central directory starts
    ev.setUint16(8, entries.length, true); // Number of central directory records on this disk
    ev.setUint16(10, entries.length, true); // Total number of central directory records
    ev.setUint32(12, centralSize, true); // Size of central directory
    ev.setUint32(16, centralOffset, true); // Offset of start of central directory
    ev.setUint16(20, 0, true); // Comment length

    return new Blob([...localParts, ...centralParts, new Uint8Array(eocd)], {
      type: 'application/zip',
    });
  }

  /**
   * Triggers download of a Blob
   * @param {Blob} blob - The blob to download
   * @param {string} filename - The filename
   */
  function downloadBlob(blob, filename) {
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

    // Build and download zip archive
    showNotification(`Bundling ${operations.items_count} operations into zip...`);

    const encoder = new TextEncoder();
    const zip = buildZip([
      { name: 'operations.json', data: encoder.encode(JSON.stringify(operations, null, 2)) },
      { name: 'wallets.json', data: encoder.encode(JSON.stringify(wallets, null, 2)) },
    ]);

    const today = new Date().toISOString().slice(0, 10);
    downloadBlob(zip, `swile-export-${today}.zip`);

    // Final notification
    setTimeout(() => {
      hideNotification();
      alert(
        `Swile export complete!\n\n${operations.items_count} operations exported.\n\nDownloaded: swile-export-${today}.zip`,
      );
    }, 1000);
  } catch (error) {
    hideNotification();
    console.error('Swile export error:', error);
    alert(`Swile export error:\n\n${error.message}\n\nCheck the console for more details.`);
  }
})();
