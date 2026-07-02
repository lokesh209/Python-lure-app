/**
 * Shared TypeScript declaration for pywebview's JS bridge.
 * Methods exposed by ``backend/desktop.py``'s ``JsBridge`` class.
 */
declare global {
  interface Window {
    pywebview?: {
      api?: {
        reveal?: (path: string) => Promise<boolean>;
        pick_folder?: (start?: string) => Promise<string | null>;
      };
    };
  }
}

export {};
