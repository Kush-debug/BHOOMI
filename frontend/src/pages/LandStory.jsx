import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Clock,
  Compass,
  Cpu,
  Database,
  Eye,
  FileText,
  Gauge,
  GitCompare,
  Globe,
  Layers,
  Link2,
  Lock,
  Map,
  MapPin,
  Ruler,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Users
} from 'lucide-react';

/**
 * LandStory - the public, unauthenticated narrative page for Bhoomi AI.
 *
 * WHY THIS PAGE EXISTS
 * BHUMI_FORENSICS_SPEC.md's Phase 8 gate is "a judge understands the product in
 * 60 seconds". The portal itself proves that to someone who already has an
 * officer account. This page proves it to everyone else: it walks a visitor
 * through why Indian land records are contested, what the government has
 * already built, what remains unsolved, and where this system fits.
 *
 * FACTUAL DISCIPLINE
 * Every figure on this page is a published government or research statistic
 * with a citation rendered next to it and a source list at the bottom - the
 * same evidence rule the product itself enforces on extracted land records
 * (PRD "Evidence > hallucination"). No number here is invented, rounded for
 * effect, or presented without its date. Nothing on this page is a live
 * reading from this deployment's own database: every backend endpoint is
 * authenticated, and this page is deliberately public, so it never calls one.
 * If live system counters are wanted here later, they need a real public
 * aggregate endpoint - not a client-side guess.
 *
 * IMPLEMENTATION NOTES
 * - No new npm dependencies. Scroll behaviour is IntersectionObserver plus CSS
 *   transitions, not an animation library, so this page adds nothing to
 *   package.json and nothing to the bundle beyond its own source.
 * - Motion is gated on prefers-reduced-motion. With that setting on, every
 *   element renders in its final state immediately and nothing animates.
 * - The colour palette is the "Modern Civic Trust" direction from the redesign
 *   canvas, written as arbitrary Tailwind values so it needs no
 *   tailwind.config.js change (that file belongs to the local session).
 */

/* ---------------------------------------------------------------- palette */

const DEEP = '#06232a'; // deepest teal - hero and closing
const TEAL_900 = '#0b3038'; // dark chapter background
const TEAL_800 = '#114452'; // raised surface on dark
const TEAL_600 = '#1a6b7d'; // dark-mode accents, rules
const GOLD = '#d4a545'; // sparing accent - emblem, chapter numerals

/* ------------------------------------------------------------------ hooks */

/** True once the user has asked the OS to reduce motion. Read once per mount. */
const usePrefersReducedMotion = () => {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = (e) => setReduced(e.matches);
    // Safari < 14 only has addListener; both are guarded so neither path throws.
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else if (mq.removeListener) mq.removeListener(onChange);
    };
  }, []);
  return reduced;
};

/**
 * One-shot "is this on screen yet" observer. Unobserves after the first hit so
 * content does not re-animate when the reader scrolls back up.
 */
const useInView = (options) => {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (typeof IntersectionObserver === 'undefined') {
      // No observer (very old browser, or a test environment): show everything.
      setInView(true);
      return undefined;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setInView(true);
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px', ...(options || {}) }
    );
    io.observe(el);
    return () => io.disconnect();
    // options is a literal at every call site; re-running on identity change
    // would tear the observer down every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return [ref, inView];
};

/** Fraction of the document scrolled, 0..1, for the top progress rule. */
const useScrollProgress = () => {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    let frame = null;
    const measure = () => {
      frame = null;
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0);
    };
    const onScroll = () => {
      if (frame === null) frame = window.requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      if (frame !== null) window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, []);
  return progress;
};

/** Which chapter section currently owns the middle of the viewport. */
const useActiveSection = (ids) => {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined;
    const io = new IntersectionObserver(
      (entries) => {
        // The entry closest to the top of the viewport that is still visible.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) setActive(visible[0].target.id);
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: 0 }
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
  }, [ids]);
  return active;
};

/* -------------------------------------------------------------- primitives */

/** Fade-and-rise wrapper. Renders final-state immediately under reduced motion. */
const Reveal = ({ children, delay = 0, className = '' }) => {
  const reduced = usePrefersReducedMotion();
  const [ref, inView] = useInView();
  const shown = reduced || inView;
  return (
    <div
      ref={ref}
      className={`transition-all duration-700 ease-out ${className}`}
      style={{
        opacity: shown ? 1 : 0,
        transform: shown ? 'none' : 'translateY(22px)',
        transitionDelay: reduced ? '0ms' : `${delay}ms`
      }}
    >
      {children}
    </div>
  );
};

/**
 * Counts a real published figure up from zero when it scrolls into view.
 * The final value is always the exact `value` prop - the animation only
 * affects what is drawn on the way there, never the number itself.
 */
