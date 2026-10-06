"""Tax rules - Fetch, Compare, Apply (2026-10-06 owner: "what changed this year as compared to last year, and another button
to apply ... for all tax, individual and the CA portal").

SimplyFile's rule watch (boilerplate rulewatch.py): the yearly tax figures chip taxwatch.items lists, for a new AY or the live
one checked again, from official sources. compute.settings regimes_by_ay keeps past years' slabs (a target's `archive`); a due
date the department extended for the live year goes into close.dates extensions (a target's `extend`).
Who: the portal owner only. Words: chip ui.taxwatch.
"""
from __future__ import annotations

from rulewatch import Watch, next_period

W = Watch("taxwatch")
settings, say, items, live_value, draft = W.settings, W.say, W.items, W.live_value, W.draft
ai_choices, fetch, edit, compare, apply = W.ai_choices, W.fetch, W.edit, W.compare, W.apply
_ay_next = next_period


if __name__ == "__main__":  # ponytail: every figure and target resolves on the shipped chips
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    print("taxwatch self-check OK", W.check(), "figures")
