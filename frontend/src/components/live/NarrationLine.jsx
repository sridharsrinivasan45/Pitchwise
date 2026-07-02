import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

/**
 * Ambient narration line. In M2 this is a static string derived from the match state.
 * In M5 the AI narrator replaces the text with an evolving, event-driven line.
 */
export default function NarrationLine({ text }) {
  return (
    <motion.div
      key={text}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      data-testid="narration-line"
      className="flex items-start gap-3 py-4"
    >
      <div className="mt-1 h-6 w-6 rounded-md bg-amber-soft border border-amber-soft flex items-center justify-center shrink-0">
        <Sparkles className="w-3.5 h-3.5" style={{ color: "hsl(var(--primary))" }} />
      </div>
      <p className="text-lg md:text-xl font-editorial leading-snug text-foreground/90 max-w-3xl">
        {text || "PitchWise is watching."}
      </p>
    </motion.div>
  );
}
