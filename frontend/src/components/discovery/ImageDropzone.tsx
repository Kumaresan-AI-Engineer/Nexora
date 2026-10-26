import { ImagePlus, RefreshCw, X } from 'lucide-react'
import { useId, useRef, useState, type DragEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { useObjectUrl } from '@/hooks/useObjectUrl'
import { cn } from '@/lib/cn'
import { validateImageFile } from '@/lib/upload'

interface Props {
  file: File | null
  onFile: (file: File | null) => void
  allowedMime?: string[]
  maxMb?: number
  disabled?: boolean
}

export function ImageDropzone({ file, onFile, allowedMime, maxMb, disabled }: Props) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const previewUrl = useObjectUrl(file)

  function accept(candidate: File | undefined) {
    if (!candidate) return
    const problem = validateImageFile(candidate, allowedMime, maxMb)
    setError(problem)
    if (!problem) onFile(candidate)
    if (inputRef.current) inputRef.current.value = ''
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (!disabled) accept(e.dataTransfer.files[0])
  }

  const remove = () => {
    setError(null)
    onFile(null)
  }

  return (
    <div>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={(allowedMime ?? ['image/jpeg', 'image/png', 'image/webp']).join(',')}
        className="sr-only"
        disabled={disabled}
        onChange={(e) => accept(e.target.files?.[0])}
        aria-describedby={`${inputId}-help`}
      />
      {file && previewUrl ? (
        <div className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 sm:flex-row sm:items-center">
          <img
            src={previewUrl}
            alt="Selected product"
            className="h-40 w-full rounded-md border border-line bg-sunken object-contain sm:w-56"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium" title={file.name}>
              {file.name}
            </p>
            <p className="text-xs text-muted">{(file.size / 1024).toFixed(0)} KB</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" disabled={disabled} onClick={() => inputRef.current?.click()}>
                <RefreshCw className="size-4" aria-hidden /> Replace image
              </Button>
              <Button variant="ghost" size="sm" disabled={disabled} onClick={remove}>
                <X className="size-4" aria-hidden /> Remove
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <label
          htmlFor={inputId}
          onDragOver={(e) => {
            e.preventDefault()
            if (!disabled) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-600',
            dragging ? 'border-brand-600 bg-brand-50' : 'border-line-strong bg-surface hover:bg-sunken',
            disabled && 'pointer-events-none opacity-60',
          )}
        >
          <ImagePlus className="size-8 text-brand-700" aria-hidden />
          <span className="text-sm font-medium">Drop a product photo here, or browse</span>
          <span id={`${inputId}-help`} className="text-xs text-muted">
            JPEG, PNG or WebP, up to {maxMb ?? 8} MB. Show the front of the pack clearly.
          </span>
        </label>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger-fg">
          {error}
        </p>
      )}
    </div>
  )
}
