"use client";

/**
 * First-login welcome shown in the chat empty state (in place of the starter
 * prompts) while the user hasn't dismissed `welcome_v1`. Each mode card
 * prefills its `tryItPrompt`; "Skip for now" just dismisses.
 *
 * Dismissing (either path) marks the welcome AND the modes it showcases as
 * seen, so a brand-new user isn't immediately re-nagged by the per-feature
 * "New" badges on those same controls. Those badges are reserved for returning
 * users when a genuinely new feature (or version) ships.
 *
 * Visibility is decided by the parent via useIsNewUser(); this component
 * assumes it is only rendered for a new user.
 */

import { Card } from "@/components/ui";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";
import { FEATURE_REGISTRY, ALL_FEATURE_KEYS } from "@/lib/onboarding/feature-registry";

// The prompt-driven modes to feature in the welcome (swarm/research/workshop/
// design). Pioneer academy has no tryItPrompt — it's surfaced contextually on
// the swarm panel instead.
const WELCOME_FEATURE_KEYS = ALL_FEATURE_KEYS.filter(
  (k) => FEATURE_REGISTRY[k].tryItPrompt
);

const DISMISS_KEYS = ["welcome_v1" as const, ...WELCOME_FEATURE_KEYS];

export function WelcomeCard({ onPrompt }: { onPrompt: (prompt: string) => void }) {
  const markSeenMany = useOnboardingStore((s) => s.markSeenMany);

  const dismiss = () => markSeenMany(DISMISS_KEYS);

  const handleTry = (prompt: string) => {
    dismiss();
    onPrompt(prompt);
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[13px] font-medium text-[var(--chat-muted)]">
          New here? Here&apos;s what you can do.
        </p>
        <button
          type="button"
          onClick={dismiss}
          className="text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors py-2 px-1"
        >
          Skip for now
        </button>
      </div>

      {/* Mobile: single column with horizontal card layout. sm+: 2-column vertical. */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {WELCOME_FEATURE_KEYS.map((key) => {
          const meta = FEATURE_REGISTRY[key];
          const Icon = meta.icon;
          return (
            <Card
              key={key}
              as="div"
              role="button"
              tabIndex={0}
              padding="none"
              interactive
              onClick={() => handleTry(meta.tryItPrompt!)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleTry(meta.tryItPrompt!);
                }
              }}
              className="group flex flex-col gap-2 px-4 py-3.5 text-left"
            >
              <div className="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] group-hover:border-[var(--chat-accent)] group-hover:text-[var(--chat-accent)] transition-colors text-[var(--chat-muted)]">
                <Icon size={15} />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-sm font-semibold text-[var(--chat-text)] leading-tight">
                  {meta.title}
                </span>
                <span className="text-xs text-[var(--chat-muted)] leading-snug">
                  {meta.description}
                </span>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
