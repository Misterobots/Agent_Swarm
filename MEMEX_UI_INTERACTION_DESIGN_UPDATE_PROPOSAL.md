# Memex UI, Interaction, and Design Update Proposal

## 1) Objective

Deliver a full redesign proposal for Memex that is:

- Modern, professional, and visually impressive
- Customizable, flexible, and fun for varied user types
- Technically efficient, avoiding unnecessary resource load in the new codebase

## 2) Current-State Snapshot (Evidence-Based)

Observed in codebase:

- Multi-workspace product scope exists already (`/chat`, `/media`, `/palace`, `/monitoring`, `/training`, `/settings`) in [ui/src/lib/config/navigation.ts](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/ui/src/lib/config/navigation.ts).
- Tokenized theme system already exists, including Memex and LCARS variants, with extensive CSS variables in [ui/src/app/globals.css](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/ui/src/app/globals.css).
- Desktop + mobile shell patterns already exist in [ui/src/components/layout/app-shell.tsx](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/ui/src/components/layout/app-shell.tsx) and [ui/src/components/layout/sidebar.tsx](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/ui/src/components/layout/sidebar.tsx).
- Real-time, tool-rich chat and streaming behavior exists in [ui/src/components/chat/chat-view.tsx](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/ui/src/components/chat/chat-view.tsx).
- High-fidelity spatial experience exists in Palace view in [ui/src/components/palace/palace-viewer.tsx](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/ui/src/components/palace/palace-viewer.tsx).
- Screenshots confirm broad UI footprint: [docs/screenshots](C:/Users/Compliance/Documents/Codex/2026-05-15/enable-goals-please/Agent_Swarm-main/docs/screenshots).

Conclusion: Memex already has strong breadth; the opportunity is coherence, personalization depth, and performance discipline across this breadth.

## 3) Design Direction: "Adaptive Mission Interface"

Core concept:

- A premium "mission console" visual language with calmer defaults and optional expressive overlays.
- One consistent spatial system across all modules: Chat, Media, Palace, Ops, Governance.
- Personality without clutter: visual richness appears progressively based on context, device class, and user preference.

Visual principles:

- High signal-to-noise layouts with intentional density controls
- Distinctive typography pair (technical + editorial) with strict hierarchy
- Layered surfaces with restrained motion and depth
- Color roles driven by semantics (status, trust, urgency), not page-specific hacks

## 4) Full UI Proposal

### 4.1 Global Information Architecture

- Keep current top-level route model, but formalize 3 user lanes:
- Create mode: Chat, Media, Art Studio, Voice
- Operate mode: Mission Control, Monitoring, Training, Governance
- Configure mode: Settings, Docs, Team/Provider controls

Add "Context Rail" pattern:

- Right-side optional rail showing contextual panels (agent roster, traces, memory links, file refs, run status)
- Shared component for all major surfaces to avoid custom one-off drawers

### 4.2 Shell and Navigation

- Introduce unified shell primitives:
- `ShellHeader` (title, context actions, status chips)
- `ShellSidebar` (nav + quick filters)
- `ShellRail` (context panel)
- `ShellCanvas` (main content zone)

Navigation upgrades:

- Persistent quick-switch (`Ctrl/Cmd+K`) for routes, recent chats, tools, and memory nodes
- Collapsible grouped nav with "recently used" pinning
- Role-aware nav presets (builder/operator/admin)

### 4.3 Design System 2.0

Token layers:

- `base` (color, type, spacing, radius, elevation)
- `semantic` (success/warn/error/info/attention/trust)
- `component` (button/input/panel/table/message)
- `experience` (chat, palace, ops, media overlays)

Component standardization:

- Normalize cards, data tables, form controls, badges, and empty states
- Shared interaction states (hover/focus/pressed/loading/disabled)
- Shared animation curves and durations

Customization:

- Theme packs (Minimal, Executive, Neon Grid, LCARS Classic)
- Density presets (Comfortable, Compact, Dense)
- Motion presets (Full, Reduced, None)
- Workspace-specific saved layouts (per route family)

### 4.4 Module-by-Module UX Upgrades

Chat:

- Split-pane option: conversation + live artifacts/trace panel
- Turn timeline markers for long sessions
- Progressive "reasoning visibility" controls (brief/normal/deep)

Media/Art:

