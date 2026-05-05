# Demo inputs

`inputs.json` is a typical mid-stage B2B-SaaS profile, easy to sanity-check:

| Input | Value |
|---|---|
| ARPU | $200 / month |
| Customer churn | 3 % / month |
| Net revenue expansion | 0.5 % / month |
| Gross margin | 78 % |
| CAC | $1,500 |
| Inference cost | $0 (non-AI product) |

## Run it

```bash
python skills/ltv-cac/run.py --inputs skills/ltv-cac/examples/inputs.json \
  --out-dir /tmp/ltv-cac-demo

open /tmp/ltv-cac-demo/ltv_cac_workbook.xlsx
```

## Expected ballpark

- **Skok basic LTV** = 200 × 0.78 / 0.03 ≈ **$5,200**
- **NDR-adjusted LTV** = 200 × 0.78 / (0.03 − 0.005) = **$6,240**
- **LTV/CAC** (Skok) ≈ **3.47** → 🟢 healthy (Skok 3:1 sweet spot)
- **CAC payback** ≈ 9.6 months
- **Annual NDR** ≈ 1.030^12 ≈ 97% (slight contraction since churn > expansion)

## Try the AI-adjusted view

Bump inference cost to $30/cust/mo to see how AI economics break the textbook:

```bash
python skills/ltv-cac/run.py \
  --arpu 200 --churn 0.03 --cac 1500 \
  --gross-margin 0.78 --expansion 0.005 \
  --inference-cost 30 \
  --out-dir /tmp/ltv-cac-ai

open /tmp/ltv-cac-ai/ltv_cac_workbook.xlsx
```

You'll see the AI-adjusted LTV drops by ~19% and the verdict flags inference cost as the key sensitivity.
