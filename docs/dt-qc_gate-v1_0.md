# QC Gate - the checklist (confirm when building is done)

Owner 2026-11-15. Quality Control = the end-of-work gate: the [QA Standard](dt-qa_standard-v1_0.md) turned into checks
(white and black box). Confirm it for yourself and every sub-session. Every line needs evidence (a test run, a
screenshot read back, a diff), never memory. A line without evidence counts as FAIL.

| # | Check | Evidence required |
|---|---|---|
| QC-1 | Journey is seamless: step count, handovers removed, no dead ends | Walk-through of the flow, with steps counted |
| QC-2 | Narration compact, elegant and professional, with SVG where it helps | Screenshot of the text, read back |
| QC-3 | Every wait over 2 s shows the progress window | Name of each slow step, plus a screenshot of its window |
| QC-4 | Only standard components used | List of components used, plus any new one made generic |
| QC-5 | Reused before building | What was reused, what was made generic, what was new and why |
| QC-6 | No hardcoding | Diff read, with each typed value mapped to its chip or op |
| QC-7 | ACT met | Accuracy check, cost per run, time taken |
| QC-8 | Performance acceptable | Measured times, plus the plan for any slow step |
| QC-9 | Guide me updated | File changed, plus `python selfcheck.py` PASS |
| QC-10 | Tour script updated (video re-rendered until render-on-first-view ships) | Script diff, plus `python tools/make_tours.py` + `python selfcheck.py` PASS |
| QC-11 | UI verified on laptop, tablet and phone, in light and dark | Six screenshots per changed screen |
| QC-12 | Tested end to end, every role | Test run output, plus the role table |
| QC-13 | AI agent scope | Proposed (what), or no (why) |
| QC-14 | MCP scope | Built (tool name), or no (why) |
| QC-15 | Fixed bugs can't come back | Guard name, with proof it fails when the bug is reintroduced |
| QC-16 | DomainTemplate updated | File or commit in DomainTemplate |

## Size the gate to the change (owner 2026-11-16)

The table is always there; how much evidence each line needs depends on the size of the change. Decide the size first
and name it in the table's title row ("QC - size S").

- **S - no screen change** (a fix inside one function, config, chip value, docs, a guard): evidence only for QC-6 (diff
  read), QC-12 (tests run), QC-15 (if a bug was fixed) and QC-16. The other lines go in ONE row: `n/a (size S, no
  screen)`. No screenshots.
- **M - a change on screens that already exist**: every line. QC-11 = two screenshots per changed screen (laptop light,
  phone dark) at half scale; full scale only to read small text. Use all six only if the layout or theme code changed.
- **L - a new screen, module, flow or portal**: every line at full evidence. QC-11 = six screenshots per new screen.

When unsure, pick the bigger size. A line shown as n/a is not a pass: say in a few words why it doesn't apply.

Then the report: Status table, numbered Pending table (with whom), Next paragraph - sub-sessions included.

A report without the QC table is not finished (owner 2026-11-16): the owner reads a missing table as "the rules were not
followed". That holds for every sub-session too.