- Generation job queue with state chips, ETA hints, and retry hooks
- Unified preview container for image/video/audio/3D outputs
- Compare mode for prompt variant outputs

Palace:

- Keep immersive mode but add "Focus Mode" (low effects, high legibility)
- Mini-map and breadcrumb memory traversal
- Quick-jump search over wings/halls/rooms

Monitoring/Ops:

- Shared metric card grammar and anomaly highlighting
- Sticky incident ribbon with guided triage workflow
- Cross-link traces to chat discussions and runbooks

Settings/Governance:

- Wizarded setup for providers and auth
- Policy health dashboard with actionable warnings
- Audit readability upgrades (diff-focused, timeline-first)

## 5) Interaction Model Proposal

Primary interaction patterns:

- Command-first: universal command palette + typed intents
- Contextual action bars: show only task-relevant controls
- Progressive disclosure: hide advanced controls until needed
- Keyboard parity for expert flows across chat/dev/ops surfaces

State and feedback patterns:

- Uniform async states (`idle/loading/streaming/success/error/retrying`)
- Non-blocking status toasts + persistent job center
- Inline recovery options near failing components

Micro-interactions:

- Staggered content reveal only at route entry
- Lightweight skeletons over spinners for data surfaces
- Precision haptics style via visual pulses (no flashy loops)

## 6) Technical Implementation Plan (Performance-Safe)

### 6.1 Resource Budget Policy

Set hard budgets per route group:

- Initial JS per route target: <= 220 KB gzipped for standard routes
- Heavy experiential routes (Palace/Studio): lazy chunks loaded only on demand
- CSS budget with token-first approach and no duplicate theme payloads

### 6.2 Code-Splitting and Lazy Loading

- Route-level lazy boundaries for heavy modules (`three`, Monaco, xterm, postprocessing)
- Dynamic import optional panels (trace drawer, previews, advanced settings)
- Defer non-critical widgets (buddy, decorative effects) until idle

### 6.3 Rendering Strategy

- Use server components for static data frames where possible
- Client islands for interactive units only
- Memoize expensive render lists and use virtualization for long chat/history tables
- Throttle high-frequency store updates and SSE paint loops

### 6.4 State and Data Efficiency

- Segment Zustand stores by domain and subscribe narrowly
- Introduce selector-level memoization for high-churn views
- Cache policy by data class:
- Fast polling for health cards
- Event-driven updates for chat/streaming
- Stale-while-revalidate for docs/settings metadata

### 6.5 Motion and Visual Effects Guardrails

- Respect `prefers-reduced-motion` globally
- Auto-disable costly effects on low-power/mobile profiles
- Palace visual tiers:
- Tier 0: static gradients
- Tier 1: lightweight CSS depth
- Tier 2: full immersive scene

### 6.6 Instrumentation and Quality Gates

- Add Web Vitals + custom metrics per route:
- TTI, INP, CLS, memory footprint, dropped frame ratio
- CI gate: block merges that regress budgets above threshold
- Add performance snapshots before/after each phase

## 7) Rollout Plan

Phase 0 (1-2 weeks):

- Design system tokens v2
- Shell primitives
- Performance budget framework + telemetry

Phase 1 (2-3 weeks):

- Chat + Sidebar modernization
- Command palette
- Context rail

Phase 2 (2-3 weeks):

- Media + Monitoring harmonization
- Job center and unified async states

Phase 3 (2-4 weeks):

- Palace focus-mode + tiered effects
- Governance/settings workflow overhaul

Phase 4 (1-2 weeks):

- Polish, accessibility pass, performance hardening, documentation

## 8) Success Criteria

Design and UX outcomes:

- Clear visual consistency across all modules
- Personalized experience without complexity overload
- Faster task completion for both novice and power users

Performance and technical outcomes:

- No route regresses beyond agreed JS/CSS/memory budgets
- Lower render churn and improved responsiveness during streaming
- Controlled heavy-module loading only when explicitly needed

## 9) Recommended Immediate Next Deliverables

1. High-fidelity UI blueprint for 6 key screens (`chat`, `media`, `palace`, `monitoring`, `settings`, `mission-control`)
2. Token schema and component spec (buttons, cards, tables, message rows, rails)
3. Route-by-route performance budget matrix and instrumentation checklist
4. Implementation backlog with ticket slicing by phase
