---
name: proposal
description: Turn a sales or discovery call transcript into a complete, ready-to-send implementation proposal: snapshot, executive summary, outcomes, scope, out-of-scope, deliverables, timeline, and investment. Use when the user says "/proposal", pastes a call transcript, or asks to "draft a proposal", "write the SOW", or "turn this transcript into a proposal". Output goes to the chat as copy-ready markdown. One-shot, no warehouse.
---

# Proposal Generator

Turn a sales or discovery call transcript into a complete implementation proposal. The deliverable is **copy-ready markdown in the chat**, not a file.

## Input

Paste the call transcript, or give a file path to it. Extract the client name, company, attendees, scope discussed, pain points, and any numbers mentioned (budget, deadline, user count).

If critical facts are missing (client legal name, company, signer name, timeline), ask ONE consolidated question before writing. Do not invent commercials.

> If your notes tool has an API, you can pull the transcript programmatically. Keep any keys in your own `.env` and read them at runtime, never hard-code credentials into the skill.

## Pre-Flight (before generating anything)

After reading the transcript, ask a single consolidated question block. Never assume pricing, timeline, or phasing from the transcript alone: the transcript captures what the client *said*, you decide what to *quote*. Draft your own answers first, then ask to confirm or override:

```
Before I draft, confirm these so I don't have to redo it:

1. Currency (set by client geography)
   Client HQ: {country/city from transcript}
   Currency:  {detected}, confirm or override?

2. Bundle structure (default: 1 to 2 bundles)
   - Bundle 1, {scope summary}: {price you'll set}
   - Bundle 2, {scope summary}: {price you'll set}
   Override anything? Different structure (single bundle, 3+ bundles)?

3. Timeline
   - Bundle 1: {N} weeks
   - Bundle 2: {N} weeks (if relevant)
   - Kickoff: mid-{month} (use vague months, NEVER fixed calendar dates)
   - Go-live: late {month}
   Sound right, or compress/extend?

4. Signer + decision flow
   - Signer: {name or "TBC"}
   - Anyone else needs to approve?

5. Anything to adjust from the transcript
   - Scope to trim or add? Pain to lean harder into? Past clients to name?
```

Wait for the response, then draft.

**Defaults if not overridden:** detect currency from geography; 1 to 2 bundles; payment terms per your standard; support / training / docs NOT included unless asked; vague month language for dates.

## Voice & Quality Bar

- **Never use em dashes.** Use commas, periods, colons, parentheses, or line breaks. (En dashes for ranges like "Weeks 1 to 3" or numeric ranges are fine.)
- **Specific, not generic.** Name the exact attributes, objects, lists, integrations, and figures the client mentioned. Not "restructure the data model" but "Archive the 80+ custom attributes on the Company object, rebuild as list-level attributes."
- **Diagnose, don't describe.** Call out concrete issues in their current setup. This is what makes the client trust you understood.
- **Hands-on, not advisory.** Deliverables are built, migrated, deployed, never "recommended" or "facilitated."
- **Phased with week ranges.** Every scope item gets a phase and a week number.
- **Short sentences. No fluff.** No "excited to partner" language. No "robust," "comprehensive," "best-in-class."
- **Visual cohesion.** Every section has AT LEAST ONE of: a `> key: value` snapshot callout, a table, or 5+ named bullets. Bare-paragraph sections fail the bar.

## Output

Output the proposal as markdown in the chat, copy-ready for the client. Use `## N. Section Name` headers. Fill every placeholder with transcript-derived content.

### Header block (above section 1)

```
> Prepared for: {Client Company}
> Prepared by:  {Your name}, {Your company}
> Date:         {today}
```

### Project Snapshot (below the header, before Section 1)

```
> project:      {3-6 word project name}
> investment:   {Bundle 1 price} and/or {Bundle 2 price}
> timeline:     {N} weeks ({phase count} phases)
> integrations: {comma-separated tool names, or "None"}
> teams:        {comma-separated teams in scope}
> signer:       {Name}, {Role}
> valid_until:  {today + 10 days, DD.MM.YYYY}
```

### 1. Executive Summary

Open with a `> key: value` callout (in_scope, outcome, phases), then 2 to 4 sentences: what you're building, for whom, why it matters.

### 2. Outcomes & Objectives

**Lead with value, not tasks.** Two halves:

**2a. Business Outcomes.** A short paragraph in the client's own language describing what changes for their business once this is live, then 3 to 5 bullets phrased as the buyer's wins. Format each: **{outcome in client language}** -> {what enables it} -> {quantified impact where possible}. The litmus test: the client should recognize their own words.

**2b. Project Objectives.** Numbered list, 5 to 7 items minimum. Concrete operational objectives that produce the outcomes above.

### 3. Scope of Work

Organized into **Phases** (0 to 4) with week ranges. Under each phase, use bolded sub-sections and bullet lists. Name concrete artifacts: lists, pipelines, objects, attributes, workflows. **Minimum 15 named artifacts** across all phases. If you can't hit that, push back on the user about what's actually in scope before drafting. **This section is the heart**: if it's vague, the proposal is weak.

### 4. Out of Scope

Bulleted exclusions. By default exclude (unless explicitly opted in):

- **Post-launch support, training, and documentation.** Any post-handover work is billed as a new engagement.
- **Historical backfills for integrations.** Integrations sync from go-live forward; backfilling historical data is an optional add-on, priced separately.

### 5. Deliverables

Markdown table: `#`, `Deliverable`, `Team/Area`. **Minimum 8 rows.** Each deliverable phrased as a noun the client can point at after go-live ("Investor Relations list with 12 attributes," not "list configuration work").

### 6. Indicative Timeline

Markdown table: `Phase`, `Activity`, `Timing`. Mirror the phase breakdown from Section 3.

### 7. Investment

This is the price the client pays. Open with a `> key: value` callout (bundles, currency, payment, validity). Then:

1. Present 1 to 2 bundles, each with a one-line scope summary and a price.
2. State validity (e.g. 10 days), currency, and your payment terms.

Describe the value, not the hours. Price each bundle as a whole, never as a time estimate.

## Rules

1. **Output to chat, copy-ready.**
2. **No placeholders left.** If you can't derive a value, ask before writing. Don't scatter `[TBD]` through the draft.
3. **No support, training, or docs by default.** Only include if explicitly asked.
4. **Today's date** in the Date fields: `Month DD, YYYY` at the top.
5. **Section 3 is the heart.** Name the objects, attributes, lists, integrations, and workflows explicitly.
6. **Visual cohesion is mandatory.** The Project Snapshot block and per-section `> key: value` callouts are not optional. Bare-paragraph sections fail the bar.
7. **Lead with value, not deliverables** (Section 2a before 2b), in the client's language.
