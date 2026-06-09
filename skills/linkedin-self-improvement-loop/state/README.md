# state/

The loop writes its memory here. **None of it is committed** (see `.gitignore`) - it's
your personal LinkedIn data and your private belief model.

- `beliefs.json` / `beliefs.md` - the model: traits with confidence that updates each cycle
- `ledger.jsonl` - one line per cycle (audit trail)
- `snapshots/<date>.json` - parsed metrics per export, for cross-cycle trends

Created on first `python loop.py` run. Back it up if you care about the history; delete it
to start the loop fresh.
