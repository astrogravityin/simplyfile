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

Then the report: Status table, numbered Pending table (with whom), Next paragraph - sub-sessions included.

A report without the QC table is not finished (owner 2026-11-16): the owner reads a missing table as "the rules were not
followed". That holds for every sub-session too.
