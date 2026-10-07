import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  icon?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}

export default function Card({ title, icon, action, children, className = '' }: CardProps) {
  return (
    <section className={`rounded-3xl border border-slate-200/60 bg-white p-6 shadow-xl shadow-slate-200/40 transition-all hover:shadow-2xl hover:shadow-slate-200/50 dark:border-slate-700/60 dark:bg-slate-900 dark:shadow-slate-950/40 dark:hover:shadow-slate-950/60 ${className}`}>
      {title && (
        <div className="mb-5 flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-3 text-lg font-bold tracking-tight text-slate-800 dark:text-white">
            {icon && (
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100/50 dark:bg-indigo-900/40 dark:text-indigo-400 dark:ring-indigo-800/50">
                {icon}
              </span>
            )}
            {title}
          </h2>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
