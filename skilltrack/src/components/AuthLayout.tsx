import type { ReactNode } from 'react'

const TREND = 'M3 17l6-6 4 4 8-8M14 7h7v7'

const FEATURES: { title: string; text: string; icon: ReactNode }[] = [
  {
    title: 'Track your skills',
    text: 'See every skill you are building and how far along you are.',
    icon: <path strokeLinecap="round" strokeLinejoin="round" d={TREND} />,
  },
  {
    title: 'Stay on target',
    text: 'Set goals, follow progress and keep your momentum going.',
    icon: (
      <>
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="3.5" />
        <path strokeLinecap="round" d="M12 12l6-6" />
      </>
    ),
  },
  {
    title: 'Earn recognition',
    text: 'Turn completed work into achievements you can show off.',
    icon: <path strokeLinecap="round" strokeLinejoin="round" d="M7 4h10v5a5 5 0 01-10 0V4zM7 6H4v1a3 3 0 003 3M17 6h3v1a3 3 0 01-3 3M12 14v4m-3 2h6" />,
  },
]

export function Icon({ children, className = 'h-5 w-5' }: { children: ReactNode; className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className={className}>
      {children}
    </svg>
  )
}

export function Logo({ dark }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${dark ? 'bg-gray-900 text-white' : 'bg-white/15 text-white backdrop-blur'}`}>
        <Icon className="h-5 w-5"><path strokeLinecap="round" strokeLinejoin="round" d={TREND} /></Icon>
      </div>
      <span className={`text-xl font-bold tracking-tight ${dark ? 'text-gray-900' : 'text-white'}`}>SkillTrack</span>
    </div>
  )
}

const ANIMATIONS = `
.sk-float{animation:sk-float 3.2s ease-in-out infinite}
.sk-float-b{animation:sk-float 3.8s ease-in-out .9s infinite}
.sk-float-c{animation:sk-float 4.2s ease-in-out 1.7s infinite}
.sk-nod{transform-box:fill-box;transform-origin:50% 100%;animation:sk-nod 5s ease-in-out infinite}
.sk-blink{transform-box:fill-box;transform-origin:center;animation:sk-blink 4.5s infinite}
.sk-tap-a{animation:sk-tap .55s ease-in-out infinite}
.sk-tap-b{animation:sk-tap .55s ease-in-out .27s infinite}
.sk-sway{transform-box:fill-box;transform-origin:50% 100%;animation:sk-sway 4s ease-in-out infinite}
.sk-steam{animation:sk-steam 2.6s ease-in-out infinite}
.sk-steam-b{animation:sk-steam 2.6s ease-in-out 1.2s infinite}
.sk-twinkle{transform-box:fill-box;transform-origin:center;animation:sk-twinkle 2.2s ease-in-out infinite}
.sk-bar{transform-box:fill-box;transform-origin:left center;animation:sk-bar 4s ease-in-out infinite}
@keyframes sk-float{50%{transform:translateY(-9px)}}
@keyframes sk-nod{50%{transform:rotate(-1.6deg)}}
@keyframes sk-blink{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
@keyframes sk-tap{50%{transform:translateY(-3px)}}
@keyframes sk-sway{50%{transform:rotate(4deg)}}
@keyframes sk-steam{0%{opacity:0;transform:translateY(6px)}50%{opacity:.85}100%{opacity:0;transform:translateY(-12px)}}
@keyframes sk-twinkle{50%{transform:scale(.3);opacity:.4}}
@keyframes sk-bar{0%{transform:scaleX(.15)}60%,100%{transform:scaleX(1)}}
@media (prefers-reduced-motion:reduce){.sk-anim *{animation:none!important}}
`

/** Animated, gender-neutral student at a desk: hoodie, headphones, laptop, books, coffee and a plant. */
export function StudentIllustration() {
  return (
    <svg viewBox="0 0 420 460" className="sk-anim h-auto w-full" role="img" aria-label="Student studying at a desk">
      <style>{ANIMATIONS}</style>

      {/* background shapes */}
      <circle cx="215" cy="235" r="170" fill="#fff" opacity=".08" />
      <ellipse cx="318" cy="200" rx="80" ry="105" fill="#e2e0df" opacity=".25" />
      <circle cx="95" cy="300" r="62" fill="#d4d1cf" opacity=".3" />
      <ellipse cx="205" cy="448" rx="190" ry="10" fill="#1a1a1a" opacity=".12" />

      {/* floating badges */}
      <g className="sk-float">
        <circle cx="78" cy="168" r="24" fill="#fff" />
        <path d="M78 154l4.2 8.6 9.5 1.4-6.9 6.7 1.6 9.4-8.4-4.4-8.4 4.4 1.6-9.4-6.9-6.7 9.5-1.4z" fill="#d4a252" />
      </g>
      <g className="sk-float-b">
        <circle cx="352" cy="150" r="22" fill="#3a3a3a" />
        <path d="M341 151l8 8 14-15" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </g>
      <g className="sk-float-c">
        <rect x="334" y="222" width="58" height="30" rx="15" fill="#fff" />
        <text x="363" y="242" textAnchor="middle" fontSize="15" fontWeight="800" fill="#3a3a3a" fontFamily="monospace">{'</>'}</text>
      </g>
      <g className="sk-float-b">
        <path d="M58 92L120 64 102 120 90 98z" fill="#fff" opacity=".95" />
        <path d="M90 98L120 64" stroke="#c4c4c4" strokeWidth="2" />
      </g>
      <path className="sk-twinkle" d="M300 70l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" fill="#e5dcc8" />
      <path className="sk-twinkle" style={{ animationDelay: '1s' }} d="M40 230l3 7 7 3-7 3-3 7-3-7-7-3 7-3z" fill="#fff" />

      {/* plant */}
      <g>
        <g className="sk-sway">
          <path d="M392 405Q386 350 392 300" stroke="#4a6e5a" strokeWidth="4" fill="none" />
          <ellipse cx="372" cy="345" rx="12" ry="36" transform="rotate(-32 372 345)" fill="#5d8a6e" />
          <ellipse cx="412" cy="335" rx="12" ry="40" transform="rotate(28 412 335)" fill="#4a6e5a" />
          <ellipse cx="392" cy="312" rx="12" ry="38" fill="#6fa080" />
        </g>
        <path d="M372 404h40l-5 40h-30z" fill="#c9a86c" />
        <rect x="368" y="398" width="48" height="10" rx="4" fill="#d4b87a" />
      </g>

      {/* desk */}
      <rect x="62" y="342" width="12" height="102" rx="3" fill="#2a2a2a" />
      <rect x="326" y="342" width="12" height="102" rx="3" fill="#2a2a2a" />
      <rect x="40" y="328" width="320" height="16" rx="8" fill="#e8e6e3" />

      {/* chair back */}
      <rect x="146" y="196" width="128" height="150" rx="46" fill="#3a3632" />

      {/* torso (hoodie) */}
      <path d="M146 336Q142 236 160 220Q184 204 210 204Q236 204 260 220Q278 236 274 336Z" fill="#5c5c5c" />
      <path d="M180 210Q210 236 240 210Q226 202 210 202Q194 202 180 210Z" fill="#484848" />
      <path d="M200 226v34M220 226v34" stroke="#888" strokeWidth="3" strokeLinecap="round" opacity=".6" />
      <circle cx="200" cy="262" r="3" fill="#888" />
      <circle cx="220" cy="262" r="3" fill="#888" />

      {/* neck */}
      <rect x="197" y="168" width="26" height="40" rx="10" fill="#dca67f" />

      {/* head group */}
      <g className="sk-nod">
        <ellipse cx="210" cy="138" rx="41" ry="45" fill="#f1c19b" />
        <ellipse cx="170" cy="146" rx="7" ry="10" fill="#e8b08a" />
        <ellipse cx="250" cy="146" rx="7" ry="10" fill="#e8b08a" />
        {/* hair */}
        <path d="M168 138Q164 90 210 88Q256 90 252 138Q246 114 224 110Q206 118 186 112Q172 118 168 138Z" fill="#2f2433" />
        <path d="M186 112Q200 98 226 108" stroke="#463548" strokeWidth="3" fill="none" strokeLinecap="round" />
        {/* face */}
        <path d="M184 128q8-6 16-1M220 127q8-5 16 1" stroke="#2f2433" strokeWidth="3" strokeLinecap="round" fill="none" />
        <ellipse className="sk-blink" cx="192" cy="141" rx="3.6" ry="4.8" fill="#2a1b24" />
        <ellipse className="sk-blink" cx="228" cy="141" rx="3.6" ry="4.8" fill="#2a1b24" />
        <path d="M210 144q-4 10 2 12" stroke="#d29873" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        <path d="M197 160q13 12 26 0" stroke="#2a1b24" strokeWidth="3.2" strokeLinecap="round" fill="none" />
        <circle cx="180" cy="156" r="7" fill="#e8b8a8" opacity=".4" />
        <circle cx="240" cy="156" r="7" fill="#e8b8a8" opacity=".4" />
        {/* headphones */}
        <path d="M164 142Q160 76 210 76Q260 76 256 142" stroke="#555" strokeWidth="7" fill="none" strokeLinecap="round" />
        <rect x="156" y="128" width="17" height="38" rx="8.5" fill="#444" />
        <rect x="247" y="128" width="17" height="38" rx="8.5" fill="#444" />
        <rect x="160" y="134" width="6" height="26" rx="3" fill="#333" opacity=".35" />
        <rect x="254" y="134" width="6" height="26" rx="3" fill="#333" opacity=".35" />
      </g>

      {/* laptop (back of lid) */}
      <rect x="154" y="262" width="112" height="68" rx="7" fill="#d5d3d0" />
      <path d="M210 304l-9-9a5.5 5.5 0 0 1 9-6.5 5.5 5.5 0 0 1 9 6.5z" fill="#fff" />
      <rect x="144" y="328" width="132" height="8" rx="4" fill="#b0ada8" />

      {/* arms + typing hands */}
      <path d="M160 232Q126 292 174 322" stroke="#505050" strokeWidth="26" strokeLinecap="round" fill="none" />
      <path d="M260 232Q294 292 246 322" stroke="#505050" strokeWidth="26" strokeLinecap="round" fill="none" />
      <circle className="sk-tap-a" cx="178" cy="325" r="10" fill="#f1c19b" />
      <circle className="sk-tap-b" cx="242" cy="325" r="10" fill="#f1c19b" />

      {/* mug with steam */}
      <rect x="296" y="302" width="28" height="26" rx="5" fill="#fff" />
      <path d="M324 309h6a5 5 0 0 1 0 12h-6" stroke="#fff" strokeWidth="4" fill="none" />
      <rect x="296" y="302" width="28" height="7" rx="3" fill="#c9a86c" />
      <path className="sk-steam" d="M306 296q-5-8 0-14" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" fill="none" />
      <path className="sk-steam-b" d="M314 296q-5-8 0-14" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" fill="none" />

      {/* books on desk */}
      <g fontSize="11" fontWeight="700" fill="#fff" fontFamily="sans-serif">
        <rect x="52" y="310" width="82" height="18" rx="4" fill="#c9a86c" />
        <text x="62" y="323">Grow</text>
        <rect x="56" y="292" width="76" height="18" rx="4" fill="#8a8a8a" />
        <text x="66" y="305">Practice</text>
        <rect x="60" y="274" width="70" height="18" rx="4" fill="#5a5a5a" />
        <text x="70" y="287">Learn</text>
      </g>

      {/* progress bar floating above books */}
      <rect x="52" y="240" width="82" height="9" rx="4.5" fill="#fff" opacity=".25" />
      <rect className="sk-bar" x="52" y="240" width="82" height="9" rx="4.5" fill="#6fa080" />
    </svg>
  )
}

/** Shared split-screen shell for the Login and Register pages. `children` is the form card. */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen overflow-hidden bg-gray-50 dark:bg-slate-950">
      {/* Brand panel */}
      <aside
        className="relative hidden flex-col justify-between overflow-hidden bg-slate-950 p-12 text-white lg:flex lg:w-[52%]"
      >
        <div className="pointer-events-none absolute -left-20 -top-20 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-96 w-96 rounded-full bg-purple-600/20 blur-3xl" />
        <div className="pointer-events-none absolute top-1/2 left-1/4 h-80 w-80 -translate-y-1/2 rounded-full bg-emerald-500/10 blur-3xl" />
        <Logo />

        {/* text stays in its own column so it never runs under the illustration */}
        <div className="relative z-10 max-w-sm space-y-8 pb-6 2xl:max-w-md">
          <div>
            <h2 className="text-4xl font-bold leading-tight 2xl:text-5xl">
              Grow your skills,
              <br />
              one step at a time.
            </h2>
            <p className="mt-5 text-lg text-gray-400">Everything you need to learn, practice and measure your progress in one place.</p>
          </div>

          <ul className="space-y-5">
            {FEATURES.map((f) => (
              <li key={f.title} className="group flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/10 text-white transition group-hover:bg-white/15">
                  <Icon className="h-5 w-5">{f.icon}</Icon>
                </div>
                <div>
                  <p className="font-semibold">{f.title}</p>
                  <p className="text-sm text-gray-400">{f.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 text-xs text-gray-500">© {new Date().getFullYear()} SkillTrack</p>

        {/* illustration sits in the free right-hand column (offset clears the slanted edge) */}
        <div className="pointer-events-none absolute bottom-4 right-[6%] hidden w-[34%] xl:block 2xl:w-[38%]">
          <StudentIllustration />
        </div>
      </aside>

      {/* Form panel */}
      <main className="relative flex flex-1 items-center justify-center p-6">{children}</main>
    </div>
  )
}
