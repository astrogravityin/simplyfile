<!-- standard-pointer: DomainTemplate/docs/dt-qc_gate-v1_0.md -->
# QC gate (the check, when done) - kept in ONE place

This file is a pointer, not a copy (owner 2026-11-23). The standard lives only in **DomainTemplate/docs/dt-qc_gate-v1_0.md**.

- On the owner's computer: open `D:\DomainTemplate\docs$f` (the folder beside this repo).
- Anywhere else (VPS, build computer): `gh api repos/astrogravityin/domaintemplate/contents/docs/dt-qc_gate-v1_0.md -H "Accept: application/vnd.github.raw"`

Change the standard only there. `python -m core.qualitycheck` follows this pointer, checks the QA/QC numbers, and fails if a full copy comes back here.
