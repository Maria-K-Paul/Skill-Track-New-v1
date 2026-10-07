import type { ReactNode } from 'react'

/** Sleek glassmorphic stat tile for modern dark hero sections. */
export default function StatTile({ label, value, icon }: { label: string; value: ReactNode; icon: ReactNode }) {
  return (
    <div className="group flex items-center gap-4 rounded-2xl border border-white/10 bg-white/5 px-5 py-4 backdrop-blur-md transition-all hover:-translate-y-1 hover:bg-white/10 hover:shadow-xl hover:shadow-black/20">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-indigo-300 ring-1 ring-inset ring-indigo-500/30 transition-all group-hover:scale-110 group-hover:from-indigo-500/30 group-hover:to-purple-500/30">
        {icon}
      </span>
      <div>
        <div className="text-2xl font-bold tracking-tight text-white">{value}</div>
        <div className="mt-0.5 text-xs font-medium uppercase tracking-wider text-slate-400">{label}</div>
      </div>
    </div>
  )
}
