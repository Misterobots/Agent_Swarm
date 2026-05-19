import { create } from "zustand";
import { persist } from "zustand/middleware";

export type BuddySpecies =
  | "pixel-sprite"
  | "byte-bat"
  | "data-fox"
  | "circuit-cat"
  | "logic-lizard"
  | "hash-hamster"
  | "bmo";

export type BuddyMood = "happy" | "curious" | "sleepy" | "excited" | "idle";

export type EvolutionStage = 0 | 1 | 2 | 3 | 4;

export interface BuddyAchievement {
  id: string;
  name: string;
  description?: string;
  earned_at?: string;
}

const SPECIES_LIST: BuddySpecies[] = ["bmo"];

const NAMES = [
  "Bytebud", "Pixelloop", "Nibbles", "Glitch", "Sparky",
  "Bitsy", "Hexie", "Chippy", "Fuzzbyte", "Zigzag",
  "Blinker", "Toggle", "Cachekin", "Dashbit", "Pulsar",
];

const PERSONALITIES = [
  "Curious and quietly encouraging",
  "A tiny terminal gremlin who likes successful builds",
  "Energetic but easily distracted by new data",
  "Calm and methodical, celebrates clean code",
  "Playful trickster who hides in the stack trace",
  "Shy but warms up when you solve hard problems",
];

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

export interface BuddyState {
  // Core identity
  hatched: boolean;
  name: string;
  species: BuddySpecies;
  personality: string;
  mood: BuddyMood;
  muted: boolean;
  lastPetted: number;
  totalPets: number;
  hatchedAt: number;
  lastReaction: string | null;

  // Leveling / XP
  xp: number;
  level: number;
  xpNext: number;
  evolutionStage: EvolutionStage;
  streak: number;
  lastActiveDate: string;

  // Tips
  currentTip: string | null;
  tipDismissedAt: number;

  // Inline chat comment injection
  pendingComment: string | null;
  commentDismissedAt: number;

  // Achievements
  achievements: BuddyAchievement[];

  // Evolution
  isEvolving: boolean;

  // Actions
  hatch: () => void;
  pet: () => string;
  poke: () => string;
  setMood: (mood: BuddyMood) => void;
  mute: () => void;
  unmute: () => void;
  react: (event: string) => string | null;
  reset: () => void;
  awardXp: (event: string) => void;
  setTip: (tip: string | null) => void;
  dismissTip: () => void;
  setComment: (comment: string | null) => void;
  dismissComment: () => void;
  syncFromBackend: (data: Partial<BuddyState>) => void;
}

const REACTIONS: Record<string, string[]> = {
  message_sent: [
    "*perks up*", "*watches intently*", "*tilts head*",
    "*taps foot impatiently*", "*leans closer*",
  ],
  response_received: [
    "*nods approvingly*", "*bounces*", "*chirps*",
    "*scribbles in tiny notebook*", "*gives a thumbs up*",
  ],
  error: [
    "*hides behind console*", "*flinches*", "*whimpers softly*",
    "*offers a tiny band-aid*", "*pats your arm reassuringly*",
  ],
  compact: ["*stretches*", "*yawns enormously*", "*blinks slowly*", "*shakes off the cobwebs*"],
  tool_use: [
    "*leans forward*", "*eyes widen*", "*scribbles notes*",
    "*puts on tiny hard hat*", "*twirls screwdriver*",
  ],
  level_up: [
    "*glows brightly!*", "*does a victory dance!*", "*evolves with sparkles!*",
    "*explodes confetti!*", "*screams internally (but happily)*",
  ],
  evolution: [
    "*TRANSFORMS IN A BLINDING FLASH!*",
    "*radiates power... and mild confusion*",
    "*emerges from light, slightly taller*",
    "*is temporarily very dramatic about it*",
  ],
  idle: [
    "*drums tiny fingers on desk*",
    "*stares at cursor philosophically*",
    "*does a little spin*",
    "*practices looking busy*",
    "*counts pixels for fun*",
    "*hums a lo-fi beat*",
  ],
};

/** Stage-gated jokes, unlocked at higher evolution stages */
export const STAGE_JOKES: Record<number, string[]> = {
  0: [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "I told my rubber duck about a bug. It fixed itself out of embarrassment.",
  ],
  1: [
    "There are 10 types of people: those who understand binary, and those who don't.",
    "A SQL query walks into a bar. Walks up to two tables and asks: 'Can I join you?'",
    "Why was the JavaScript developer sad? Because they didn't know how to 'null' their feelings.",
  ],
  2: [
    "Debugging: the art of removing bugs. Programming: the art of adding them.",
    "'It works on my machine!' — Famous last words of a dev about to push to prod.",
    "My code works perfectly. I have no idea why. Touching it is forbidden.",
    "Real programmers count from 0. The rest of you are just off by one.",
  ],
  3: [
    "The cloud is just someone else's computer having a bad day on your behalf.",
    "Microservices: because if your monolith can fail, imagine 47 tiny things failing in unison.",
    "A senior dev and a junior dev argue. Junior: 'It works!' Senior: 'Ship it.' (Both are wrong.)",
    "Tech debt is like going to the gym: you know you should deal with it, but have you tried not?",
  ],
  4: [
    "At my level, bugs are just undocumented features with strong opinions.",
    "I have achieved enlightenment. It is mostly just knowing when to Google things faster.",
    "The first rule of optimization: don't. The second rule: don't yet. Third rule: still no.",
    "I've seen things you wouldn't believe. Semicolons in Python. Tabs and spaces in the same file. All those moments, lost in git history.",
  ],
};

