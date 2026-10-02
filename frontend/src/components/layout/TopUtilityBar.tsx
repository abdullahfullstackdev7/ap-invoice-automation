import { Link } from 'react-router-dom'

export function TopUtilityBar() {
  return (
    <div className="hidden bg-brand-navy text-xs text-slate-300 md:block">
      <div className="mx-auto flex max-w-[1240px] items-center justify-end gap-6 px-4 py-2 sm:px-6 lg:px-8">
        <Link to="/resources" className="hover:text-white">
          Support
        </Link>
        <Link to="/contact" className="hover:text-white">
          Contact sales
        </Link>
        <span aria-hidden="true" className="text-slate-500">
          |
        </span>
        <span>English (US)</span>
      </div>
    </div>
  )
}
