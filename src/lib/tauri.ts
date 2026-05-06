/**
 * Tauri Integration Layer for GenericAgent
 *
 * Provides a unified API that works both in Tauri desktop mode
 * and browser dev mode. When running in Tauri, it uses native APIs
 * for window management, file dialogs, and backend sidecar control.
 * In browser mode, it falls back to web APIs.
 */

// Dynamic import — the Tauri runtime is only available inside the
// desktop app. In a plain browser session the module does not exist,
// so we resolve it lazily and cache the result.

let _isTauriCache: boolean | null = null;
let _isTauriChecked = false;

/**
 * Check whether the Tauri runtime is present.
 * Uses the `__TAURI_INTERNALS__` global that Tauri injects.
 */
function checkIsTauriRuntime(): boolean {
  if (typeof window === 'undefined') return false;
  // The canonical way to detect Tauri at runtime without importing the package
  return !!(window as any).__TAURI_INTERNALS__;
}

// Lazy-loaded Tauri APIs
let invoke: any = null;
let tauriEvent: any = null;
let appWindow: any = null;

async function loadTauriApis() {
  if (typeof window !== 'undefined' && checkIsTauriRuntime()) {
    try {
      // Use variable-based dynamic imports so the bundler does NOT try to
      // resolve them at build time (Tauri APIs are only available at runtime
      // inside the desktop app shell).
      const coreMod = '@tauri-apps/api/core';
      const eventMod = '@tauri-apps/api/event';
      const winMod = '@tauri-apps/api/webviewWindow';

      const core = await import(/* webpackIgnore: true */ /* @vite-ignore */ coreMod);
      invoke = core.invoke;
      tauriEvent = await import(/* webpackIgnore: true */ /* @vite-ignore */ eventMod);
      const webviewWindow = await import(/* webpackIgnore: true */ /* @vite-ignore */ winMod);
      appWindow = webviewWindow.getCurrentWebviewWindow();
    } catch (e) {
      console.warn('Failed to load Tauri APIs:', e);
    }
  }
}

// Initialize on first use
let apisLoaded = false;
async function ensureApis() {
  if (!apisLoaded) {
    await loadTauriApis();
    apisLoaded = true;
  }
}

// ═══════════════════════════════════════════════════════════════
//  Environment Detection
// ═══════════════════════════════════════════════════════════════

/** Check if running inside Tauri desktop app */
export function isTauri(): boolean {
  if (_isTauriChecked) return _isTauriCache!;
  _isTauriCache = checkIsTauriRuntime();
  _isTauriChecked = true;
  return _isTauriCache;
}

// ═══════════════════════════════════════════════════════════════
//  Backend Sidecar Management
// ═══════════════════════════════════════════════════════════════

export interface BackendStatus {
  running: boolean;
  pid: number | null;
  port: number;
}

/** Start the Python backend sidecar (Tauri only) */
export async function startBackend(): Promise<boolean> {
  await ensureApis();
  if (!isTauri()) {
    console.warn('startBackend: Not in Tauri mode');
    return false;
  }
  try {
    return await invoke('start_backend');
  } catch (e) {
    console.error('Failed to start backend:', e);
    return false;
  }
}

/** Stop the Python backend sidecar (Tauri only) */
export async function stopBackend(): Promise<boolean> {
  await ensureApis();
  if (!isTauri()) return false;
  try {
    return await invoke('stop_backend');
  } catch (e) {
    console.error('Failed to stop backend:', e);
    return false;
  }
}

/** Get backend sidecar status (Tauri only) */
export async function getBackendStatus(): Promise<BackendStatus | null> {
  await ensureApis();
  if (!isTauri()) return null;
  try {
    return await invoke('get_backend_status');
  } catch (e) {
    console.error('Failed to get backend status:', e);
    return null;
  }
}

/** Check backend health via HTTP (works in both modes) */
export async function checkBackendHealthTauri(): Promise<boolean> {
  await ensureApis();
  if (!isTauri()) return false;
  try {
    return await invoke('check_backend_health');
  } catch (e) {
    return false;
  }
}

// ═══════════════════════════════════════════════════════════════
//  Window Management (Tauri only)
// ═══════════════════════════════════════════════════════════════

/** Minimize the window */
export async function minimizeWindow(): Promise<void> {
  await ensureApis();
  if (!isTauri()) {
    // Fallback: no-op in browser
    return;
  }
  try {
    await invoke('minimize_window');
  } catch (e) {
    console.error('Failed to minimize window:', e);
  }
}