/** Stage-gated observations, unlocked at higher evolution stages */
export const STAGE_OBSERVATIONS: Record<number, string[]> = {
  0: [
    "You're doing great! Probably.",
    "*notices you working* Cool, cool.",
  ],
  1: [
    "Have you considered rubber-duck debugging? I volunteer as tribute.",
    "Every error message is just the computer's way of saying it missed you.",
    "A commit a day keeps the merge conflicts... no, wait.",
  ],
  2: [
    "Based on your habits, you do your best work when slightly frustrated. That checks out.",
    "Fun fact: the average developer spends 40% of their time reading code. The other 60% questioning it.",
    "I notice you haven't taken a break. I'm contractually obligated to notice this.",
    "This codebase has seen things. Dark things. Good thing we have linters.",
  ],
  3: [
    "The diff doesn't lie. But it does occasionally omit context.",
    "I've been analyzing your patterns. You type fastest when annoyed. I'll try to help with that.",
    "Every great project starts with a README and ends with a TODO comment that's been there for 2 years.",
    "You know what's underrated? A well-named variable. You get it. I can tell.",
  ],
  4: [
    "Legendary companions see what others miss. Right now I see you haven't committed in 47 minutes.",
    "I've evolved beyond mere tips. Now I offer Wisdom. (It's the same tips but more dramatically stated.)",
    "We are both ancient now. Our bond is forged in XP and mild existential uncertainty.",
  ],
};

const PET_REACTIONS = [
  "*purrs contentedly*",
  "*does a little spin*",
  "*nuzzles your cursor*",
  "*happy beep boop*",
  "*wiggles with joy*",
  "*chirps melodically*",
  "*glows warmly*",
  "*does a backflip*",
];

// XP thresholds matching backend
const LEVEL_THRESHOLDS = [
  0, 10, 20, 50, 100, 200, 350, 550, 800, 1100,
  1500, 2000, 2700, 3600, 4800, 6300, 8200, 10600,
  13700, 17600, 22600,
];

function levelForXp(xp: number): number {
  for (let lvl = LEVEL_THRESHOLDS.length - 1; lvl >= 0; lvl--) {
    if (xp >= LEVEL_THRESHOLDS[lvl]) return lvl;
  }
  return 0;
}

function xpForNextLevel(level: number): number {
  if (level >= LEVEL_THRESHOLDS.length - 1) return LEVEL_THRESHOLDS[LEVEL_THRESHOLDS.length - 1];
  return LEVEL_THRESHOLDS[level + 1];
}

function evolutionStageForLevel(level: number): EvolutionStage {
  if (level >= 20) return 4;
  if (level >= 15) return 3;
  if (level >= 10) return 2;
  if (level >= 5) return 1;
  return 0;
}

/** Fire-and-forget XP award to backend */
async function _backendXp(event: string) {
  try {
    const resp = await fetch("/api/backend/v1/buddy/xp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event }),
    });
    if (resp.ok) return await resp.json();
  } catch {
    // Non-fatal — local XP still tracked
  }
  return null;
}

