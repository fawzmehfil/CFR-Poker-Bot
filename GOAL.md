You are upgrading the frontend UX/UI of the existing CFR-Poker-Bot Texas Hold’em interface.

The current frontend works functionally, but it feels static, instantaneous, flat, and prototype-like. The goal is to transform it into a polished, cinematic, highly responsive poker experience while keeping the UI clean, modern, readable, and professional.

This is NOT a redesign into a cluttered casino UI.
Avoid:
- tacky neon overload
- excessive glow spam
- visual chaos
- fake gambling aesthetics
- bloated dashboards

Target aesthetic:
- modern
- cinematic
- premium
- smooth
- restrained
- Apple/Arc/Linear/Riot-client quality
- subtle motion-heavy polish
- high responsiveness
- dark elegant poker table atmosphere

The UX should feel:
- tactile
- alive
- satisfying
- smooth
- deliberate
- immersive

The user should immediately feel:
“this is a serious poker engine.”

==================================================
PRIMARY UX/UI GOALS
==================================================

1. ADD REAL MOTION + GAME FEEL
The current UI updates instantly with no transitions.

Add:
- smooth card dealing animations
- flop/turn/river reveal animations
- chip movement animations
- stack count transitions
- button hover/press feedback
- fade/slide transitions
- smooth state transitions
- subtle motion between streets
- pot growth animation
- showdown reveal timing
- action timing pacing

The game should breathe slightly.
Do NOT instantly snap every state update.

Examples:
- opponent acts -> slight pause
- chips animate to pot
- board cards reveal sequentially
- showdown pauses before reveal

==================================================
2. IMPROVE TABLE PRESENTATION
==================================================

Upgrade:
- table gradients
- felt texture subtlety
- lighting
- depth
- shadows
- layering
- chip presentation
- card placement
- spacing
- proportions

Requirements:
- cleaner geometry
- stronger visual hierarchy
- more premium visual depth
- subtle ambient glow around table
- realistic but restrained shadows
- better spacing around center action area

The table should feel:
- cinematic
- premium
- focused

NOT:
- cluttered
- cartoonish
- fake casino

==================================================
3. CARD DESIGN IMPROVEMENTS
==================================================

Upgrade:
- card shadows
- card depth
- card transitions
- reveal animations
- subtle tilt/parallax
- stack overlap positioning

Requirements:
- cards should feel physical
- clean premium styling
- slightly animated hover on player cards
- smooth reveal timing
- smooth showdown reveals

Add:
- sequential board reveals
- subtle flip animations
- smoother hidden-card styling

==================================================
4. ACTION FLOW IMPROVEMENTS
==================================================

The game flow currently feels too immediate.

Improve:
- action pacing
- action readability
- turn indication
- opponent thinking state
- feedback timing

Add:
- “Bot thinking...” state
- short configurable action delay
- active-player emphasis
- smoother street transitions
- temporary action banners:
  - CALL
  - RAISE
  - FOLD
  - ALL-IN

These should animate in/out cleanly.

==================================================
5. BUTTON + INPUT UX
==================================================

Upgrade controls:
- hover feedback
- press feedback
- subtle scaling
- cleaner gradients
- disabled states
- active states

Improve:
- raise sizing UX
- betting controls
- spacing
- responsiveness

Buttons should feel:
- tactile
- responsive
- satisfying

==================================================
6. IMPROVE INFORMATION HIERARCHY
==================================================

Make the interface easier to parse instantly.

Improve:
- pot prominence
- current street visibility
- active player visibility
- stack readability
- action history readability
- spacing between sections

The eye should naturally flow:
table -> pot -> action -> controls.

==================================================
7. ACTION HISTORY REDESIGN
==================================================

Current action history feels like debug text.

Redesign it into:
- clean event feed
- readable poker timeline
- street separators
- action color coding
- subtle animations

Example:
[PREFLOP]
You call 1
Bot raises to 4
You call

[FLOP]
Bot checks
You bet 6

==================================================
8. SHOWDOWN EXPERIENCE
==================================================

Showdowns should feel dramatic.

Add:
- delayed reveal pacing
- winner highlight
- chip push animation
- winning hand text
- smooth stack updates

Examples:
- “Pair of Queens”
- “Straight”
- “Ace High”

==================================================
9. RESPONSIVENESS + POLISH
==================================================

Improve:
- scaling
- spacing
- responsive layouts
- animation smoothness
- visual consistency

Requirements:
- no janky layout shifts
- no oversized UI
- no overlapping controls
- preserve readability on smaller screens

==================================================
10. PERFORMANCE
==================================================

Animations must remain smooth.

Requirements:
- avoid excessive re-renders
- avoid animation spam
- avoid laggy transitions
- preserve responsiveness

Target:
- smooth 60fps feel
- fast interaction responsiveness

==================================================
11. TECHNICAL REQUIREMENTS
==================================================

- Keep architecture clean.
- Avoid giant monolithic components.
- Use reusable UI primitives where appropriate.
- Use clean animation abstractions.
- Preserve current game logic.
- Do not break existing functionality.

If appropriate:
- use Framer Motion
- improve component structure
- improve state transition handling

==================================================
12. SUCCESS CRITERIA
==================================================

The phase is NOT complete unless:

- frontend still functions correctly
- existing gameplay still works
- animations are visibly present
- action flow feels smoother
- showdown pacing feels cinematic
- UI feels significantly more premium
- no major responsiveness regressions
- no visual clutter introduced
- no broken game states
- frontend build passes
- screenshots/gifs can be captured that look impressive

==================================================
13. REQUIRED OUTPUTS
==================================================

Generate:
- updated frontend UI
- improved animations
- improved action history
- improved table presentation
- updated styling system if needed

Also:
- update README screenshots if appropriate
- document major frontend improvements
- summarize UX improvements made

==================================================
14. IMPORTANT DESIGN DIRECTION
==================================================

The target is:
“professional poker software with cinematic polish.”

NOT:
- online gambling website
- neon cyberpunk overload
- arcade game
- cartoon poker app

Think:
- premium
- restrained
- smooth
- immersive
- modern
- elegant
- high-end desktop software