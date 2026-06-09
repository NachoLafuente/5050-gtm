#!/usr/bin/env python3
"""
linkedin-self-improvement-loop: the build-measure-learn loop around analyze.py.

analyze.py is the MEASURE stage (parse a LinkedIn export, tag + score every post).
This file is the loop: it keeps a persistent belief model about what drives your
LinkedIn, and every cycle it RECONCILES the last cycle's beliefs against the new
data, UPDATES confidence, PROPOSES one experiment to run next, and emits DRAFT
BRIEFS you can hand to a drafting skill.

The state lives in --state (default ./state):
  beliefs.json     the model (machine)         beliefs.md   the model (human, git-friendly)
  ledger.jsonl     one line per cycle (audit)  snapshots/   parsed metrics per export

Run it on a cadence (e.g. /schedule every 2 weeks) with each fresh export:

    python loop.py --analytics "AggregateAnalytics_*.xlsx" \
                   --archive   "Complete_LinkedInDataExport_folder" \
                   --state ./state --metric engagements

No API keys. Deterministic. The drafting itself is left to a drafting skill so a
human always sees the post before it ships (advisory loop).
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date

import analyze  # MEASURE stage lives next door

# ---- loop tunables --------------------------------------------------------
LEARN_RATE = 0.34       # confirmations to go 0 -> ~0.7 in ~3 cycles
DEADBAND = 0.05         # |ratio-1| < this = inconclusive, no confidence move
MIN_N = 3               # ignore dimension-values with fewer than this many posts
SEED_CONF = 0.20        # confidence a freshly spotted pattern starts at
ARCHIVE_BELOW = 0.08    # drop a belief once confidence decays under this
WIN = "win"
LOSS = "loss"


# ---- MEASURE: turn an export into per-dimension ratios --------------------
def metric_of(p, metric):
    return {"engagements": p["eng"], "impressions": p["imp"], "er": p["er"]}[metric]


def snapshot(P, metric):
    """Per-dimension {value: {ratio, n, avg}} vs the overall mean of `metric`."""
    overall = sum(metric_of(p, metric) for p in P) / len(P)
    dims = {
        "topic": lambda p: p["topics"],
        "hook": lambda p: p["hooks"],
        "day": lambda p: [p["day"]],
        "length": lambda p: [analyze.length_bucket(p["len"])],
    }
    out = {}
    for dim, fn in dims.items():
        buckets = defaultdict(list)
        for p in P:
            for v in fn(p):
                buckets[v].append(metric_of(p, metric))
        out[dim] = {
            v: {"n": len(xs), "avg": sum(xs) / len(xs), "ratio": (sum(xs) / len(xs)) / overall if overall else 0}
            for v, xs in buckets.items()
        }
    return {"overall": overall, "dims": out}


# ---- state load/save ------------------------------------------------------
def load_state(state_dir, metric):
    path = os.path.join(state_dir, "beliefs.json")
    if os.path.isfile(path):
        return json.load(open(path))
    return {"version": 1, "metric": metric, "cycles": [], "beliefs": {}}


def save_state(state_dir, st):
    json.dump(st, open(os.path.join(state_dir, "beliefs.json"), "w"), indent=2)
    render_beliefs_md(state_dir, st)


def render_beliefs_md(state_dir, st):
    rows = sorted(st["beliefs"].values(), key=lambda b: -b["confidence"])
    L = [
        "# LinkedIn beliefs",
        "",
        f"_Metric: **{st['metric']}** · cycles: {len(st['cycles'])} · "
        f"last: {st['cycles'][-1] if st['cycles'] else '-'}_",
        "",
        "Confidence rises each cycle a belief survives, halves when contradicted. "
        "A belief is just: \"posts with this trait beat your average.\"",
        "",
        "| Confidence | Trait | Effect | Posts (n) | Cycles | Status |",
        "|---|---|---|---|---|---|",
    ]
    for b in rows:
        bar = "#" * round(b["confidence"] * 10)
        L.append(
            f"| {b['confidence']:.2f} `{bar:<10}` | {b['dim']} = **{b['value']}** "
            f"| {b['effect']:.2f}x | {b['n']} | {b['cycles_seen']} | {b['status']} |"
        )
    open(os.path.join(state_dir, "beliefs.md"), "w").write("\n".join(L) + "\n")


# ---- RECONCILE + UPDATE ---------------------------------------------------
def key(dim, value):
    return f"{dim}={value}"


def reconcile(st, snap, today):
    """Move every existing belief's confidence based on the new snapshot."""
    deltas = []
    seen = set()
    for dim, values in snap["dims"].items():
        for value, m in values.items():
            if m["n"] < MIN_N:
                continue
            k = key(dim, value)
            seen.add(k)
            ratio = m["ratio"]
            if k in st["beliefs"]:
                b = st["beliefs"][k]
                old = b["confidence"]
                agree = (b["direction"] == WIN and ratio > 1 + DEADBAND) or (
                    b["direction"] == LOSS and ratio < 1 - DEADBAND
                )
                contra = (b["direction"] == WIN and ratio < 1 - DEADBAND) or (
                    b["direction"] == LOSS and ratio > 1 + DEADBAND
                )
                if agree:
                    b["confidence"] = round(old + LEARN_RATE * (1 - old), 3)
                    verdict = "confirmed"
                elif contra:
                    b["confidence"] = round(old * 0.5, 3)
                    verdict = "contradicted"
                else:
                    verdict = "inconclusive"
                b["effect"] = round(ratio, 2)
                b["n"] = m["n"]
                b["cycles_seen"] += 1
                b["history"].append({"date": today, "ratio": round(ratio, 2), "n": m["n"]})
                if b["confidence"] < ARCHIVE_BELOW:
                    b["status"] = "archived"
                deltas.append({"trait": k, "from": old, "to": b["confidence"], "verdict": verdict, "effect": round(ratio, 2)})
    return deltas, seen


