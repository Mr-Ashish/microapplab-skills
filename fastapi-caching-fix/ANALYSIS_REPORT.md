# FastAPI Dependency + Caching Interaction: Analysis Report

> **Scope:** FastAPI `Depends()` combined with `functools.lru_cache` and custom in-memory caches  
> **Repo analyzed:** [fastapi/fastapi](https://github.com/fastapi/fastapi) @ latest main  
> **Risk level:** CRITICAL — cross-user data leaking under concurrent load

---

## 1. How FastAPI's Dependency Cache Actually Works (the safe part)

Before diagnosing what goes wrong, you must understand what FastAPI does **correctly** on its own.

### 1.1 Per-Request Dependency Cache

Every time a request hits an endpoint, FastAPI calls `solve_dependencies()` in `fastapi/routing.py:457`. Crucially, it does **not** pass a `dependency_cache` argument:

```python
# fastapi/routing.py:457-464
solved_result = await solve_dependencies(
    request=request,
    dependant=dependant,
    body=...,
    dependency_overrides_provider=...,
    async_exit_stack=async_exit_stack,
    embed_body_fields=embed_body_fields,
)
```

Inside `solve_dependencies()` at `fastapi/dependencies/utils.py:626-627`:

```python
if dependency_cache is None:
    dependency_cache = {}
```

**This means a brand-new empty dict is created for every request.** The cache only lives for the duration of one request's dependency resolution tree. This is safe.

### 1.2 What the Per-Request Cache Does

When the same dependency function appears multiple times in one request's tree (e.g., `get_db` used by both `get_current_user` and the endpoint itself), FastAPI uses the cache to avoid calling it twice **within that same request**:

```python
# fastapi/dependencies/utils.py:664-665
if sub_dependant.use_cache and sub_dependant.cache_key in dependency_cache:
    solved = dependency_cache[sub_dependant.cache_key]
```

The cache key is defined in `fastapi/dependencies/models.py:63-71`:

```python
@cached_property
def cache_key(self) -> DependencyCacheKey:
    return (
        self.call,           # The callable itself
        scopes_for_cache,    # OAuth scopes tuple
        self.computed_scope or "",
    )
```

**Key takeaway:** `Depends(use_cache=True)` (the default) is purely per-request deduplication. It cannot cause cross-request leaking on its own.

### 1.3 The `use_cache=False` Escape Hatch

```python
# fastapi/params.py:745-748
@dataclass(frozen=True)
class Depends:
    dependency: Callable[..., Any] | None = None
    use_cache: bool = True
    scope: Literal["function", "request"] | None = None
```

Setting `Depends(get_db, use_cache=False)` forces a fresh call even within one request. You rarely need this unless the same dependency must produce **different instances** within a single request.

---

## 2. The Three Root Causes of Your Bug

The problems you describe — stale data and cross-user leaking — do **not** come from FastAPI's `Depends` cache. They come from layering Python-level caching **on top of** the dependency system.

### Root Cause 1: `lru_cache` on Dependencies That Return Mutable Per-Request Objects

**This is the critical data-leaking bug.**

```python
from functools import lru_cache

@lru_cache()
def get_db():
    return SessionLocal()   # ← ONE session object, forever, for ALL requests
```

`lru_cache` is **process-global and permanent**. It caches by argument hash. Since `get_db()` takes no arguments, it returns the exact same `Session` object to every concurrent request.

**What goes wrong:**
- Request A starts a transaction, queries user A's data
- Request B (concurrent) gets the **same session**, sees user A's uncommitted dirty state
- Request A commits; Request B now has stale/wrong objects in its identity map
- Under load, SQLAlchemy's session is not thread-safe — undefined behavior

**Files you'd need to audit in your codebase:**
- Any file with `@lru_cache` decorating a function that returns a DB session, connection, or any mutable object
- Any file where `Depends(get_something)` and `get_something` is `@lru_cache`'d

### Root Cause 2: Global Mutable Dict Cache Without TTL or Copy Semantics

```python
_user_cache: dict[int, dict] = {}   # Module-level mutable dict

def get_user_profile(user_id: int):
    if user_id in _user_cache:
        return _user_cache[user_id]  # ← Returns the SAME dict reference
    profile = db.query(User).get(user_id).to_dict()
    _user_cache[user_id] = profile
    return profile
```

**Two distinct problems:**

1. **Stale data:** No TTL. If user updates their profile, the cache serves the old version forever (until process restart).

2. **Mutation leaking:** If the endpoint mutates the returned dict (e.g., `profile["computed_field"] = ...`), that mutation persists in the cache. The next request for the same user sees the mutation. Worse — if the mutation includes request-specific data (auth tokens, other user's context), it leaks.

**Files you'd need to audit:**
- Any module-level `dict`, `defaultdict`, or custom cache class
- Any dependency that returns a reference to a cached mutable object without copying

### Root Cause 3: `lru_cache` + `Depends` Interaction on User-Parametric Functions

```python
@lru_cache(maxsize=256)
def get_user_config(user_id: int):
    return db.query(Config).filter_by(user_id=user_id).first()
```

This looks harmless but:
- The returned ORM object is tied to a (now possibly closed) session
- The object is mutable — if any code modifies `.some_field`, it's modified in the cache
- `maxsize=256` means eviction is LRU, not time-based — stale configs stay until 256 distinct users push them out
- If DB config changes, cached version persists

---

## 3. Files in FastAPI's Source You Must Understand

| File | What It Does | Why It Matters |
|---|---|---|
| `fastapi/params.py:745-748` | `Depends` dataclass definition | `use_cache=True` default; `scope` parameter for generator lifetime |
| `fastapi/dependencies/models.py:32-71` | `Dependant` dataclass + `cache_key` | Cache key is `(callable, scopes, scope)` — understand what makes two deps "the same" |
| `fastapi/dependencies/utils.py:598-735` | `solve_dependencies()` | The core resolution loop; lines 626-627 create fresh cache; lines 664-684 do lookup/store |
| `fastapi/dependencies/utils.py:578-586` | `_solve_generator()` | Generator deps get special lifetime management via `AsyncExitStack` |
| `fastapi/routing.py:457-464` | Request handler calling `solve_dependencies` | Proves no `dependency_cache` is passed → fresh dict per request |
| `fastapi/types.py:12` | `DependencyCacheKey` type | `tuple[Callable[...] | None, tuple[str, ...], str]` — the exact cache key shape |

---

## 4. Concepts You Must Understand Before Fixing

### 4.1 Python Object Identity vs. Value

`lru_cache` stores and returns **the same object**, not a copy. When you cache `SessionLocal()`, every caller gets the identical `Session` instance (same `id()`). This is the fundamental cause of cross-request leaking.

### 4.2 FastAPI's Async Concurrency Model

FastAPI runs on a single-threaded async event loop (uvicorn). `async def` endpoints interleave at every `await`. Two concurrent requests are not parallel threads — they're coroutines taking turns on one thread. But:
- They share the same process memory space
- Module-level variables are shared
- `lru_cache` lives at module level
- When an `await` yields, another request's coroutine can run and access the same cached object

With workers > 1 (uvicorn `--workers N`), each worker is a separate process with its own `lru_cache`, but within one worker, all requests share it.

### 4.3 SQLAlchemy Session Scoping

A SQLAlchemy `Session` is **not safe to share across concurrent requests**. It maintains an identity map (cached ORM objects), transaction state, and connection. Sharing a session means:
- One request's `session.add()` is visible to another
- One request's `session.rollback()` rolls back another's work
- Lazy-loaded relationships trigger queries in the wrong request context

### 4.4 When `lru_cache` IS Appropriate with FastAPI

FastAPI's own docs (`docs/en/docs/advanced/settings.md:206-294`) recommend `@lru_cache` for **one specific pattern**: caching a Pydantic `Settings` object that reads from `.env` files.

```python
@lru_cache
def get_settings():
    return config.Settings()   # ← Immutable Pydantic model, no DB state
```

This is safe **because**:
- `Settings` is effectively immutable (Pydantic model with frozen fields)
- It has no per-request state
- It reads from env vars / `.env` file that don't change at runtime
- No user-specific data

**`lru_cache` is safe ONLY for immutable, request-independent, user-independent data.**

### 4.5 The `Depends` `use_cache` vs. `lru_cache` Distinction

| Property | `Depends(use_cache=True)` | `@lru_cache` |
|---|---|---|
| **Scope** | Per-request only | Process-global, permanent |
| **Lifetime** | Dies when request ends | Lives until process dies or maxsize eviction |
| **Thread safety** | N/A (single async request) | Shared across all concurrent coroutines |
| **Key** | `(callable, scopes, scope)` | Function arguments hash |
| **Purpose** | Dedup within one request's dep tree | Memoize expensive pure computations |

These are **completely different mechanisms**. Mixing them without understanding the scope difference is what causes the bugs.

---

## 5. What Files in YOUR Codebase Are Likely Affected

You haven't shared your codebase, but based on the symptoms described, audit these patterns:

### 5.1 High Priority (data leaking)

Search your codebase for:

```
grep -rn "@lru_cache" --include="*.py" | grep -v "get_settings\|Settings"
```

Any hit that returns a DB session, connection, ORM object, or mutable dict is a bug.

### 5.2 Medium Priority (stale data)

Search for:

```
grep -rn "^_.*cache.*=.*{}\|^_.*cache.*=.*dict()\|^.*_cache:.*dict" --include="*.py"
```

Any module-level dict used as a cache without TTL causes staleness.

### 5.3 Lower Priority (concurrency edge cases)

Search for:

```
grep -rn "Depends.*lru_cache\|lru_cache.*Depends" --include="*.py"
```

Any dependency that is both `@lru_cache`'d AND used via `Depends()` — the `lru_cache` overrides Depends' per-request semantics.

---

## 6. Areas Around the Problem You Need to Know

### 6.1 Generator Dependencies and Cleanup

FastAPI supports generator dependencies (`yield` deps) for cleanup:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

These are managed by `AsyncExitStack` in `_solve_generator()` (utils.py:578-586). The `scope` parameter (`"request"` or `"function"`) controls when cleanup runs. If you wrap this with `lru_cache`, the generator runs **once** and the yielded session is cached forever — the cleanup never runs again.

### 6.2 Dependency Overrides for Testing

FastAPI's `app.dependency_overrides` (routing.py, utils.py:632-647) lets you replace dependencies in tests. This is the **correct** way to inject test doubles — not by clearing `lru_cache`. If you're calling `get_settings.cache_clear()` in tests, that's a code smell.

### 6.3 ASGI Lifespan for Shared Resources

For resources that truly need to be shared (connection pools, Redis clients), use ASGI lifespan events, not `lru_cache`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = create_pool()  # Created once at startup
    yield
    app.state.pool.close()          # Cleaned up at shutdown
```

This is process-level singleton done correctly — explicit lifecycle, visible in code, no hidden caching.

---

## 7. Decision Matrix: What to Cache How

| What You're Caching | Safe Method | Unsafe Method |
|---|---|---|
| Pydantic Settings (immutable) | `@lru_cache` on `get_settings()` | — |
| DB connection pool | ASGI lifespan → `app.state` | `@lru_cache` on pool factory |
| DB session per request | `yield` dependency (generator) | `@lru_cache` on session factory |
| User-specific data | TTL cache with copy-on-read | Global dict without TTL |
| Config from DB | TTL cache (e.g., `cachetools.TTLCache`) | `@lru_cache` (no expiry) |
| Expensive computation (pure) | `@lru_cache` if args are hashable + result immutable | Mutable result in `lru_cache` |

---

## 8. Summary

**FastAPI's `Depends(use_cache=True)` is not the problem.** It is per-request scoped and safe by design.

**The problem is `@lru_cache` and global mutable dicts** layered on top, which:
1. Make process-global singletons out of objects that must be per-request (sessions, connections)
2. Return shared mutable references that let one request's mutations leak to another
3. Have no TTL, serving stale data indefinitely

**Before writing any fix**, audit every `@lru_cache` usage and every module-level cache dict in your codebase against the decision matrix in Section 7.
