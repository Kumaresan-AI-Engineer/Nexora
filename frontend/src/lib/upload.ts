export const DEFAULT_ALLOWED_MIME = ['image/jpeg', 'image/png', 'image/webp']
export const DEFAULT_MAX_MB = 8

/** Client-side pre-check for fast feedback. The server re-validates content (magic bytes) regardless. */
export function validateImageFile(
  file: File,
  allowed: string[] = DEFAULT_ALLOWED_MIME,
  maxMb: number = DEFAULT_MAX_MB,
): string | null {
  if (!allowed.includes(file.type)) return 'Unsupported file type. Use a JPEG, PNG or WebP image.'
  if (file.size === 0) return 'The selected file is empty.'
  if (file.size > maxMb * 1024 * 1024) return `The image is larger than ${maxMb} MB.`
  return null
}
