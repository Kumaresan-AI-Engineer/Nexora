import { useEffect, useState } from 'react'

/**
 * Object URL for a File, created and revoked inside the effect so React StrictMode's simulated
 * unmount/remount can never leave the component holding a revoked URL (a broken image in dev).
 */
export function useObjectUrl(file: File | null): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!file) {
      // oxlint-disable-next-line react/set-state-in-effect -- synchronising with an external resource (blob URL)
      setUrl(null)
      return
    }
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [file])
  return url
}
