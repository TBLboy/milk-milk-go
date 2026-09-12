export const DATA_SYNC_EVENT = 'milk:data-sync'

export function emitDataSync() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(DATA_SYNC_EVENT))
  }
}
