import { create } from "zustand";
import { persist } from "zustand/middleware";

export type BuddySpecies =
  | "pixel-sprite"
  | "byte-bat"
  | "data-fox"
  | "circuit-cat"
  | "logic-lizard"
  | "hash-hamster";

export type BuddyMood = "happy" | "curious" | "sleepy" | "excited" | "idle";

export type EvolutionStage = 0 | 1 | 2 | 3;

export interface BuddyAchievement {
  id: string;
  name: string;
  description?: string;
  earned_at?: string;
}

const SPECIES_LIST: BuddySpecies[] = [
  "pixel-sprite", "byte-bat", "data-fox", "circuit-cat", "logic-lizard", "hash-hamster",
];

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

  // Achievements
  achievements: BuddyAchievement[];

  // Actions
  hatch: () => void;
  pet: () => string;
  setMood: (mood: BuddyMood) => void;
  mute: () => void;
  unmute: () => void;
  react: (event: string) => string | null;
  reset: () => void;
  awardXp: (event: string) => void;
  setTip: (tip: string | null) => void;
  dismissTip: () => void;
  syncFromBackend: (data: Partial<BuddyState>) => void;
}

const REACTIONS: Record<string, string[]> = {
  message_sent: ["*perks up*", "*watches intently*", "*tilts head*"],
  response_received: ["*nods approvingly*", "*bounces*", "*chirps*"],
  error: ["*hides behind console*", "*flinches*", "*whimpers softly*"],
  compact: ["*stretches*", "*yawns*", "*blinks*"],
  tool_use: ["*leans forward*", "*eyes widen*", "*scribbles notes*"],
  level_up: ["*glows brightly!*", "*does a victory dance!*", "*evolves with sparkles!*"],
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
  if (level >= 15) return 3;
  if (level >= 10) return 2;
  if (level >= 5) return 1;
  return 0;
}

/** Fire-and-forget XP award to backend */
async function _backendXp(event: string) {
  try {
    const resp = await fetch("/api/v1/buddy/xp", {
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
      species: "pixel-sprite",
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

      // Achievements
      achievements: [],

      hatch: () =>
        set({
          hatched: true,
          name: pickRandom(NAMES),
          species: pickRandom(SPECIES_LIST),
          personality: pickRandom(PERSONALITIES),
          mood: "happy",
          hatchedAt: Date.now(),
          lastReaction: "*hatches and looks around curiously*",
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
          species: "pixel-sprite",
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
        };
        const gain = XP_MAP[event] ?? 1;
        set((s) => {
          const newXp = s.xp + gain;
          const newLevel = levelForXp(newXp);
          const leveledUp = newLevel > s.level;
          const evoStage = evolutionStageForLevel(newLevel);
          return {
            xp: newXp,
            level: newLevel,
            xpNext: xpForNextLevel(newLevel),
            evolutionStage: evoStage,
            ...(leveledUp ? { lastReaction: pickRandom(REACTIONS.level_up), mood: "excited" as BuddyMood } : {}),
          };
        });
        // Sync to backend (fire-and-forget)
        _backendXp(event);
      },

      setTip: (tip) => set({ currentTip: tip }),

      dismissTip: () => set({ currentTip: null, tipDismissedAt: Date.now() }),

      syncFromBackend: (data) =>
        set((s) => ({
          ...s,
          ...(data.xp !== undefined ? { xp: data.xp } : {}),
          ...(data.level !== undefined ? { level: data.level } : {}),
          ...(data.streak !== undefined ? { streak: data.streak } : {}),
          ...(data.achievements ? { achievements: data.achievements } : {}),
        })),
    }),
    { name: "hive-buddy" }
  )
);
