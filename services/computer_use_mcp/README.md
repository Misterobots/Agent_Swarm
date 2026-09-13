# computer_use_mcp

Screenshot-grounded desktop control, exposed to Qwen Code (or any MCP client) over stdio.

**Runs on the host, not in Docker** — it needs the real desktop.

## How it works

```
Qwen Code --(MCP stdio)--> computer_use --(HTTP)--> code_gateway:8010 --> Ollama --> qwen3.8:27b
                                |
                          Windows desktop: ImageGrab capture + user32 input
```

The server calls the vision model **itself** and returns **text**, rather than handing an image
block back to the CLI. That is deliberate:

- It works regardless of whether the host CLI forwards MCP image content to its model.
- A screenshot costs ~1300 prompt tokens. Feeding one into the coding session every step would
  consume the context budget of the conversation doing the work. Grounding happens out-of-band;
  only coordinates come back.

## Tools

| tool | clicks? | purpose |
|---|---|---|
| `screen_info()` | no | screen dimensions, dry-run state, threshold |
| `locate_on_screen(target)` | **no** | find an element, return coordinates + confidence |
| `click(x, y, button, double)` | yes | click explicit coordinates |
| `find_and_click(target)` | conditionally | locate, then click **only above the confidence threshold** |
| `type_text(text)` | — | unicode keystrokes at current focus |

`find_and_click` returns `needs_human: true` plus an `instruct_user` string when confidence is
below `COMPUTER_USE_MIN_CONFIDENCE` — the deliberate hand-off rather than a guess at someone's
desktop.

## Config

| env | default | |
|---|---|---|
| `COMPUTER_USE_GATEWAY` | `http://localhost:8010/v1/chat/completions` | code_gateway |
| `COMPUTER_USE_MODEL` | `qwen3.8:27b` | must have the `vision` capability |
| `COMPUTER_USE_MIN_CONFIDENCE` | `0.7` | below this, hand off to the human |
| `COMPUTER_USE_DRY_RUN` | `0` | `1` = report intended actions, perform none |
| `COMPUTER_USE_MAX_PIXELS` | `1400000` | downscale cap — see below |
| `COMPUTER_USE_LOG` | `~/.qwen/computer_use.log` | every action, JSONL |

## Measured on this hardware (2026-09-13)

Grounding on a 1440x900 UI screenshot, three targets, all landing inside their element:

| target | predicted | truth | error |
|---|---|---|---|
| "Run History" tab | (418, 22) | (417, 20) | 2 px |
| "Model Training" card | (840, 258) | (847, 267) | 11 px |
| "Hatch a Companion" button | (122, 805) | (127, 806) | 5 px |

Live 3440x1440 desktop, "taskbar clock": found at (3358, 1401), confidence 0.95, **49 s**.

### Two gotchas worth knowing

**Per-monitor DPI awareness is set at import.** Without it Windows reports the screenshot at
physical resolution while `SetCursorPos` works in scaled units, so every click misses by the
display's scaling factor.

**`MAX_PIXELS` is well under the model's 4194304 limit.** A full-size 3440x1440 grab crashed the
runner: vision tokens land on top of a KV slot that may already be near the window limit, and
llama.cpp's context checkpoints (~617 MiB each, up to 32) are not budgeted against VRAM. At
~1.4 MP a 3440-wide screen still maps to ~1800 px — enough for accurate grounding — at a third
of the token cost.

**Latency is the real constraint.** ~50 s per perception step suits one deliberate action, not a
tight screenshot→decide→act loop.

## Install

```
pip install mcp pillow
```

Then register it in `~/.qwen/settings.json` under `mcpServers` (see the entry this repo ships).
