# SimplyFile - project rules

Read and follow these before every change.

## Every change - the owner's standard (HARD, AstroStage + every FY portal, 2026-10-30)

Every feature, screen or fix is finished only when ALL of these are true. Answer each one in the closing report
from evidence (a test run, a screenshot read back), never from memory.

1. **Reuse first - never reinvent the wheel.** Before building, look for an existing component, control, op or chip.
   Fits fully -> use it. Fits partly -> make it generic so both uses share it. Nothing fits -> only then build new.
2. **Chips and ops.** Every rule, value, word, default and threshold lives in a chip or an op - nothing hardcoded.
3. **Professional narration.** Words on screen, in Guide me and in tours are compact, elegant and professional,
   with a beautiful SVG where a picture helps.
4. **Guide me** updated for every changed screen.
5. **Tour Video** re-rendered for every changed screen (sound and picture checked).
6. **UI verified** on laptop, tablet and phone, in light and dark: alignment, nothing cut off, easy to use.
7. **Slow work shows a UEW.** Any step that can take more than ~1 s (first page load, a big chart, a backend
   call, a build, an AI call) shows the progress window at once with what is happening and the time gone - plan it
   while building, and check it exists while testing (a white screen with no word is a fail).
8. **Tested** on laptop, tablet and phone - the real feature end to end, every role, not just that the page opens.
   Run the project's tests yourself; a test written but not run is not done.
9. **AI agents** - scope identified for each changed feature (free options first) and built on the standard
   agent framework, or "no (why)".
10. **MCP server** - scope identified for each changed feature and built on the standard MCP framework, or "no (why)".
11. **Status** - end with: what is done, the pending list, and what is next.

Skills for every change: **development** = `.agents/skills/module-builder/SKILL.md` section 0 (AstroStage modules) or
`.agents/skills/portal-builder/SKILL.md` (portals); **testing** = `.agents/skills/screen-test/SKILL.md`.
