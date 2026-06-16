import '@testing-library/jest-dom';

// Node 22+ stellt ein eigenes, unvollständiges globales `localStorage` bereit
// (erfordert --localstorage-file) und überschattet damit window.localStorage
// in jsdom. Ersetzt es durch eine vollwertige In-Memory-Storage-Implementierung.
if (typeof globalThis.localStorage?.getItem !== 'function') {
  class MemoryStorage implements Storage {
    private store = new Map<string, string>();

    get length(): number {
      return this.store.size;
    }

    clear(): void {
      this.store.clear();
    }

    getItem(key: string): string | null {
      return this.store.has(key) ? this.store.get(key)! : null;
    }

    key(index: number): string | null {
      return Array.from(this.store.keys())[index] ?? null;
    }

    removeItem(key: string): void {
      this.store.delete(key);
    }

    setItem(key: string, value: string): void {
      this.store.set(key, String(value));
    }
  }

  const memoryStorage = new MemoryStorage();
  for (const target of [globalThis, window]) {
    Object.defineProperty(target, 'localStorage', {
      value: memoryStorage,
      configurable: true,
      writable: true,
    });
  }
}

