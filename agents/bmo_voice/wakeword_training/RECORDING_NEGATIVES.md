# Recording household hard-negatives (the "stop false-triggering" fix)

The shipped "Hey Friday" model already trained on synthetic + real **positives** and still
false-fires on ~40% of turns. The reason is **negatives**: the pre-built generic negative sets
(`speech`, `dinner_party`, `no_speech`) have never heard *your* TV, *your* voices, or *your* rooms,
so the model doesn't know that your household's ambient audio is **not** the wake word.

This guide is the Phase-A fix: record that ambient audio and feed it back as hard-negatives.

---

## What to record

The exact stuff that's been falsely waking her:
- The **TV / shows / movies** you actually watch, at normal volume.
- **Normal conversation** between household members.
- **Music**, kitchen noise, kids playing, background chatter.

**Record where the Mini physically sits** — a phone laid on the same shelf/counter is perfect. The
value is the *real distance + room reverb*, not clean close-mic audio.

### The one hard rule
> **Do NOT say "Hey Friday" during these recordings.** Every slice becomes a "this is NOT the wake
> word" example — a real wake phrase in here would teach the model to *ignore* itself.

### How much
- **Training:** ~20–40 minutes total. More and more varied = better. Cover the rooms/scenarios where
  false wakes happen most.
- **Eval (held-out):** a **separate** ~5–10 minutes, recorded on a different occasion — used only to
  measure the false-accept rate before/after, never trained on.

---

## Where to put it

Drop the raw recordings (any format — m4a/mp3/wav all fine) into:

| Purpose | Folder |
|---|---|
| Training negatives | `data/household_negatives_raw/` |
| Held-out eval | `data/eval_negatives_raw/` |

Both are under the **gitignored** `data/` volume, so **recordings never leave this machine** and are
never committed.

---

## Privacy

These are your private rooms. The recordings **stay local** (gitignored, never pushed, never sent to
any cloud). If capturing conversation is uncomfortable, lean on **TV / media / music** — that alone is
a strong negative set. (The most targeted negatives would be the *actual* false-trigger clips, but
capturing those on-device is Stage B; this Phase-A ambient approach needs no device changes.)

---

## Then hand back to the pipeline

Once the recordings are in place, the slicer + training config are already wired:

```bash
# 1. slice raw ambient into dense 1.5s clips
./slice_negatives.sh data/household_negatives_raw data/household_negatives

# 2. uncomment the `household_negative_features` block in training_parameters.yaml
#    (extract_features.py already featurizes household_negatives/ when present)

# 3. retrain (delete stale *_augmented_features/ dirs first if you changed clips), then eval + flash
```

Just tell me when the recordings are dropped in and I'll run steps 1–3 and measure the before/after.