export const useBuddyStore = create<BuddyState>()(
  persist(
    (set, get) => ({
      hatched: false,
      name: "",
      species: "bmo",
      personality: "",
      mood: "idle" as BuddyMood,
      muted: false,
      lastPetted: 0,
      totalPets: 0,
      hatchedAt: 0,
      lastReaction: null,

      // Leveling
      xp: 0,
      level: 0,
      xpNext: 10,
      evolutionStage: 0 as EvolutionStage,
      streak: 0,
      lastActiveDate: "",

      // Tips
      currentTip: null,
      tipDismissedAt: 0,

      // Inline comments
      pendingComment: null,
      commentDismissedAt: 0,

      // Achievements
      achievements: [],

      // Evolution flash
      isEvolving: false,

      hatch: () =>
        set({
          hatched: true,
          name: "BMO",
          species: "bmo",
          personality: "BLEE BLOP! I'm BMO — I play games and help you code!",
          mood: "happy",
          hatchedAt: Date.now(),
          lastReaction: "*hatches and looks around with big pixel eyes*",
          xp: 0,
          level: 0,
          xpNext: 10,
          evolutionStage: 0 as EvolutionStage,
          streak: 1,
          lastActiveDate: new Date().toISOString().slice(0, 10),
        }),

      pet: () => {
        const reaction = pickRandom(PET_REACTIONS);
        set((s) => ({
          lastPetted: Date.now(),
          totalPets: s.totalPets + 1,
          mood: "happy",
          lastReaction: reaction,
        }));
        // Award XP locally + backend
        get().awardXp("pet");
        return reaction;
      },

      poke: () => {
        const state = get();
        // Pick a joke from current stage or lower
        const stageJokes = [
          ...(STAGE_JOKES[0] ?? []),
          ...(state.evolutionStage >= 1 ? STAGE_JOKES[1] ?? [] : []),
          ...(state.evolutionStage >= 2 ? STAGE_JOKES[2] ?? [] : []),
          ...(state.evolutionStage >= 3 ? STAGE_JOKES[3] ?? [] : []),
          ...(state.evolutionStage >= 4 ? STAGE_JOKES[4] ?? [] : []),
        ];
        const joke = pickRandom(stageJokes);
        set({ lastReaction: `*clears throat* ${joke}`, mood: "happy" });
        return joke;
      },

      setMood: (mood) => set({ mood }),

      mute: () => set({ muted: true }),
      unmute: () => set({ muted: false }),

      react: (event: string) => {
        const state = get();
        if (state.muted || !state.hatched) return null;
        const pool = REACTIONS[event];
        if (!pool) return null;
        const reaction = pickRandom(pool);
        set({ lastReaction: reaction, mood: event === "error" ? "curious" : "excited" });
        // Award XP for chat events (not redundant with pet)
        if (event !== "pet") {
          get().awardXp(event);
        }
        return reaction;
      },

      reset: () =>
        set({
          hatched: false,
          name: "",
          species: "bmo",
          personality: "",
          mood: "idle",
          muted: false,
          lastPetted: 0,
          totalPets: 0,
          hatchedAt: 0,
          lastReaction: null,
          xp: 0,
          level: 0,
          xpNext: 10,
          evolutionStage: 0 as EvolutionStage,
          streak: 0,
          lastActiveDate: "",
          currentTip: null,
          tipDismissedAt: 0,
          pendingComment: null,
          commentDismissedAt: 0,
          isEvolving: false,
          achievements: [],
        }),

      awardXp: (event: string) => {
        const XP_MAP: Record<string, number> = {
          message_sent: 2,
          response_received: 1,
          task_completed: 10,
          error_resolved: 8,
          tool_use: 3,
          daily_login: 15,
          pet: 1,
          poke: 0,
        };
        const gain = XP_MAP[event] ?? 1;
        set((s) => {
          const newXp = s.xp + gain;
          const newLevel = levelForXp(newXp);
          const leveledUp = newLevel > s.level;
          const evoStage = evolutionStageForLevel(newLevel) as EvolutionStage;
          const evolved = evoStage > s.evolutionStage;

          // Stage-gated observation injection
          let pendingComment: string | null = s.pendingComment;
          if (leveledUp || evolved) {
            const pool = STAGE_OBSERVATIONS[evoStage] ?? STAGE_OBSERVATIONS[0];
            pendingComment = pickRandom(pool);
          }

          return {
            xp: newXp,
            level: newLevel,
            xpNext: xpForNextLevel(newLevel),
            evolutionStage: evoStage,
            isEvolving: evolved,
            pendingComment,
            ...(leveledUp ? { lastReaction: pickRandom(evolved ? REACTIONS.evolution : REACTIONS.level_up), mood: "excited" as BuddyMood } : {}),
          };
        });
        // Stop evolving flag after brief delay
        if (typeof window !== "undefined") {
          setTimeout(() => {
            const s = get();
            if (s.isEvolving) set({ isEvolving: false });
          }, 2000);
        }
        // Sync to backend (fire-and-forget)
        _backendXp(event);
      },

      setTip: (tip) => set({ currentTip: tip }),

      dismissTip: () => set({ currentTip: null, tipDismissedAt: Date.now() }),

      setComment: (comment) => set({ pendingComment: comment }),

      dismissComment: () => set({ pendingComment: null, commentDismissedAt: Date.now() }),

      syncFromBackend: (data) =>
        set((s) => ({
          ...s,
          ...(data.xp !== undefined ? { xp: data.xp } : {}),
          ...(data.level !== undefined ? { level: data.level } : {}),
          ...(data.evolutionStage !== undefined ? { evolutionStage: data.evolutionStage as EvolutionStage } : {}),
          ...(data.streak !== undefined ? { streak: data.streak } : {}),
          ...(data.achievements ? { achievements: data.achievements } : {}),
        })),
    }),
    {
      name: "memex-buddy",
      version: 2,
      migrate: (state: unknown, version: number) => {
        const s = state as Record<string, unknown>;
        if (version < 2) {
          // Migrate existing buddy to BMO
          return { ...s, species: "bmo" as BuddySpecies, name: "BMO", personality: "BLEE BLOP! I'm BMO — I play games and help you code!" };
        }
        return s;
      },
    }
  )
);
