"""Route-guard ratchet (2026-11-18, gap audit C1-7): every /api route carries a guard dependency or is public on purpose.

A guard = any FastAPI dependency on the route, its router or its include (access.screen, auth.signed_in, auth.owner, a firm
gate, a site key - every Depends in this framework is one). Public routes are chip security.public_routes `routes`; routes that
still check sign-in only inside their body count against its `unguarded_ceiling`, which only falls.
ponytail: "has a dependency" is the test, not "the dependency refuses a stranger" - the signed-out walk (C1-8) proves that."""
from __future__ import annotations

from core import engine


def _flat(routes, deps: tuple = ()):
    for r in routes:
        inc = getattr(r, "include_context", None)
        if inc is not None:                      # FastAPI >= 0.140 keeps an included router as one entry
            yield from _flat(inc.included_router.routes, deps + tuple(getattr(inc, "dependencies", None) or ()))
        elif hasattr(r, "dependant"):
            yield r, deps


def unguarded(app) -> list[str]:
    """'METHOD path' of every /api route with no guard that the chip does not list as public."""
    public = set(engine.run("security.public_routes")["routes"])
    out = []
    for r, deps in _flat(app.routes):
        if not r.path.startswith("/api") or deps or r.dependant.dependencies:
            continue
        out += [k for k in (f"{m} {r.path}" for m in sorted(r.methods - {"HEAD", "OPTIONS"})) if k not in public]
    return sorted(out)


def check(app) -> None:
    got, cap = unguarded(app), int(engine.run("security.public_routes")["unguarded_ceiling"])
    assert len(got) <= cap, (f"{len(got)} /api routes have no guard (ceiling {cap}) - add Depends(access.screen(...)) / "
                             f"auth.signed_in, or list a truly public one in chip security.public_routes: {got}")
    tail = f" - lower unguarded_ceiling to {len(got)}" if len(got) < cap else ""
    print(f"  route guards: every /api route guarded or public, {len(got)} still checked in the body (ceiling {cap}){tail} OK")


if __name__ == "__main__":
    from fastapi import APIRouter, Depends, FastAPI

    def guard() -> None:
        return None

    app_, sub = FastAPI(), APIRouter(dependencies=[Depends(guard)])
    app_.get("/api/bootstrap")(lambda: 1)                    # public by the chip
    app_.get("/api/mine", dependencies=[Depends(guard)])(lambda: 1)
    sub.get("/api/sub")(lambda: 1)                           # guarded by its router
    app_.include_router(sub)
    assert unguarded(app_) == [], unguarded(app_)
    app_.post("/api/open")(lambda: 1)                        # the bite: a new route with no guard
    assert unguarded(app_) == ["POST /api/open"], unguarded(app_)
    print("core.routeguard OK")
