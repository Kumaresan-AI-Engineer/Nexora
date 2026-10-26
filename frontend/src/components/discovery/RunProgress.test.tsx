import { render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RunProgress } from './RunProgress'

const file = new File([new Uint8Array(10)], 'pack.png', { type: 'image/png' })

describe('RunProgress', () => {
  const revoked = new Set<string>()
  let n = 0

  beforeEach(() => {
    revoked.clear()
    n = 0
    URL.createObjectURL = vi.fn(() => `blob:test-${++n}`)
    URL.revokeObjectURL = vi.fn((u: string) => void revoked.add(u))
  })
  afterEach(() => vi.restoreAllMocks())

  it('never shows an image whose URL has been revoked (React StrictMode regression)', () => {
    render(
      <StrictMode>
        <RunProgress file={file} stage="reading" providerName="OpenAI" identified={null} />
      </StrictMode>,
    )
    const src = screen.getByAltText('Image being analysed').getAttribute('src')
    expect(src).toBeTruthy()
    expect(revoked.has(src as string)).toBe(false)
  })

  it('shows what is really happening at each stage', () => {
    const { rerender } = render(<RunProgress file={file} stage="reading" providerName="OpenAI" identified={null} />)
    expect(screen.getByText('Reading the pack with OpenAI…')).toBeInTheDocument()
    expect(screen.getByText('Identify the product')).toBeInTheDocument()

    rerender(
      <RunProgress
        file={file}
        stage="searching"
        providerName="OpenAI"
        identified={{ name: 'Paracetamol', chips: ['500 mg', 'Tablet'], seconds: 3.14 }}
      />,
    )
    expect(screen.getByText('Read the pack with OpenAI')).toBeInTheDocument()
    expect(screen.getByText('Done in 3.1 s')).toBeInTheDocument()
    expect(screen.getByText('Identified: Paracetamol')).toBeInTheDocument()
    expect(screen.getByText('500 mg')).toBeInTheDocument()
    expect(screen.getByText('Starting the supplier search')).toBeInTheDocument()
  })

  it('revokes the object URL when it unmounts', () => {
    const { unmount } = render(<RunProgress file={file} stage="reading" providerName="OpenAI" identified={null} />)
    unmount()
    expect(revoked.size).toBeGreaterThan(0)
  })
})