/** Toggle maximize/restore */
export async function toggleMaximize(): Promise<void> {
  await ensureApis();
  if (!isTauri()) return;
  try {
    await invoke('toggle_maximize_window');
  } catch (e) {
    console.error('Failed to toggle maximize:', e);
  }
}

/** Close the window */
export async function closeWindow(): Promise<void> {
  await ensureApis();
  if (!isTauri()) {
    // Fallback: close browser tab
    window.close();
    return;
  }
  try {
    await invoke('close_window');
  } catch (e) {
    console.error('Failed to close window:', e);
  }
}

// ═══════════════════════════════════════════════════════════════
//  File Dialog (Tauri native / browser fallback)
// ═══════════════════════════════════════════════════════════════

export interface FileFilter {
  name: string;
  extensions: string[];
}

export interface FileDialogResult {
  paths: string[] | null;
}

/** Open a native file dialog */
export async function openFileDialog(
  title?: string,
  filters?: FileFilter[],
  multiple?: boolean
): Promise<FileDialogResult> {
  await ensureApis();
  if (!isTauri()) {
    // Browser fallback using input element
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      if (multiple) input.multiple = true;
      // Note: browser file dialogs don't support filters the same way
      input.onchange = () => {
        const files = input.files;
        if (files && files.length > 0) {
          resolve({
            paths: Array.from(files).map((f) => f.name),
          });
        } else {
          resolve({ paths: null });
        }
      };
      input.click();
    });
  }
  try {
    return await invoke('open_file_dialog', {
      title: title || 'Select File',
      filters: filters || [],
      multiple: multiple || false,
    });
  } catch (e) {
    console.error('Failed to open file dialog:', e);
    return { paths: null };
  }
}

// ═══════════════════════════════════════════════════════════════
//  App Version
// ═══════════════════════════════════════════════════════════════

export interface AppVersion {
  version: string;
  name: string;
}

/** Get the application version */
export async function getAppVersion(): Promise<AppVersion> {
  await ensureApis();
  if (!isTauri()) {
    return { version: '1.0.0-web', name: 'GenericAgent' };
  }
  try {
    return await invoke('get_app_version');
  } catch (e) {
    return { version: '0.0.0', name: 'GenericAgent' };
  }
}

// ═══════════════════════════════════════════════════════════════
//  Event Listeners
// ═══════════════════════════════════════════════════════════════

/** Listen for Tauri events (e.g., backend-crashed) */
export async function listenToEvent<T = any>(
  event: string,
  handler: (payload: T) => void
): Promise<(() => void) | null> {
  await ensureApis();
  if (!isTauri() || !tauriEvent) return null;
  try {
    const unlisten = await (tauriEvent as any).listen(event, (e: any) => {
      handler(e.payload);
    });
    return unlisten;
  } catch (e) {
    console.error('Failed to listen to event:', e);
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
//  App Lifecycle Initialization
// ═══════════════════════════════════════════════════════════════

/**
 * Initialize the Tauri app lifecycle:
 * 1. If in Tauri mode, start the backend sidecar
 * 2. Wait for backend health check to pass
 * 3. Listen for backend crash events
 *
 * Returns true if backend started successfully, false otherwise.
 */
export async function initializeTauriApp(): Promise<{
  isDesktop: boolean;
  backendStarted: boolean;
}> {
  const desktop = isTauri();

  if (!desktop) {
    console.log('[Tauri] Running in browser mode');
    return { isDesktop: false, backendStarted: false };
  }

  console.log('[Tauri] Running in desktop mode, initializing...');

  // Start the backend sidecar
  let backendStarted = false;
  try {
    backendStarted = await startBackend();
    console.log('[Tauri] Backend sidecar start result:', backendStarted);
  } catch (e) {
    console.error('[Tauri] Failed to start backend:', e);
  }

  // Wait for backend health check (up to 30 seconds)
  if (backendStarted) {
    const maxAttempts = 15;
    for (let i = 0; i < maxAttempts; i++) {
      const healthy = await checkBackendHealthTauri();
      if (healthy) {
        console.log('[Tauri] Backend is healthy after', (i + 1) * 2, 'seconds');
        break;
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
  }

  // Listen for backend crash events
  listenToEvent('backend-crashed', () => {
    console.error('[Tauri] Backend crashed!');
    // The frontend should show a reconnection dialog
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('backend-crashed'));
    }
  });

  // Listen for tray events
  listenToEvent('tray-start-backend', async () => {
    console.log('[Tauri] Tray: Start backend requested');
    await startBackend();
  });

  listenToEvent('tray-stop-backend', async () => {
    console.log('[Tauri] Tray: Stop backend requested');
    await stopBackend();
  });

  return { isDesktop: true, backendStarted };
}
