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

  hatch: () => void;
  pet: () => string;
  setMood: (mood: BuddyMood) => void;
  mute: () => void;
  unmute: () => void;
  react: (event: string) => string | null;
  reset: () => void;
}

const REACTIONS: Record<string, string[]> = {
  message_sent: ["*perks up*", "*watches intently*", "*tilts head*"],
  response_received: ["*nods approvingly*", "*bounces*", "*chirps*"],
  error: ["*hides behind console*", "*flinches*", "*whimpers softly*"],
  compact: ["*stretches*", "*yawns*", "*blinks*"],
  tool_use: ["*leans forward*", "*eyes widen*", "*scribbles notes*"],
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

      hatch: () =>
        set({
          hatched: true,
          name: pickRandom(NAMES),
          species: pickRandom(SPECIES_LIST),
          personality: pickRandom(PERSONALITIES),
          mood: "happy",
          hatchedAt: Date.now(),
          lastReaction: "*hatches and looks around curiously*",
        }),

      pet: () => {
        const reaction = pickRandom(PET_REACTIONS);
        set((s) => ({
          lastPetted: Date.now(),
          totalPets: s.totalPets + 1,
          mood: "happy",
          lastReaction: reaction,
        }));
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
        }),
    }),
    { name: "hive-buddy" }
  )
);
