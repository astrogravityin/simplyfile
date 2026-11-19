# QA Standard - the stage (follow while building)

Owner 2026-11-15. Quality Assurance = the in-process standard. Follow it while building and you are assuring quality.
It applies to me and every sub-session, on top of the project's skills, prompts and framework.
The end-of-work check is [QC_GATE.md](dt-qc_gate-v1_0.md) - same numbers: QC-5 checks QA-5.

## A. The user's journey

1. **Seamless journey.** Every flow has as few steps and handovers as possible, with no dead ends and no question
   we could answer ourselves. People remember the pain, so leave none.
2. **Words and pictures.** On-screen text, Guide me and tours are compact, elegant and professional, with a clean
   SVG wherever a picture helps (skill `ui-standard`).
3. **Progress window.** Any step that can take over 2 s shows the standard progress window (UEW) at once, with
   what is happening and the time gone.
4. **One component set.** Use the universal standard components, the same within a portal and across every portal.

## B. How it is built

5. **Reuse first.** Use an existing component, op or chip if it fits fully. If it fits partly, make it generic so
   both uses share it. Build new only when nothing fits.
6. **Chips and ops, no hardcoding.** Every rule, value, word, default, threshold, address or name lives in a chip
   or an op (skill `ops-chips-first`).
7. **ACT:** highest Accuracy, lowest Cost, lowest Time. Free options come first.
8. **Performance.** Measure response times. If any screen or process is not fast, fix it now or record a plan to
   make it the best.

## C. Help on every screen

9. **Guide me** is updated for every changed screen (skill `guide-me-script`).
10. **Tour Video: update the script, not the video.** That means the Guide me steps plus the screen's row in
    `tours/<prefix>-<screen>.json`. Target: the video renders on first view with a progress window and is
    kept until the script or screen changes; only videos shared outside (marketing, demo cards, client links) are
    pre-rendered and checked for sound and picture.
    *Until render-on-first-view ships, `guide_drift` still fails `video_stale`, so re-render the changed screen's
    video as before.*

## D. Check as you go

11. **UI check after each UI piece.** Check laptop, tablet and phone in light and dark: alignment, nothing cut off,
    easy to use. Show a screenshot as evidence (skill `screen-test`).
12. **Real testing.** Test the full feature end to end on laptop, tablet and phone, for every role. Run the
    project's tests yourself.

## E. Extend

13. **AI agent scope** for each feature, free options first, built on the standard agent framework, or "no (why)".
14. **MCP server scope** for each feature, built on the standard MCP framework, or "no (why)".

## F. Learn

15. **Never the same mistake twice.** Each fix gets a guard that fails if the bug returns, a lesson in the skill and
    a memory.
16. **Carry it home.** Every new learning goes into the DomainTemplate skills, prompts and framework in the same
    change.

## G. Stay safe

17. **Security watch green before anything ships.** The weekly watch (agent `ag_security_watch`, `core/securitywatch.py`)
    checks every pinned package against osv.dev and re-runs the security walls; its row on the owner's bar is green, and
    `python selfcheck.py` (which holds the every-route wall) passes. A new advisory is fixed (raise the pin, lock again)
    before the change ships, never waived. Each week the sweep in skill `security-watch` files every new class as a gap
    with its guard.

## Report format (end of every reply that changed something)

1. **Status:** a table of what was done, where, and its state, including sub-sessions.
2. **Pending:** a numbered table of each item and who it is pending with, including sub-sessions.
3. **Next:** one paragraph, including sub-sessions.