const CountUp = ({ value, decimals = 0, suffix = '', prefix = '', duration = 1400 }) => {
  const reduced = usePrefersReducedMotion();
  const [ref, inView] = useInView({ threshold: 0.4 });
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!inView || reduced) return undefined;
    let frame = null;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic - fast first, settles on the real number
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(value * eased);
      if (t < 1) frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => {
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [inView, reduced, value, duration]);

  const display = reduced || !inView ? value : shown;
  return (
    <span ref={ref}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
};

/** A small bracketed citation marker that jumps to the source list. */
const Cite = ({ n }) => (
  <a
    href="#sources"
    className="align-super text-[10px] font-bold text-emerald-600 hover:text-emerald-500 no-underline ml-0.5"
    aria-label={`Source ${n}`}
  >
    [{n}]
  </a>
);

/** A headline figure with its label and citation. `dark` flips it for dark chapters. */
const Figure = ({
  value,
  label,
  decimals = 0,
  suffix = '',
  prefix = '',
  // '' / 0 mean "not supplied" - both render as absent below, and unlike a null
  // default they let the checker infer the real string/number types.
  note = '',
  cite = 0,
  dark = false
}) => (
  <div>
    <div
      className={`text-4xl sm:text-5xl font-extrabold tracking-tight tabular-nums ${
        dark ? 'text-white' : 'text-slate-900'
      }`}
    >
      <CountUp value={value} decimals={decimals} suffix={suffix} prefix={prefix} />
    </div>
    <div className={`mt-2 text-sm font-semibold ${dark ? 'text-emerald-300' : 'text-emerald-800'}`}>
      {label}
      {cite ? <Cite n={cite} /> : null}
    </div>
    {note ? (
      <div className={`mt-1 text-xs leading-relaxed ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
        {note}
      </div>
    ) : null}
  </div>
);

/** Chapter heading: numeral, kicker, title, standfirst. */
const ChapterHead = ({ numeral, kicker, title, standfirst, dark = false }) => (
  <Reveal>
    <div className="max-w-3xl">
      <div className="flex items-center gap-3">
        <span
          className="text-xs font-extrabold tracking-[0.2em]"
          style={{ color: dark ? GOLD : '#a16207' }}
        >
          {numeral}
        </span>
        <span className="h-px flex-1 max-w-[80px]" style={{ background: dark ? TEAL_600 : '#e2e8f0' }} />
        <span
          className={`text-[11px] font-bold uppercase tracking-[0.14em] ${
            dark ? 'text-slate-400' : 'text-slate-500'
          }`}
        >
          {kicker}
        </span>
      </div>
      <h2
        className={`mt-5 text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold tracking-tight leading-[1.12] ${
          dark ? 'text-white' : 'text-slate-900'
        }`}
      >
        {title}
      </h2>
      {standfirst ? (
        <p
          className={`mt-5 text-base sm:text-lg leading-relaxed ${
            dark ? 'text-slate-300' : 'text-slate-600'
          }`}
        >
          {standfirst}
        </p>
      ) : null}
    </div>
  </Reveal>
);

/* ------------------------------------------------------------ page content */

const CHAPTERS = [
  { id: 'problem', label: 'The problem' },
  { id: 'schemes', label: 'What exists' },
  { id: 'gap', label: 'The gap' },
  { id: 'method', label: 'The method' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'integrate', label: 'Where it fits' }
];

/** The eight pipeline stages, each mapped to the phase that actually built it. */
const PIPELINE = [
  {
    icon: UploadCloud,
    title: 'Intake',
    body: 'A scanned register page, a photographed mutation entry, a sale deed PDF or a cadastral sheet is uploaded and checked - real file type, real size limits, stored against a real document record.',
    detail: 'Nothing is accepted on trust: an unreadable or unsupported file is rejected here, not silently passed downstream.'
  },
  {
    icon: Sparkles,
    title: 'Pre-processing',
    body: 'Pages are deskewed, denoised and contrast-corrected so faded ink and bleed-through stop defeating the recogniser.',
    detail: 'Enhancement is stored alongside the original page image. The original is never replaced.'
  },
  {
    icon: Eye,
    title: 'OCR and handwriting recognition',
    body: 'Every page is read - printed Devanagari and regional scripts as well as the clerk handwriting that fills older registers - and each recognised word keeps its position on the page.',
    detail: 'If the engine is unavailable, the system reports that failure. It never substitutes sample text for a page it could not read.'
  },
  {
    icon: Globe,
    title: 'Language handling',
    body: 'Script and language are detected per page, and text is translated for officers who do not read that script - with the source text kept intact beside the translation.',
    detail: 'A translation is a view of the record, never a replacement for it.'
  },
  {
    icon: BrainCircuit,
    title: 'Field extraction',
    body: 'Khasra number, khata number, survey number, owner names, area and classification are pulled out of the recognised text as structured claims.',
    detail: 'Each claim records which document, which page and which region of that page it came from.'
  },
  {
    icon: Gauge,
    title: 'Confidence scoring',
    body: 'Every extracted field carries a confidence value, and every parcel carries a sufficiency score built from extraction quality, cross-document agreement, temporal continuity and identity confidence.',
    detail: 'A component with no data available is shown as unavailable - not filled in with an average.'
  },
  {
    icon: GitCompare,
    title: 'Cross-document reconciliation',
    body: 'Claims about the same parcel from different documents and different years are lined up into a timeline, and contradictions or unexplained changes are raised as findings.',
    detail: 'An ownership change with no supporting deed is flagged as an evidence gap rather than quietly accepted.'
  },
  {
    icon: ShieldCheck,
    title: 'Human verification',
    body: 'A revenue officer reviews flagged records against the source page, corrects what is wrong and approves what is right. Only then does a record count as verified.',
    detail: 'A correction creates a new, superseding claim. The original AI output stays on the record permanently.'
  }
];

/* ------------------------------------------------------------------- page */

export const LandStory = () => {
  const progress = useScrollProgress();
  const chapterIds = useMemo(() => CHAPTERS.map((c) => c.id), []);
  const active = useActiveSection(chapterIds);
  const reduced = usePrefersReducedMotion();

  const scrollTo = useCallback(
    (id) => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
    },
    [reduced]
  );

  return (
    <div className="bg-white text-slate-900 antialiased">
      {/* Reading progress - a hairline, not a chrome bar */}
      <div className="fixed top-0 left-0 right-0 h-[3px] z-50 bg-transparent" aria-hidden="true">
        <div
          className="h-full bg-emerald-500 transition-[width] duration-150 ease-out"
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      {/* Masthead */}
      <header
        className="fixed top-0 left-0 right-0 z-40 backdrop-blur-md border-b"
        style={{ background: 'rgba(6,35,42,0.86)', borderColor: 'rgba(255,255,255,0.10)' }}
      >
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <svg viewBox="0 0 44 44" className="w-7 h-7 shrink-0" fill="none" aria-hidden="true">
              <path
                d="M22 3 L38 9 V21 C38 31 31 38.5 22 41 C13 38.5 6 31 6 21 V9 Z"
                fill={TEAL_600}
                stroke={GOLD}
                strokeWidth="1.6"
              />
              <path d="M15 18 H29 M15 23 H29 M15 28 H24" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            <div className="leading-none">
              <div className="text-white font-extrabold text-sm tracking-tight">Bhoomi AI</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Land Record Intelligence</div>
            </div>
          </div>
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-xs font-bold text-white px-3.5 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 transition-colors"
          >
            <Lock className="w-3.5 h-3.5" />
            Officer sign in
          </Link>
        </div>
      </header>

      {/* Chapter rail */}
      <nav
        className="hidden xl:flex flex-col gap-3 fixed right-8 top-1/2 -translate-y-1/2 z-40"
        aria-label="Chapters"
      >
        {CHAPTERS.map((c) => {
          const on = active === c.id;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => scrollTo(c.id)}
              className="group flex items-center gap-3 justify-end"
              aria-current={on ? 'true' : undefined}
            >
              <span
                className={`text-[10px] font-bold uppercase tracking-wider transition-opacity ${
                  on ? 'opacity-100 text-emerald-600' : 'opacity-0 group-hover:opacity-70 text-slate-500'
                }`}
              >
                {c.label}
              </span>
              <span
                className={`rounded-full transition-all ${
                  on ? 'w-2.5 h-2.5 bg-emerald-500' : 'w-1.5 h-1.5 bg-slate-300 group-hover:bg-slate-400'
                }`}
              />
            </button>
          );
        })}
      </nav>

      {/* ------------------------------------------------------------ hero */}
      <section
        className="relative min-h-screen flex items-center overflow-hidden pt-14"
        style={{ background: `linear-gradient(165deg, ${DEEP} 0%, ${TEAL_900} 58%, ${TEAL_800} 100%)` }}
      >
        {/* cadastral grid - the visual motif of the whole page */}
        <div
          className="absolute inset-0 opacity-[0.09] pointer-events-none"
          aria-hidden="true"
          style={{
            backgroundImage:
              'repeating-linear-gradient(0deg, rgba(255,255,255,.55) 0 1px, transparent 1px 104px), repeating-linear-gradient(90deg, rgba(255,255,255,.55) 0 1px, transparent 1px 104px)'
          }}
        />
        <div
          className="absolute -top-24 -right-24 w-[420px] h-[420px] rounded-full blur-3xl pointer-events-none"
          aria-hidden="true"
          style={{ background: 'rgba(16,185,129,0.16)' }}
        />

        <div className="relative z-10 max-w-6xl mx-auto px-5 sm:px-8 py-24 w-full">
          <Reveal>
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-bold tracking-wide mb-8"
              style={{ background: 'rgba(255,255,255,0.10)', color: '#cbd5e1' }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Smart India Hackathon 2026 &middot; Problem Statement 26018
            </div>
          </Reveal>

          <Reveal delay={80}>
            <h1 className="text-white font-extrabold tracking-tight leading-[1.05] text-[2.6rem] sm:text-6xl lg:text-7xl max-w-4xl">
              Two-thirds of India&rsquo;s pending court cases
              <span style={{ color: GOLD }}> are about land.</span>
            </h1>
          </Reveal>

          <Reveal delay={160}>
            <p className="mt-7 text-lg sm:text-xl text-slate-300 max-w-2xl leading-relaxed">
              Not because the country lacks records &mdash; but because the records cannot prove
              what they claim. This is the story of that gap, and of a system built to close it
              one document at a time.
            </p>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => scrollTo('problem')}
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm transition-colors"
              >
                Read the story
                <ChevronDown className="w-4 h-4" />
              </button>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-xl border font-bold text-sm text-white transition-colors hover:bg-white/10"
                style={{ borderColor: 'rgba(255,255,255,0.28)' }}
              >
                Enter the portal
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </Reveal>

          <Reveal delay={320}>
            <p className="mt-12 text-[11px] text-slate-500 max-w-xl leading-relaxed">
              Every figure on this page is a published government or research statistic, cited
              where it appears and listed in full at the end.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------- 01 problem */}
      <section id="problem" className="py-24 sm:py-32 bg-white">
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <ChapterHead
            numeral="01"
            kicker="The problem"
            title="The record says one thing. The land says another."
            standfirst="India does not have a shortage of land records. It has a shortage of land records that can be trusted without going to court. The reasons are structural, and they are old."
          />

          <div className="mt-16 grid gap-10 sm:grid-cols-3">
            <Reveal delay={0}>
              <Figure
                value={66}
                suffix="%"
                label="of pending court cases relate to land"
                note="A World Bank study cited in the PRS India review of land records and titles puts land-related disputes at roughly two-thirds of all pending cases."
                cite={1}
              />
            </Reveal>
            <Reveal delay={120}>
              <Figure
                value={20}
                suffix=" yrs"
                label="average time to resolve a land dispute"
                note="NITI Aayog's assessment, as cited in the same review. A title contested today may be settled by the next generation."
                cite={1}
              />
            </Reveal>
            <Reveal delay={240}>
              <Figure
                value={50}
                prefix="> "
                suffix=" yrs"
                label="average age of village cadastral maps"
                note="The Committee on State Agrarian Relations found the average village map in most states is more than half a century old."
                cite={1}
              />
            </Reveal>
          </div>

          <div className="mt-20 grid gap-6 md:grid-cols-3">
            {[
              {
                icon: BookOpen,
                title: 'Registration is not proof of ownership',
                body: 'India follows presumptive titling. Registering a sale deed records that a transaction happened - it does not guarantee the seller had the right to sell. The burden of verifying a title sits with the buyer, not the state.',
                cite: 1
              },
              {
                icon: Layers,
                title: 'Three departments, three truths',
                body: 'Records of rights sit with Revenue, maps with Survey and Settlement, deeds with Registration. They are maintained separately and updated at different times, so the same parcel can be described three different ways.',
                cite: 1
              },
              {
                icon: Users,
                title: 'Inheritance goes unrecorded',
                body: 'When land is divided among heirs, registration is often not mandatory. Partitions therefore go unrecorded for decades, and the person farming the land is not the person the record names.',
                cite: 1
              }
            ].map((card, i) => {
              const Icon = card.icon;
              return (
                <Reveal key={card.title} delay={i * 110}>
                  <div className="h-full rounded-2xl border border-slate-200 p-6 hover:border-slate-300 transition-colors">
                    <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center">
                      <Icon className="w-5 h-5 text-slate-700" />
                    </div>
                    <h3 className="mt-4 font-bold text-slate-900">
                      {card.title}
                      <Cite n={card.cite} />
                    </h3>
                    <p className="mt-2 text-sm text-slate-600 leading-relaxed">{card.body}</p>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------- 02 schemes */}
      <section
        id="schemes"
        className="py-24 sm:py-32 relative overflow-hidden"
        style={{ background: TEAL_900 }}
      >
        <div
          className="absolute inset-0 opacity-[0.07] pointer-events-none"
          aria-hidden="true"
          style={{
            backgroundImage:
              'repeating-linear-gradient(0deg, rgba(255,255,255,.6) 0 1px, transparent 1px 96px), repeating-linear-gradient(90deg, rgba(255,255,255,.6) 0 1px, transparent 1px 96px)'
          }}
        />
        <div className="relative z-10 max-w-6xl mx-auto px-5 sm:px-8">
          <ChapterHead
            dark
            numeral="02"
            kicker="What already exists"
            title="India has spent two decades digitising land records. It worked."
            standfirst="Any honest account of this problem has to start by saying what the state has already built - because it is substantial, and because a new system is only useful if it fits into it rather than ignoring it."
          />

          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <Reveal delay={0}>
              <Figure
                dark
                value={95.09}
                decimals={2}
                suffix="%"
                label="of villages have computerised RoR"
                note="625,137 of 657,397 villages, as reported by the Department of Land Resources for DILRMP as on 31 December 2023."
                cite={2}
              />
            </Reveal>
            <Reveal delay={110}>
              <Figure
                dark
                value={68}
                prefix="> "
                suffix="%"
                label="of cadastral maps digitised"
                note="About 25.2 million of 37.0 million maps across 28 states and UTs, same reporting date."
                cite={2}
              />
            </Reveal>
            <Reveal delay={220}>
              <Figure
                dark
                value={93}
                prefix="> "
                suffix="%"
                label="of sub-registrar offices computerised"
                note="5,060 of 5,329 offices; about 4,669 are integrated with land records."
                cite={2}
              />
            </Reveal>
            <Reveal delay={330}>
              <Figure
                dark
                value={3.29}
                decimals={2}
                suffix=" lakh"
                label="villages drone-surveyed under SVAMITVA"
                note="Against a target of 3.44 lakh villages; 3.10 crore property cards prepared and 2.65 crore distributed, as on 11 March 2026."
                cite={3}
              />
            </Reveal>
          </div>

          <Reveal delay={120}>
            <div
              className="mt-16 rounded-2xl border p-7 sm:p-9"
              style={{ background: TEAL_800, borderColor: 'rgba(255,255,255,0.12)' }}
            >
              <h3 className="text-white font-bold text-lg">The programmes this system has to live inside</h3>
              <div className="mt-6 grid gap-6 sm:grid-cols-2">
                {[
                  {
                    icon: Database,
                    name: 'DILRMP',
                    full: 'Digital India Land Records Modernisation Programme',
                    body: 'A centrally funded programme running eight components - computerising records of rights and registration, survey and resurvey, modern record rooms, digitising revenue courts and linking Aadhaar to RoR on a voluntary basis.',
                    cite: 2
                  },
                  {
                    icon: Map,
                    name: 'SVAMITVA',
                    full: 'Survey of Villages and Mapping with Improvised Technology',
                    body: 'Drone survey of inhabited rural land to give village residents a formal, mapped property record - in many cases the first documentary proof of ownership their household has held.',
                    cite: 3
                  },
                  {
                    icon: Link2,
                    name: 'ULPIN / Bhu-Aadhaar',
                    full: 'Unique Land Parcel Identification Number',
                    body: 'A permanent identifier for a land parcel, derived from its geo-coordinates, so the same plot can be recognised across departments and across time instead of by a locally worded description.',
                    cite: 2
                  },
                  {
                    icon: FileText,
                    name: 'NGDRS',
                    full: 'National Generic Document Registration System',
                    body: 'A common registration platform that states can adopt in place of bespoke systems, so deed registration data is captured in a comparable shape nationwide.',
                    cite: 4
                  }
                ].map((p) => {
                  const Icon = p.icon;
                  return (
                    <div key={p.name} className="flex gap-4">
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                        style={{ background: 'rgba(255,255,255,0.10)' }}
                      >
                        <Icon className="w-5 h-5" style={{ color: GOLD }} />
                      </div>
                      <div>
                        <div className="text-white font-bold text-sm">
                          {p.name}
                          <Cite n={p.cite} />
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">{p.full}</div>
                        <p className="text-sm text-slate-300 mt-2 leading-relaxed">{p.body}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ----------------------------------------------------------- 03 gap */}
      <section id="gap" className="py-24 sm:py-32 bg-slate-50">
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <ChapterHead
            numeral="03"
            kicker="The gap"
            title="Digitised is not the same as verified."
            standfirst="A computerised record of rights is a typed row in a database. It tells you what the current entry says. It does not tell you which document that entry came from, whether the change before it was ever justified, or whether two departments still disagree about the same field."
          />

          <div className="mt-14 grid gap-6 lg:grid-cols-2">
            <Reveal>
              <div className="rounded-2xl bg-white border border-slate-200 p-7 h-full">
                <div className="flex items-center gap-2 text-emerald-700">
                  <CheckCircle2 className="w-5 h-5" />
                  <span className="text-xs font-bold uppercase tracking-wider">What digitisation solved</span>
                </div>
                <ul className="mt-5 space-y-3 text-sm text-slate-700">
                  {[
                    'The current entry for a parcel can be looked up online instead of queued for at a counter.',
                    'Registration and record-of-rights data increasingly sit in the same system rather than in separate ledgers.',
                    'Parcels are getting permanent identifiers, so the same plot can be matched across departments.',
                    'Rural inhabited land is being mapped and given formal property cards for the first time.'
                  ].map((t) => (
                    <li key={t} className="flex gap-3">
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>

            <Reveal delay={140}>
              <div className="rounded-2xl bg-white border-2 p-7 h-full" style={{ borderColor: '#fca5a5' }}>
                <div className="flex items-center gap-2 text-red-700">
                  <AlertTriangle className="w-5 h-5" />
                  <span className="text-xs font-bold uppercase tracking-wider">What it did not</span>
                </div>
                <ul className="mt-5 space-y-3 text-sm text-slate-700">
                  {[
                    'The historical chain of title still lives in handwritten registers, in regional scripts, on paper that is fading - not in the database.',
                    'A digitised entry carries no pointer back to the page and the line it was transcribed from, so it cannot be independently checked.',
                    'Roughly a third of cadastral maps are still not digitised, and about half of villages are still not geo-referenced.',
                    'Nothing in a typed entry flags that an owner changed between two years with no registered deed to explain it.'
                  ].map((t) => (
                    <li key={t} className="flex gap-3">
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-red-400 shrink-0" />
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-5 text-[11px] text-slate-500 leading-relaxed">
                  Derived from the same DILRMP progress figures above: 68% of maps digitised leaves
                  roughly 32% undigitised, and 49.10% of villages geo-referenced leaves roughly half
                  without a ULPIN-grade parcel identity.
                  <Cite n={2} />
                </p>
              </div>
            </Reveal>
          </div>

          <Reveal delay={80}>
            <div className="mt-14 rounded-2xl p-8 sm:p-10" style={{ background: DEEP }}>
              <div className="flex flex-col sm:flex-row gap-6 sm:items-center">
                <Compass className="w-10 h-10 shrink-0" style={{ color: GOLD }} />
                <p className="text-lg sm:text-xl text-white leading-relaxed font-medium">
                  The unsolved problem is not storage. It is <span style={{ color: GOLD }}>evidence</span> &mdash;
                  making a legacy paper record machine-readable without losing the one property that
                  makes it worth anything in a dispute: the ability to point at the exact place it
                  came from.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* -------------------------------------------------------- 04 method */}
      <section id="method" className="py-24 sm:py-32 bg-white">
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <ChapterHead
            numeral="04"
            kicker="The method"
            title="How a paper register becomes a verified record."
            standfirst="Eight stages, in order. Each one keeps what the stage before it produced, so a value can always be walked backwards to the page it was read from."
          />

          <div className="mt-16 relative">
            {/* the spine */}
            <div
              className="hidden md:block absolute left-[27px] top-4 bottom-4 w-px"
              style={{ background: 'linear-gradient(to bottom, #10b981, #cbd5e1)' }}
              aria-hidden="true"
            />
            <ol className="space-y-5">
              {PIPELINE.map((step, i) => {
                const Icon = step.icon;
                return (
                  <li key={step.title}>
                    <Reveal delay={Math.min(i * 60, 300)}>
                      <div className="flex gap-5 group">
                        <div className="relative shrink-0">
                          <div className="w-14 h-14 rounded-2xl bg-white border-2 border-slate-200 group-hover:border-emerald-500 flex items-center justify-center transition-colors">
                            <Icon className="w-6 h-6 text-emerald-700" />
                          </div>
                          <span className="absolute -top-1.5 -left-1.5 w-6 h-6 rounded-full bg-slate-900 text-white text-[11px] font-bold flex items-center justify-center">
                            {i + 1}
                          </span>
                        </div>
                        <div className="pt-1 pb-2 flex-1 border-b border-slate-100">
                          <h3 className="font-bold text-slate-900">{step.title}</h3>
                          <p className="mt-1.5 text-sm text-slate-600 leading-relaxed max-w-3xl">
                            {step.body}
                          </p>
                          <p className="mt-2 text-xs text-emerald-800 bg-emerald-50 inline-block px-2.5 py-1.5 rounded-lg leading-relaxed max-w-3xl">
                            {step.detail}
                          </p>
                        </div>
                      </div>
                    </Reveal>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ 05 evidence */}
      <section
        id="evidence"
        className="py-24 sm:py-32 relative overflow-hidden"
        style={{ background: TEAL_900 }}
      >
        <div
          className="absolute inset-0 opacity-[0.07] pointer-events-none"
          aria-hidden="true"
          style={{
            backgroundImage:
              'repeating-linear-gradient(0deg, rgba(255,255,255,.6) 0 1px, transparent 1px 96px), repeating-linear-gradient(90deg, rgba(255,255,255,.6) 0 1px, transparent 1px 96px)'
          }}
        />
        <div className="relative z-10 max-w-6xl mx-auto px-5 sm:px-8">
          <ChapterHead
            dark
            numeral="05"
            kicker="Evidence"
            title="Every field can be asked: how do you know that?"
            standfirst="This is the part that separates the system from a bulk transcription exercise. An extracted value is never stored on its own - it is stored as a claim with a provenance chain behind it."
          />

          <Reveal>
            <div className="mt-14 flex flex-wrap items-center gap-2 sm:gap-3">
              {[
                'Original document',
                'Page',
                'OCR run',
                'Text region',
                'Extracted claim',
                'Validation',
                'Officer correction',
                'Verified record'
              ].map((node, i, arr) => (
                <React.Fragment key={node}>
                  <span
                    className="px-3 py-2 rounded-lg text-[11px] sm:text-xs font-bold text-white"
                    style={{ background: i === arr.length - 1 ? '#047857' : 'rgba(255,255,255,0.10)' }}
                  >
                    {node}
                  </span>
                  {i < arr.length - 1 ? (
                    <ArrowRight className="w-3.5 h-3.5 shrink-0" style={{ color: TEAL_600 }} />
                  ) : null}
                </React.Fragment>
              ))}
            </div>
          </Reveal>

          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Search,
                title: 'Point at the source',
                body: 'A claim stores its document, page number and the bounding box of the text it came from. The interface can therefore show the officer the actual scanned region behind a value, not a re-typed copy of it.'
              },
              {
                icon: Clock,
                title: 'Never overwrite history',
                body: 'Correcting a field does not edit it. It writes a new claim that supersedes the old one, and both stay on the record - so the original machine output and the human judgement that replaced it remain distinguishable forever.'
              },
              {
                icon: Ruler,
                title: 'Say when you do not know',
                body: 'Where no evidence region exists, the record says so and gives the reason. A missing confidence component is reported as unavailable rather than filled with a plausible-looking default.'
              }
            ].map((c, i) => {
              const Icon = c.icon;
              return (
                <Reveal key={c.title} delay={i * 120}>
                  <div
                    className="h-full rounded-2xl border p-6"
                    style={{ background: TEAL_800, borderColor: 'rgba(255,255,255,0.12)' }}
                  >
                    <Icon className="w-6 h-6" style={{ color: GOLD }} />
                    <h3 className="mt-4 font-bold text-white">{c.title}</h3>
                    <p className="mt-2 text-sm text-slate-300 leading-relaxed">{c.body}</p>
                  </div>
                </Reveal>
              );
            })}
          </div>

          <Reveal delay={100}>
            <p className="mt-12 text-sm text-slate-400 max-w-3xl leading-relaxed">
              The same discipline applies to this system&rsquo;s own limits. If the recognition engine
              is unavailable, processing reports a failure &mdash; it does not fall back to demonstration
              data and present it as though it came from the uploaded document. Seeded demo records
              exist for development and are kept separate from anything extracted from a real file.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ----------------------------------------------------- 06 integrate */}
      <section id="integrate" className="py-24 sm:py-32 bg-white">
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <ChapterHead
            numeral="06"
            kicker="Where it fits"
            title="A layer on top of what the state already runs."
            standfirst="This is not a replacement land record system. It is the verification layer between a scanned legacy document and the official record that a revenue department is willing to stand behind."
          />

          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Cpu,
                title: 'Reads what exists',
                body: 'Scanned registers, mutation entries, sale deeds and cadastral sheets - in the condition they are actually in, including handwritten pages in regional scripts.'
              },
              {
                icon: ShieldCheck,
                title: 'Adds the evidence layer',
                body: 'Extraction, confidence, contradiction detection, timeline reconstruction and officer verification - producing records that carry their own justification.'
              },
              {
                icon: MapPin,
                title: 'Hands off to the system of record',
                body: 'Verified, geo-tagged records are designed to flow onward through APIs to state land record systems - with any integration that is not live clearly labelled as a mock rather than dressed up as a connection.'
              }
            ].map((c, i) => {
              const Icon = c.icon;
              return (
                <Reveal key={c.title} delay={i * 120}>
                  <div className="h-full rounded-2xl border border-slate-200 p-6">
                    <div className="w-11 h-11 rounded-xl bg-emerald-50 flex items-center justify-center">
                      <Icon className="w-5 h-5 text-emerald-700" />
                    </div>
                    <h3 className="mt-4 font-bold text-slate-900">{c.title}</h3>
                    <p className="mt-2 text-sm text-slate-600 leading-relaxed">{c.body}</p>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- CTA */}
      <section
        className="py-24 sm:py-32 relative overflow-hidden"
        style={{ background: `linear-gradient(165deg, ${DEEP} 0%, ${TEAL_900} 100%)` }}
      >
        <div
          className="absolute inset-0 opacity-[0.08] pointer-events-none"
          aria-hidden="true"
          style={{
            backgroundImage:
              'repeating-linear-gradient(0deg, rgba(255,255,255,.6) 0 1px, transparent 1px 104px), repeating-linear-gradient(90deg, rgba(255,255,255,.6) 0 1px, transparent 1px 104px)'
          }}
        />
        <div className="relative z-10 max-w-3xl mx-auto px-5 sm:px-8 text-center">
          <Reveal>
            <h2 className="text-white text-3xl sm:text-4xl font-extrabold tracking-tight leading-tight">
              See it work on a real document.
            </h2>
          </Reveal>
          <Reveal delay={100}>
            <p className="mt-5 text-slate-300 leading-relaxed">
              The portal is restricted to authorised revenue, tehsil and verification staff. Upload
              a scanned record and follow it through every stage described above &mdash; extraction,
              scoring, contradiction detection and officer review.
            </p>
          </Reveal>
          <Reveal delay={180}>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm transition-colors"
              >
                <Lock className="w-4 h-4" />
                Officer sign in
              </Link>
              <button
                type="button"
                onClick={() => window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' })}
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl border text-white font-bold text-sm transition-colors hover:bg-white/10"
                style={{ borderColor: 'rgba(255,255,255,0.28)' }}
              >
                Back to the top
              </button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* --------------------------------------------------------- sources */}
      <section id="sources" className="py-16 bg-slate-50 border-t border-slate-200">
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Sources</h2>
          <ol className="mt-5 space-y-3 text-xs text-slate-600 leading-relaxed">
            <li>
              <span className="font-bold text-slate-800">[1]</span> PRS India, &ldquo;Land Records and
              Titles in India&rdquo; &mdash; citing a World Bank study on land disputes as a share of
              pending cases, NITI Aayog on average resolution time, and the Committee on State
              Agrarian Relations on cadastral map age.{' '}
              <a
                className="text-emerald-700 font-semibold hover:underline break-all"
                href="https://prsindia.org/policy/discussion-papers/land-records-and-titles-india"
                target="_blank"
                rel="noreferrer"
              >
                prsindia.org
              </a>
            </li>
            <li>
              <span className="font-bold text-slate-800">[2]</span> Department of Land Resources,
              Ministry of Rural Development &mdash; Digital India Land Records Modernisation Programme
              (DILRMP) progress, figures as on 31 December 2023.{' '}
              <a
                className="text-emerald-700 font-semibold hover:underline break-all"
                href="https://dolr.gov.in/en/programmes-schemes/dilrmp-2/"
                target="_blank"
                rel="noreferrer"
              >
                dolr.gov.in
              </a>
            </li>
            <li>
              <span className="font-bold text-slate-800">[3]</span> Press Information Bureau, Government
              of India &mdash; SVAMITVA scheme progress, figures as on 11 March 2026.
            </li>
            <li>
              <span className="font-bold text-slate-800">[4]</span> Ministry of Rural Development &mdash;
              National Generic Document Registration System (NGDRS) adoption by states and UTs.
            </li>
          </ol>
          <p className="mt-8 text-[11px] text-slate-500 leading-relaxed max-w-3xl">
            Figures are reproduced as published, with the reporting date shown, and are not adjusted
            or projected forward. Where this page derives a number from a published one &mdash; for
            example the share of cadastral maps not yet digitised &mdash; the derivation is stated at
            the point it appears.
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------- footer */}
      <footer className="py-10" style={{ background: DEEP }}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5">
            <svg viewBox="0 0 44 44" className="w-6 h-6" fill="none" aria-hidden="true">
              <path
                d="M22 3 L38 9 V21 C38 31 31 38.5 22 41 C13 38.5 6 31 6 21 V9 Z"
                fill={TEAL_600}
                stroke={GOLD}
                strokeWidth="1.6"
              />
              <path d="M15 18 H29 M15 23 H29 M15 28 H24" stroke="white" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            <span className="text-white font-bold text-sm">Bhoomi AI</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed sm:text-right max-w-lg">
            Prototype built for Smart India Hackathon 2026, Problem Statement 26018. Not a deployed
            government system and not an official portal of any ministry or department. Programme
            names above refer to public government schemes for context only.
          </p>
        </div>
      </footer>
    </div>
  );
};