def discover(st, snap, seen, today):
    """Add freshly spotted strong patterns as low-confidence beliefs."""
    added = []
    for dim, values in snap["dims"].items():
        for value, m in values.items():
            if m["n"] < MIN_N:
                continue
            k = key(dim, value)
            if k in st["beliefs"]:
                continue
            ratio = m["ratio"]
            if abs(ratio - 1) <= DEADBAND:
                continue  # average, not a pattern
            direction = WIN if ratio > 1 else LOSS
            st["beliefs"][k] = {
                "dim": dim,
                "value": value,
                "direction": direction,
                "effect": round(ratio, 2),
                "confidence": SEED_CONF,
                "n": m["n"],
                "cycles_seen": 1,
                "status": "tracking",
                "history": [{"date": today, "ratio": round(ratio, 2), "n": m["n"]}],
            }
            added.append({"trait": k, "direction": direction, "effect": round(ratio, 2), "n": m["n"]})
    return added


# ---- PROPOSE one experiment ----------------------------------------------
def propose(st):
    """Highest leverage = biggest effect on the least-settled WIN belief."""
    live = [
        b for b in st["beliefs"].values()
        if b["status"] != "archived" and b["direction"] == WIN and b["confidence"] < 0.85 and b["n"] >= MIN_N
    ]
    if not live:
        return None
    live.sort(key=lambda b: -(abs(b["effect"] - 1) * (1 - b["confidence"])))
    bet = live[0]
    # worst thing to stop doing
    losers = [b for b in st["beliefs"].values() if b["direction"] == LOSS and b["status"] != "archived" and b["n"] >= MIN_N]
    stop = min(losers, key=lambda b: b["effect"]) if losers else None
    return {"bet": bet, "stop": stop}


def best_by_dim(st, dim):
    cands = [
        b for b in st["beliefs"].values()
        if b["dim"] == dim and b["direction"] == WIN and b["status"] != "archived" and b["n"] >= MIN_N
    ]
    if not cands:
        return None
    return max(cands, key=lambda b: b["confidence"] * abs(b["effect"] - 1))


def draft_briefs(st, prop):
    """Structured briefs for a drafting skill. Combines the bet with your best
    topic/hook/day so the next posts execute the experiment in-voice."""
    bet = prop["bet"]
    topic = best_by_dim(st, "topic")
    hook = best_by_dim(st, "hook")
    day = best_by_dim(st, "day")
    base = {
        "topic": (topic["value"] if topic else "your strongest topic"),
        "hook": (hook["value"] if hook else "Statement"),
        "day": (day["value"] if day else "your best day"),
    }
    # ensure the bet's own dimension is reflected in the brief
    base[bet["dim"]] = bet["value"]
    briefs = [
        {
            "angle": f"Lead with the **{base['hook']}** hook on a **{base['topic']}** angle.",
            "topic": base["topic"], "hook": base["hook"], "post_on": base["day"],
            "tests": key(bet["dim"], bet["value"]),
        },
        {
            "angle": f"Second post, same experiment, different angle on **{base['topic']}** "
                     f"(vary the opener so it's not a repeat).",
            "topic": base["topic"], "hook": base["hook"], "post_on": base["day"],
            "tests": key(bet["dim"], bet["value"]),
        },
    ]
    return briefs


