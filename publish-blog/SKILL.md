---
name: publish-blog
description: >
  Turn any agent conversation into a polished Hashnode blog post. Analyzes the conversation thread —
  questions asked, choices made, solutions reached — auto-detects the best blog format, generates
  beginner-friendly markdown rich with real insights, and publishes via Hashnode MCP tools.
  Use when: the user says "publish blog", "write a blog from this", "blog this conversation",
  "post to hashnode", "/publish-blog", or wants to turn a conversation into a readable blog post.
---

# Publish Blog — Conversation to Hashnode

Turn the current conversation into a publish-ready blog post on Hashnode. The blog should read
like a knowledgeable friend explaining the topic — clear enough for beginners, insightful enough
for practitioners.

## When to Activate

- User runs `/publish-blog`
- User says "publish this as a blog", "turn this into a blog", "blog this", "post to hashnode"
- End of a conversation where the user wants to share what was discussed

## Prerequisites

The `hashnode` MCP server must be connected. Verify by calling `hashnode_get_publication` first.
If it fails, tell the user to run the setup script:

```
~/.grok/skills/publish-blog/scripts/setup.sh
```

---

## Step 1: Extract the Conversation Spine

Read the full conversation and pull out these 7 elements. Do not skip any.

| Element | What to extract | Why it matters |
|---|---|---|
| **Core Question** | The original problem or topic the user brought up | Becomes the blog hook |
| **Starting Context** | What the user already knew, their setup, constraints | Helps readers self-qualify ("this is for me") |
| **Options Explored** | Every approach discussed, including rejected ones | Shows the reasoning, not just the answer |
| **Decision Rationale** | WHY a choice was made — tradeoffs, constraints, preferences | The most valuable part for readers |
| **Code & Config** | Any code, commands, config snippets, or outputs | Concrete proof the solution works |
| **Gotchas Found** | Surprising behaviors, edge cases, mistakes made along the way | Saves readers hours of debugging |
| **Final Outcome** | What worked, what was built, what was decided | The payoff |

If any element is missing from the conversation (e.g., no code was written), note it and skip that
section in the blog — do not invent content.

---

## Step 2: Auto-Detect Blog Format

Classify the conversation into one of three formats based on its shape:

### Format A: Problem → Solution
**Use when:** The conversation started with a bug, error, architecture question, or "how do I..."
and ended with a resolution.

Signals: error messages, debugging steps, comparing alternatives, "this worked".

### Format B: Step-by-Step Tutorial
**Use when:** The conversation followed a build-along pattern — "set up X, then configure Y,
then connect Z" with incremental progress.

Signals: sequential steps, setup instructions, "now let's add...", building toward a working thing.

### Format C: TIL / Quick Insight
**Use when:** The conversation was short (under ~10 exchanges) and centered on a single discovery,
technique, or clarification.

Signals: brief exchange, one "aha" moment, a specific tip or pattern.

**Tell the user which format you chose and why.** Let them override it.

---

## Step 3: Generate the Blog Post

### Writing Voice — The Three Rules

1. **Clear over clever.** Write like you are explaining to a smart friend who has not seen this
   specific topic before. No jargon without a parenthetical explanation on first use.
2. **Insightful over comprehensive.** Do not pad. Every paragraph must teach something, show
   something, or connect two ideas. If a sentence just "sounds professional" but adds nothing,
   delete it.
3. **Concrete over abstract.** Replace "this approach is more efficient" with "this cuts the
   response time from 800ms to 120ms because it avoids the N+1 query."

### Banned Phrases — Delete on Sight

- "In this blog post, we will explore..."
- "Let's dive in" / "Let's get started" / "Without further ado"
- "It's worth noting that" / "It's important to mention"
- "In today's rapidly evolving landscape"
- "game-changer" / "revolutionary" / "cutting-edge" / "powerful"
- "As we all know" / "As you can see"
- Ending with a vague question just for engagement

### Content Structure by Format

#### Format A: Problem → Solution

```markdown
# [Specific problem statement] — [Solution approach in ≤5 words]

> **TL;DR:** [One sentence: what the problem was and how it was solved.]

## The Problem

[What went wrong or what was needed. Be specific. Include the actual error message,
symptom, or requirement. A reader with the same problem should think "that's exactly
what I'm seeing."]

## What I Considered

### [Option 1 name]
[1-2 sentences: what it is and why it looked promising.]

**Verdict:** [Worked / Didn't work / Partially worked — and the specific reason why.]

### [Option 2 name]
[Same structure.]

> **Key insight:** [The non-obvious thing this comparison revealed.]

## The Solution

[The approach that worked. Walk through it step by step.]

```[language]
// Include the actual code with short, useful comments
// Not obvious-comments like "// import the module"
```

[Explain WHY this works — the underlying mechanism, not just the steps.]

## Watch Out For

- [Gotcha 1: specific, actionable]
- [Gotcha 2]
- [Gotcha 3]

## Takeaways

- [Concrete lesson 1]
- [Concrete lesson 2]
- [Concrete lesson 3]
```

