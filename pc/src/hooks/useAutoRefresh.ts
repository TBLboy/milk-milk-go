import { useEffect, useRef } from 'react'
import { DATA_SYNC_EVENT } from '../services/dataSync'

export function useAutoRefresh(onRefresh: () => void | Promise<void>) {
  const refreshRef = useRef(onRefresh)

  useEffect(() => {
    refreshRef.current = onRefresh
  }, [onRefresh])

  useEffect(() => {
    let active = true
    let inFlight = false

    const refresh = async () => {
      if (!active || inFlight || document.visibilityState === 'hidden') return
      inFlight = true
      try {
        await refreshRef.current()
      } catch {
        // Keep showing the last successful data set during transient failures.
      } finally {
        inFlight = false
      }
    }

    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }

    window.addEventListener(DATA_SYNC_EVENT, refresh)
    window.addEventListener('focus', refreshWhenVisible)
    document.addEventListener('visibilitychange', refreshWhenVisible)

    return () => {
      active = false
      window.removeEventListener(DATA_SYNC_EVENT, refresh)
      window.removeEventListener('focus', refreshWhenVisible)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [])
}