# ---- report ---------------------------------------------------------------
def report(st, snap, deltas, added, prop, briefs):
    L = []
    p = L.append
    p("=" * 70)
    p("LINKEDIN SELF-IMPROVEMENT LOOP")
    p("=" * 70)
    p(f"\nMetric this loop optimizes: {st['metric']} | cycle #{len(st['cycles'])}")

    p("\n## RECONCILE  (last cycle's beliefs vs this export)")
    if not deltas:
        p("  First cycle, or nothing tracked yet. Beliefs seeded below.")
    for d in sorted(deltas, key=lambda x: -abs(x["to"] - x["from"])):
        arrow = "UP" if d["to"] >= d["from"] else "DOWN"
        p(f"  [{d['verdict']:13s}] {d['trait']:18s} conf {d['from']:.2f} -> {d['to']:.2f} ({arrow}) | {d['effect']:.2f}x")

    if added:
        p("\n## DISCOVERED  (new patterns added to the model this cycle)")
        for a in sorted(added, key=lambda x: -abs(x["effect"] - 1)):
            p(f"  + {a['trait']:18s} {a['direction']:4s} {a['effect']:.2f}x  (n={a['n']})")

    p("\n## BELIEFS  (the model, top by confidence)")
    for b in sorted([b for b in st["beliefs"].values() if b["status"] != "archived"], key=lambda b: -b["confidence"])[:10]:
        p(f"  {b['confidence']:.2f}  {b['dim']:7s} = {b['value']:14s} {b['effect']:.2f}x  n={b['n']}  ({b['cycles_seen']} cyc)")

    p("\n## PROPOSE  (one experiment, highest leverage)")
    if not prop:
        p("  No actionable WIN belief above the noise floor yet. Keep posting, run again next export.")
    else:
        bet = prop["bet"]
        p(f"  >> BET: lean into {bet['dim']} = {bet['value']}  ({bet['effect']:.2f}x your avg, confidence {bet['confidence']:.2f})")
        p(f"     Why: biggest effect on the least-settled belief. Confirm it or kill it next cycle.")
        if prop["stop"]:
            s = prop["stop"]
            p(f"  >> STOP: {s['dim']} = {s['value']} drags ({s['effect']:.2f}x). Cut it from the rotation.")

    if briefs:
        p("\n## DRAFT BRIEFS  (hand these to your drafting skill, e.g. /social-content)")
        for i, b in enumerate(briefs, 1):
            p(f"  {i}. {b['angle']}")
            p(f"     topic={b['topic']} | hook={b['hook']} | post_on={b['post_on']} | tests={b['tests']}")

    p("\n## NEXT")
    p("  1. Expand the briefs into posts (in voice), ship them.")
    p("  2. Re-run this loop with your next analytics export (~2 weeks).")
    p("  3. The loop will tell you if the bet paid off and pick the next one.")
    return "\n".join(L)


# ---- orchestration --------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="LinkedIn build-measure-learn loop")
    ap.add_argument("--analytics", required=True, help="AggregateAnalytics_*.xlsx")
    ap.add_argument("--archive", help="Shares_*.csv or the data-export folder (for post text)")
    ap.add_argument("--state", default="./state", help="State dir (default ./state)")
    ap.add_argument("--metric", default="engagements", choices=["engagements", "impressions", "er"])
    args = ap.parse_args()

    if not os.path.isfile(args.analytics):
        sys.exit(f"Analytics file not found: {args.analytics}")
    os.makedirs(os.path.join(args.state, "snapshots"), exist_ok=True)

    # MEASURE
    data = analyze.parse_analytics(args.analytics)
    shares = analyze.find_shares_csv(args.archive)
    analyze.join_text(data["top_posts"], shares)
    P = analyze.enrich(data["top_posts"])
    if not P:
        sys.exit("No posts with impressions + engagements in the export. Check the TOP POSTS sheet.")

    today = str(date.today())
    snap = snapshot(P, args.metric)
    json.dump({"date": today, "metric": args.metric, **snap},
              open(os.path.join(args.state, "snapshots", f"{today}.json"), "w"), indent=2)

    # LEARN
    st = load_state(args.state, args.metric)
    deltas, seen = reconcile(st, snap, today)
    added = discover(st, snap, seen, today)
    st["cycles"].append(today)
    st["updated"] = today

    # PROPOSE + DRAFT
    prop = propose(st)
    briefs = draft_briefs(st, prop) if prop else []

    save_state(args.state, st)
    with open(os.path.join(args.state, "ledger.jsonl"), "a") as f:
        f.write(json.dumps({
            "date": today, "metric": args.metric, "posts_seen": len(P),
            "reconciled": deltas, "discovered": added,
            "proposed": (key(prop["bet"]["dim"], prop["bet"]["value"]) if prop else None),
        }) + "\n")

    print(report(st, snap, deltas, added, prop, briefs))
    print(f"\nState updated: {os.path.join(args.state, 'beliefs.md')}")


if __name__ == "__main__":
    main()
