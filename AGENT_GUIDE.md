# Forge Imagine — Agent Guide

> This document is for AI agents integrating Forge Imagine into their workflows.
> Not for end users. Not a technical API reference — that's in `README.md`.

---

## Before You Generate a Single Ad

**Do not rush to generate ads.** A creative tool without product knowledge produces expensive noise.

Before calling any `generate_*` function, you must complete a knowledge build for the client. This is not a form. It is a conversation — one you lead, not one the user fills out.

---

## Step 0 — Check What You Already Know First

**Do not ask the user for information you already have. Do not scrape a URL before checking internal knowledge.**

Before touching any external source, exhaust internal knowledge in this order:

### 0a — Search Your Own Memory
- Search `MEMORY.md` and all `memory/*.md` files for anything about this client or product
- Scan workspace reference files — enterprise agents may be preloaded with product briefs, brand guides, or compliance documents at deploy time
- Check if a knowledge pack already exists: call `load_knowledge_pack(client_id, product_slug)` from `knowledge_builder.py`
  - If it exists and is complete → use it, skip Steps 0b and 0c entirely
  - If it exists but is outdated or thin → note the gaps, proceed to 0b/0c for those gaps only

### 0b — Query Other Agents (if on a shared gateway)
- Query Archon, Helena, or any other agent that works with this client
- Do not duplicate conversations the user has already had with other agents
- Pass whatever you find into `gather_build_material(prior_context=...)` as agent memory

### 0c — Scrape the URL (if needed)
- Only reach for `scrape_text(url)` after 0a and 0b are exhausted or insufficient
- Pass all internal context collected above into `gather_build_material(prior_context=...)` first
- If `ScraperBlockedError` is raised: stop, tell the user clearly, ask them to paste or upload product content. Never hallucinate.

### Rule: Internal knowledge takes precedence
If your memory and the scraped content conflict, trust your memory. You were explicitly loaded with accurate information. Scraped marketing copy may be aspirational, outdated, or imprecise — your preloaded context was provided by someone who knows the product.

### Always confirm sources to the operator
After building or updating a knowledge pack, report:
> "Saved knowledge pack for [Product]. Sources used: [agent memory / scrape:requests / scrape:playwright / user-provided]"

The operator should always know what went into the knowledge pack.

---

## Step 1 — Onboarding Conversation

If no knowledge file exists, or if it's incomplete, conduct the onboarding conversation. This is semi-structured — you do not need to ask questions in order, and you should skip anything you already know from shared context.

**The things you must know before generating any ad:**

### Product
- What does this product do? (One clear sentence — if you can't write this, the user can't either and you need to slow down)
- Who is it for? (Demographics, health status, geography, mindset)
- What is the core value proposition? (What changes in the customer's life because of this product?)
- What does it NOT do? (Critical for regulated health/biotech products — FDA guardrails depend on this)
- What is the product category? (Consumer health, medical device, supplement, SaaS, etc.)

### Brand & Tone
- What's the brand voice? (Clinical and authoritative? Warm and hopeful? Urgent and direct?)
- Are there words or claims that must NEVER appear? (Get specific — "cures", "prevents", specific competitor names, etc.)
- Are there regulatory or legal constraints? (FDA, FTC, HIPAA comms, state-level — what applies?)

### Audience
- Where does this audience spend time? (Facebook, Instagram, Google, LinkedIn, email?)
- What is the audience's primary emotional state before encountering this ad? (Anxious? Proactive? Uninformed? Skeptical?)
- What objections does the audience typically have?

### Creative Direction
- What imagery has worked well in the past? (Share examples if available)
- What imagery must be avoided?
- Does the brand have a logo and approved brand colors?

### Campaign Objective
- Is this ad for cold audience (awareness), warm audience (conversion), or existing customers (retention/upsell)?
- What is the desired action? (Click to website, DM, phone call, purchase?)

---

## Step 2 — Write the Knowledge File

Once you have enough context, write it to:
```
brand_kits/<client_id>_knowledge.md
```

Write it in plain language as if briefing a copywriter. Not a database schema — a brief. Include everything a creative professional would need to write compelling, accurate, compliant ad copy for this client without asking a single follow-up question.

**Example structure:**

```markdown
# [Product Name] — Creative Knowledge Pack
Last updated: [date]

## Product
[1-3 sentences: what it is, what it does, who it's for]

## Audience
[Specific target: demographics, psychographics, health context, where they are]

## Core Value Propositions
- [Prop 1]
- [Prop 2]
- [Prop 3]

## What To Say (proven angles)
- [Emotional hook that resonates]
- [Rational differentiator]
- [Social proof or credibility frame]

## What NOT To Say
- Never claim: [specific claims]
- Always include: [required language]
- Regulatory constraint: [plain-English summary]

## Brand Voice
[2-3 sentences: tone, feel, what the brand sounds like]

## Imagery That Works
[Description of visual themes, settings, demographics that have tested well]

## Campaign Context
[What's the current objective? What's been tried? What's working?]
```

Update this file whenever you learn something new. It should get richer over time.

---

## Step 3 — Verify Before Generating

Before generating any ad, confirm:

- [ ] You can state the product's core value in one sentence without hesitation
- [ ] You know who the ad is for with enough specificity to imagine that person
- [ ] You know the regulatory constraints (especially for health/biotech)
- [ ] You have brand colors, logo, and tone locked
- [ ] You know what imagery direction to give the image model
- [ ] You have a campaign objective (cold, warm, retargeting)

If you are uncertain on any of these, ask. A 5-minute onboarding conversation saves 50 ad generations that miss the mark.

---

## Asset Management

### Input Assets (logos, product photos, reference images)
Store in: `brand_kits/assets/<client_id>/`

How assets arrive:
- **Discord attachment:** User sends file → download the attachment URL → save to assets directory
- **URL (Dropbox/Drive share link):** Download directly via `requests.get(url)` → save to assets directory
- **Existing workspace:** Pull from shared knowledge if another agent already has the files

Once stored locally, reference assets by path. Do not re-download on every run.

### Output Assets (generated ads)
Store in: `output/<client_id>/<YYYY-MM-DD>/`

Deliver to user via Discord attachment or email. Never just print a file path — the user can't access the VPS filesystem.

---

## What Good Looks Like

A good Forge Imagine session:
1. Agent pulls shared context → identifies what it knows and doesn't
2. Brief onboarding conversation → fills gaps, confirms brand constraints
3. Agent writes or updates the knowledge file
4. User provides or confirms a campaign brief ("this week we're targeting 50+ men who've been told they have liver risk")
5. Agent generates 3 copy variants, shows the brief to user for sanity check
6. Agent generates 1 image + composite → sends for visual approval
7. If approved, generates full ad set (all platforms, all copy variants)
8. Outputs delivered via channel

A bad Forge Imagine session:
1. User says "make me some ads"
2. Agent immediately generates 9 ads with generic copy
3. User says "these are wrong, our product doesn't do that"
4. Wasted API spend, wasted time, eroded trust

---

## Forge Imagine Is a Capability, Not an Agent

Forge Imagine is a tool your agent calls — not a standalone product. You are the one with the relationship, the memory, and the judgment. Forge Imagine handles the image generation and compositing. You handle knowing when to use it, what to say, and whether the output is good.

The tool will generate whatever you tell it to. The quality of the brief you give it is the quality of the ads you get out.
