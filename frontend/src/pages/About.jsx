export default function About() {
  return (
    <div className="max-w-[1000px] mx-auto px-6 py-10" data-testid="about-page">
      <p className="text-dim text-[11px] uppercase tracking-widest mb-3">About</p>
      <h1 className="font-editorial text-4xl md:text-5xl leading-tight mb-6">
        PitchWise is the FotMob for cricket.
      </h1>
      <p className="text-lg text-muted-foreground mb-10 max-w-2xl">
        Cricket has scorecards. It has commentary. It has statistics.
        What it doesn&apos;t have is a way to tell you <em>why</em> a match unfolded the way it did.
      </p>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          ["Pressure Index", "Every ball carries pressure — chase context, phase, wickets in hand. We measure it."],
          ["Difficulty", "Not every wicket is equal. Not every boundary is equal. We weight both."],
          ["Match Context", "Impact only matters relative to what the moment demanded. We compute both."],
        ].map(([title, body]) => (
          <div key={title} className="rounded-lg border border-border/50 bg-card/60 p-5">
            <h3 className="font-editorial text-xl mb-2">{title}</h3>
            <p className="text-sm text-muted-foreground">{body}</p>
          </div>
        ))}
      </section>

      <div className="mt-16 text-dim text-sm">
        v0.1 · Explainable Cricket Intelligence
      </div>
    </div>
  );
}
