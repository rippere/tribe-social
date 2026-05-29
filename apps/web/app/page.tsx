import Link from 'next/link'

function HeroSection() {
  return (
    <section className="relative overflow-hidden py-24 px-6">
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 h-96 w-96 rounded-full bg-[#6366F1]/10 blur-3xl" />
      </div>

      <div className="mx-auto max-w-4xl text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#1F2937] bg-[#111827] px-4 py-1.5 text-sm text-[#9CA3AF]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#6366F1] animate-pulse" />
          TRIBE v2 Neural Encoding
        </div>

        <h1 className="text-5xl font-bold tracking-tight text-[#F9FAFB] sm:text-6xl lg:text-7xl mb-6 leading-tight">
          Does your content{' '}
          <span className="text-[#6366F1]">activate the brain?</span>
        </h1>

        <p className="text-lg text-[#9CA3AF] max-w-2xl mx-auto mb-10 leading-relaxed">
          TRIBE v2 neural encoding scores your videos against 6 brain regions that predict viral engagement.
          Stop guessing — let neuroscience drive your content strategy.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#6366F1] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#4F46E5]"
          >
            View Corpus →
          </Link>
          <Link
            href="/scorer"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#1F2937] bg-[#111827] px-6 py-3 text-sm font-semibold text-[#F9FAFB] transition hover:border-[#6366F1]/50"
          >
            Score a Clip →
          </Link>
        </div>

        <div className="mx-auto max-w-sm rounded-2xl border border-[#1F2937] bg-[#111827] p-6">
          <p className="text-sm text-[#9CA3AF] mb-2">Corpus Average Score</p>
          <div className="flex items-end gap-2 mb-4">
            <span className="text-6xl font-bold text-[#6366F1]">63.8</span>
            <span className="text-2xl text-[#9CA3AF] mb-2">/ 100</span>
          </div>
          <div className="flex gap-3 text-xs">
            <span className="rounded-full bg-[#16A34A]/10 px-3 py-1 text-[#16A34A] font-medium">12 POST</span>
            <span className="rounded-full bg-[#D97706]/10 px-3 py-1 text-[#D97706] font-medium">8 REVISE</span>
            <span className="rounded-full bg-[#DC2626]/10 px-3 py-1 text-[#DC2626] font-medium">4 RETHINK</span>
          </div>
        </div>
      </div>
    </section>
  )
}

function AudienceSection() {
  const cards = [
    {
      icon: '🔬',
      title: 'ML Engineers',
      description:
        'A full corpus pipeline from raw TRIBE v2 scores to normalized features, with Pearson r computed across 6 brain regions and engagement metrics.',
    },
    {
      icon: '🚀',
      title: 'Founders',
      description:
        'Know before you post. Our GO/NO-GO verdict synthesizes neural signal from 24 scored videos into a clear content investment decision.',
    },
    {
      icon: '📊',
      title: 'Content Orgs',
      description:
        'Score every piece of content against neuroscience benchmarks. Identify which brain regions are underactivated and get specific revision templates.',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-[#1F2937]">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold text-[#F9FAFB] mb-12">
          Built for every layer of the stack
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {cards.map((card) => (
            <div
              key={card.title}
              className="rounded-xl border border-[#1F2937] bg-[#111827] p-6 hover:border-[#6366F1]/40 transition-colors"
            >
              <div className="text-3xl mb-4">{card.icon}</div>
              <h3 className="text-lg font-semibold text-[#F9FAFB] mb-2">{card.title}</h3>
              <p className="text-sm text-[#9CA3AF] leading-relaxed">{card.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function BrainRegionSection() {
  const regions = [
    { name: 'vmPFC', role: 'Value / reward signal', color: '#FFB74D' },
    { name: 'TPJ', role: 'Social cognition & mentalising', color: '#81C784' },
    { name: 'IFJa / IFJp', role: 'Executive attention', color: '#4FC3F7' },
    { name: 'Area 45', role: 'Language processing', color: '#CE93D8' },
    { name: 'MT/V5', role: 'Visual motion', color: '#80DEEA' },
  ]

  return (
    <section className="py-20 px-6 border-t border-[#1F2937]">
      <div className="mx-auto max-w-4xl text-center">
        <h2 className="text-3xl font-bold text-[#F9FAFB] mb-4">6 Brain Regions. One Score.</h2>
        <p className="text-[#9CA3AF] mb-12 max-w-2xl mx-auto">
          TRIBE v2 maps every second of video onto activation in these key regions.
          Higher activation predicts stronger neural engagement — and higher predicted shareability.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {regions.map(r => (
            <div key={r.name} className="flex items-center gap-3 rounded-lg border border-[#1F2937] bg-[#111827] px-4 py-3">
              <div className="h-3 w-3 rounded-full flex-shrink-0" style={{ background: r.color }} />
              <div className="text-left">
                <p className="text-sm font-semibold text-[#F9FAFB]">{r.name}</p>
                <p className="text-xs text-[#9CA3AF]">{r.role}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <AudienceSection />
      <BrainRegionSection />
    </>
  )
}
