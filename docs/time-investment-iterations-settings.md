# Time Investment & Iterations Settings — Implementation Summary

## Overview

The **time investment and iterations settings** control the MarsRL (Solver → Verifier → Corrector) loop behavior in the Agent Swarm system. These settings allow users to adjust the quality-effort trade-off for agent responses.

## Location in UI

The settings are now available in the **Chat Settings Menu** (⚙️ gear icon in the chat interface):

1. Open any chat conversation
2. Click the **Settings** button (⚙️) in the bottom toolbar
3. Scroll to the **"Quality & Effort"** section
4. Adjust the sliders:
   - **Max Iterations**: Controls how many Solver/Corrector refinement rounds (0 = unlimited, default = 2)
   - **Max Time**: Controls maximum processing time in seconds (0 = unlimited)

## What Changed

### Frontend Changes

#### 1. Settings Store (`ui/src/lib/stores/settings-store.ts`)
Added two new state properties:
- `solvingMaxIter: number` — Default: 2
- `solvingMaxTime: number` — Default: 0 (unlimited)

#### 2. New Component: Quality Settings Panel (`ui/src/components/chat/quality-settings-panel.tsx`)
- Interactive sliders for both settings
- Real-time feedback on what each value means
- Visual indicators showing quality/speed trade-offs

#### 3. Chat Settings Menu (`ui/src/components/chat/chat-settings-menu.tsx`)
- Added "Quality & Effort" section with the new panel

#### 4. API Layer (`ui/src/lib/api/chat.ts`)
- Added `solvingMaxIter` and `solvingMaxTime` to `ChatStreamOptions` interface
- Added parameters to `sendChatStream` function
- Included in request body as `solving_max_iter` and `solving_max_time`

#### 5. Chat Hook (`ui/src/lib/hooks/use-chat-stream.ts`)
- Reads settings from store
- Passes them to the API call

### Backend Changes

#### 1. API Model (`agents/main.py`)
Added to `ChatRequest` class:
```python
solving_max_iter: Optional[int] = None  # MarsRL max iterations (0 = unlimited, overrides config)
solving_max_time: Optional[int] = None  # MarsRL max time in seconds (0 = unlimited, overrides config)
```

#### 2. Router (`agents/church.py`)
- Added parameters to `chat_swarm()` function signature
- Updated both `MarsRLLoop` instantiations to use user-provided values:
  ```python
  mars = MarsRLLoop(
      solver=solver,
      verifier=verifier,
      corrector=corrector,
      max_iter=solving_max_iter if solving_max_iter is not None else 2,
      max_time=solving_max_time if solving_max_time is not None else None,
      ...
  )
  ```

#### 3. Main API Endpoint (`agents/main.py`)
- Passes parameters from `ChatRequest` to `chat_swarm()`

## How It Works

### Iterations Setting
- **0**: Unlimited iterations — fastest response (single-pass)
- **1**: Single pass — quick but minimal refinement
- **2**: Default — balanced quality (Solver → Verifier → Corrector once)
- **3-5**: Higher quality — multiple refinement rounds
- **6-10**: Maximum quality — thorough refinement

### Time Setting
- **0**: No time limit — process until done or max iterations reached
- **30-60s**: Fast timeout — quick responses only
- **60-180s**: Moderate timeout — balanced
- **180-300s**: Extended timeout — complex tasks allowed

### Precedence
- User settings (from UI) override environment variables in `config.py`
- If not set in UI, falls back to:
  - `SOLVING_MAX_ITER` (default: 2)
  - `SOLVING_MAX_TIME` (default: 0)

## Environment Variables (Backend)

These are still available in `agents/config.py` for system-wide defaults:
```python
PLANNING_MAX_ITER = int(os.getenv("PLANNING_MAX_ITER", "0"))
PLANNING_MAX_TIME = int(os.getenv("PLANNING_MAX_TIME", "0"))
SOLVING_MAX_ITER = int(os.getenv("SOLVING_MAX_ITER", "2"))
SOLVING_MAX_TIME = int(os.getenv("SOLVING_MAX_TIME", "0"))
```

## Testing

To test the feature:
1. Start the UI development server
2. Open a chat conversation
3. Click Settings ⚙️
4. Scroll to "Quality & Effort"
5. Adjust the sliders
6. Send a message — the MarsRL loop will respect the new limits

## Files Modified

### Frontend (7 files)
1. `ui/src/lib/stores/settings-store.ts`
2. `ui/src/components/chat/quality-settings-panel.tsx` (NEW)
3. `ui/src/components/chat/chat-settings-menu.tsx`
4. `ui/src/lib/api/chat.ts`
5. `ui/src/lib/hooks/use-chat-stream.ts`

### Backend (2 files)
1. `agents/main.py`
2. `agents/church.py`

---

**Status**: ✅ Complete — Ready for testing
