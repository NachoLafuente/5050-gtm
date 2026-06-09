# Sample loop output

Anonymized illustration of `loop.py` (identity stripped, numbers real-shaped). The point
isn't the one report - it's that running it again in two weeks reconciles against this.

## Cycle 1 (first run - everything is newly discovered)

```
LINKEDIN SELF-IMPROVEMENT LOOP
Metric this loop optimizes: engagements | cycle #1

## RECONCILE
  First cycle, nothing tracked yet. Beliefs seeded below.

## DISCOVERED
  + hook=Personal-I    win  1.68x  (n=5)
  + hook=Contrarian    win  1.67x  (n=3)
  + topic=CRM          win  1.45x  (n=21)
  + day=Wed            win  1.42x  (n=5)
  + day=Fri            loss 0.58x  (n=7)
  ...

## PROPOSE  (one experiment, highest leverage)
  >> BET:  lean into hook = Personal-I  (1.68x your avg, confidence 0.20)
  >> STOP: day = Fri drags (0.58x). Cut it from the rotation.

## DRAFT BRIEFS
  1. Lead with the Personal-I hook on a CRM angle.
     topic=CRM | hook=Personal-I | post_on=Wed | tests=hook=Personal-I
  2. Second post, same experiment, different angle on CRM.
     topic=CRM | hook=Personal-I | post_on=Wed | tests=hook=Personal-I
```

## Cycle 2 (two weeks + a few posts later)

The same beliefs are now checked against fresh data instead of discovered cold:

```
## RECONCILE  (last cycle's beliefs vs this export)
  [confirmed    ] hook=Personal-I   conf 0.20 -> 0.47 (UP)   | 1.66x
  [contradicted ] day=Wed           conf 0.20 -> 0.10 (DOWN) | 0.94x
  [inconclusive ] topic=CRM         conf 0.47 -> 0.47        | 1.39x

## PROPOSE
  >> BET: lean into hook = Contrarian (1.71x, confidence 0.20)
     (Personal-I confirmed and is climbing; the loop moves to the next unsettled bet.)
```

That's the whole idea: **Personal-I got confirmed and promoted, the Wednesday hunch got
contradicted and demoted, and the loop automatically advanced to the next experiment.**
Beliefs that survive enough cycles become laws; ones that break get archived.

## How to read it

- **Confidence is the signal, effect is the size.** A 1.7x effect at 0.20 confidence is a
  fresh hunch; the same effect at 0.80 across four cycles is a law.
- **One bet at a time.** The loop deliberately proposes a single experiment so you can
  actually tell whether it worked, instead of changing ten things at once.
- **STOP matters as much as BET.** Cutting your worst-performing trait is often higher ROI
  than adding a new winner.
