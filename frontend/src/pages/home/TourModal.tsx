import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

export function TourModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    closeButtonRef.current?.focus()
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center bg-black/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-modal-title"
        className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="tour-modal-title" className="font-serif text-xl font-semibold text-brand-navy">
            Product tour
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close product tour"
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        <div className="flex aspect-video items-center justify-center rounded-xl bg-slate-900 text-slate-400">
          <p className="max-w-sm px-6 text-center text-sm">
            A walkthrough video isn&apos;t available in this sample deployment. Log in with the demo
            credentials on the login page to explore the real application instead.
          </p>
        </div>
      </div>
    </div>
  )
}