#### Format B: Step-by-Step Tutorial

```markdown
# How to [Build/Set Up/Configure X] with [Technology Y]

> **What you'll end up with:** [One sentence describing the working result.]

## Before You Start

- [Prerequisite 1 — with version if it matters]
- [Prerequisite 2]

## Step 1: [Action verb — Set up / Create / Configure]

[Why this step matters — one sentence.]

```[language]
[code]
```

[What to expect: what the output looks like, what to check.]

## Step 2: [Action verb]

[Same pattern: context → code → verification.]

...

## Common Mistakes

| Mistake | What happens | Fix |
|---|---|---|
| [Specific mistake] | [Symptom] | [One-line fix] |

## What You Learned

- [Skill/concept 1 the reader now has]
- [Skill/concept 2]
```

#### Format C: TIL / Quick Insight

```markdown
# TIL: [The specific thing you learned]

> [One sentence: when this knowledge is useful.]

## Context

[What I was doing when I ran into this — 2-3 sentences max.]

## The Thing

[The actual insight. Show it with code, a comparison, or a concrete example.]

```[language]
[code that demonstrates the insight]
```

## Why This Matters

[When you'd reach for this. What it saves you. One paragraph.]

## Quick Reference

```[language]
[The minimal snippet someone would bookmark]
```
```

### Making It Not Plain — Insight Injection Rules

After generating the draft, scan every section and apply these:

1. **Before/After pairs.** Wherever you describe an improvement, show the before and after
   side by side. Readers remember comparisons.
2. **"The reason this works" callouts.** After any code block that does something non-obvious,
   add a short paragraph starting with "This works because..." explaining the underlying mechanism.
3. **Gotcha boxes.** For every tricky detail found in the conversation, add a bold callout:
   **Watch out:** [specific thing] — [what happens if you miss it].
4. **Decision context.** When the conversation compared options, don't just say which won.
   Show the tradeoff: "Option A is simpler but breaks under [condition]. Option B handles
   that at the cost of [tradeoff]."
5. **Real numbers and real output.** If the conversation produced measurable results (timing,
   file sizes, error counts), include them. "Reduced from X to Y" beats "made it faster."

---

## Step 4: Compose Metadata

Generate:

- **Title:** Specific and searchable. Bad: "My Experience with Caching". Good: "Fixing Slow API
  Responses with Redis Read-Through Caching in FastAPI".
- **Subtitle:** One sentence that adds context the title doesn't cover.
- **Slug:** Lowercase, hyphenated, ≤60 chars. Derived from the title.
- **Tags:** 3-5 relevant tags. Use common Hashnode tag slugs (e.g., "javascript", "python",
  "web-development", "devops", "beginners"). Verify they exist with `hashnode_search_tags`.
- **Cover image:** If the user has one, use it. Otherwise skip — Hashnode has defaults.

---

## Step 5: Draft Review

Present the complete blog to the user:

1. Show the metadata (title, subtitle, slug, tags)
2. Show the full markdown body in a code block
3. Ask:
   - **Publish now** — goes live immediately
   - **Save as draft** — saved to Hashnode dashboard for further editing
   - **Edit first** — user gives feedback, you revise, then re-present

**Never publish without explicit user approval.**

---

## Step 6: Publish

### If "Publish now"
1. Use `search_tool` to find `hashnode_publish_post` schema
2. Call `hashnode_publish_post` with: title, contentMarkdown, subtitle, slug, tags, coverImageURL
3. Return the live URL to the user

### If "Save as draft"
1. Use `search_tool` to find `hashnode_create_draft` schema
2. Call `hashnode_create_draft` with the same fields
3. Tell the user: "Draft saved. You can edit it at your Hashnode dashboard."

### If "Edit first"
Apply user's feedback, regenerate the relevant sections, and return to Step 5.

---

## Quality Gate — Check Before Presenting Draft

- [ ] Title is specific enough to be useful in search results
- [ ] TL;DR / intro tells the reader what they get in one sentence
- [ ] Every jargon term is explained in parentheses on first use
- [ ] Every code block has a language tag and non-obvious comments only
- [ ] No banned phrases survived
- [ ] At least one before/after, comparison, or concrete number appears
- [ ] Gotchas section has at least one entry (if the conversation surfaced any)
- [ ] Takeaways are concrete actions or lessons, not vague summaries
- [ ] Blog reads naturally start to finish — no awkward transitions

---

## Related Skills

- `article-writing` — general long-form writing with voice matching
- `content-engine` — adapt blog content for X, LinkedIn, newsletters
- `brand-voice` — build a reusable authorial voice profile
- `crosspost` — distribute the blog as social posts after publishing