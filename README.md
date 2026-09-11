# Claims Triage System

![CI](https://github.com/coltonmartinn/insurance-claims-system/actions/workflows/ci.yml/badge.svg)

A small auto insurance claims system built around one design decision: **the
software never decides to pay or deny a claim.** It decides who looks at it,
and how urgently.

## Why triage, not auto-decisioning

It would be easy to build a model that outputs "approve" or "deny" and call
it done. That's also a bad way to run a claims operation, and not how real
carriers actually use automation. Two things push in that direction:

- **Denials are a liability decision with a regulatory and reputational
  cost.** An insurer that auto-denies claims exposes itself to bad-faith
  claims, complaints to state insurance departments, and reversals that
  should never have gone out the door. There is essentially no version of
  "let a rules engine deny claims unsupervised" that a carrier's legal or
  claims org would sign off on.
- **Auto-approval is a different risk profile than auto-denial.** Wrongly
  fast-tracking a small, clean claim costs the company a bounded amount of
  money. Wrongly denying a legitimate claim costs a customer relationship,
  and potentially a lawsuit. The two mistakes are not symmetric, so the
  system should not treat them symmetrically.

So the system is built as a **triage layer**: every claim gets scored, and
the score routes the claim down one of two paths.

- **Auto-clear**: low claimed amount *and* a low risk score. No human ever
  looks at it. This is the only path the system can resolve by itself, and
  it only ever results in the claim being paid out on terms the policyholder
  already agreed to (their claimed amount, under their existing coverage).
- **Human review queue**: everything ambiguous, high-value, or flagged.
  An adjuster sees the full claim, the policy, and exactly which risk rules
  fired and why, then makes the actual approve/deny call.

The system's only authority is to skip review for claims that are cheap and
clean. It never has the authority to say no.

## The rules engine (the centerpiece)

`app/triage.py` runs every submitted claim through a small set of
independent, hand-written rules. Each rule looks at one concrete risk
pattern and, if present, contributes points:

| Rule | Signal |
|---|---|
| Amount-to-limit ratio | Claim is a large fraction of the policy's coverage limit |
| Policy/incident gap | Incident happened very soon after the policy started (a well-known fraud pattern: buy a policy, stage a loss) |
| Prior claims history | Policy has prior claims on file |
| Round-number amount | Claimed amount is a suspiciously round number (e.g. exact multiple of $500) |
| Type/description mismatch | Claim filed as one incident type, but the free-text description reads like a different one (e.g. filed as "collision," description says "stolen") |
| Late reporting | Long delay between the incident and when the claim was filed |

The points sum to a risk score. The score, combined with an absolute dollar
threshold, decides the recommendation:

```
score < 15  AND  claimed_amount <= $2,000   -> auto_clear
score >= 50                                  -> pending_review, high priority
otherwise                                    -> pending_review, normal priority
```

Every rule that fires is recorded, not just the final number, so
`claim.risk_explanation` is a full, human-readable audit of *why* a score
came out the way it did. An adjuster opening a claim sees the same
rule-by-rule breakdown, not a black-box number.

An optional secondary signal, a scikit-learn logistic regression trained on
a synthetic labeled dataset (`tools/train_model.py`) using the same six
features as the rules engine, is shown alongside the rules score in the
adjuster view when a trained model is present. It's explicitly a second
opinion for the adjuster to weigh, not part of the routing decision. Delete
`app/model.pkl` and the app degrades gracefully: the rules engine needs
nothing else to function.

### Model evaluation

`tools/train_model.py` holds out a stratified 25% test split and reports
precision, recall, F1, ROC-AUC, and a confusion matrix, not just accuracy,
which would be misleading here because the synthetic fraud label is
intentionally imbalanced (rare positive class), the same shape real claims
fraud data has. The report is written to `app/model_metrics.json` and
surfaced on the adjuster dashboard as a small model-monitoring card, so the
model's real-world performance is visible in the app itself rather than
buried in a training script's console output.

Worth calling out honestly: at the default 0.5 threshold, recall on the
synthetic test set is low (the model misses most positives) even though
ROC-AUC is reasonable (~0.79), a textbook precision/recall tradeoff for an
imbalanced classifier. That's acceptable *only* because this is a secondary
signal an adjuster weighs alongside the rules engine, not a gate anything
passes through automatically. A model this permissive on recall would need
threshold tuning (or a recall-oriented metric target) before it could drive
any decision on its own.

## Audit trail

Every status change, automatic or human, writes a `ClaimStatusEvent`: old
status, new status, who/what changed it (`"system"` or an adjuster's
username), a timestamp, and a reason. There is no code path that changes
`Claim.status` without writing one of these. That's what makes the claim
detail page's "Audit Trail" section a complete history rather than a
snapshot.

## Claim lifecycle

```
submitted -> auto_cleared                        (system, only for low-value/low-risk claims)
submitted -> pending_review -> approved -> paid   (human)
submitted -> pending_review -> denied             (human)
```

An adjuster can also send a claim back to normal priority from high
priority ("Lower Priority") if their initial read is that it doesn't
warrant the fast-tracked attention. That's a priority override, not a
status change, and it's still logged.

## Premium rating (quote flow)

`app/rating.py` computes an annual premium as a base rate multiplied by five
independent factors (driver age, vehicle age, prior claims, rating
territory, coverage limit), each with a plain-English explanation. It's
intentionally simple (a real actuarial rating plan has dozens of variables
and is filed with state regulators), but every dollar of the quoted premium
traces back to one named factor, shown on the quote result page.

## Underwriting risk (quote time)

`app/underwriting.py` runs the same explainable-rules pattern as claims
triage, but at the opposite end of the policy lifecycle: instead of asking
"does this claim look suspicious," it asks "how much risk is the company
taking on by issuing this policy at all." Six independent rules over driver
age, vehicle age (both new-vehicle payout exposure and old-vehicle
reliability), prior claims, territory loss history, and coverage limit sum
into a score banded **Safe / Moderate / Risky**, shown on the quote result
page right below the premium breakdown.

Like claims triage, this is advisory only: it never blocks a quote or
changes the premium. It surfaces a second, complementary risk lens (pricing
risk vs. underwriting exposure) for a human underwriter, using the same
score-ring/rule-list UI components the adjuster view uses for claims, so
both risk signals in the app read the same way.

## Reviewer mode

The adjuster sidebar is organized as a "Reviewer Mode" section with three
distinct, purpose-built views instead of one undifferentiated claim list:

- **Needs Review** (`/adjuster/queue`): every `pending_review` claim,
  sorted by risk score, highest first. This is where the actual
  approve/deny/mark-paid decisions happen.
- **Auto-Cleared** (`/adjuster/auto-cleared`): every claim the system
  cleared on its own, with no human ever weighing in. Read-only, and it
  exists specifically so an adjuster can audit what auto-clear has been
  doing rather than taking it on faith.
- **All Claims** (`/claims/`): every claim regardless of status, for a
  full submission history.

## JSON API

`app/routes/api.py` exposes the same triage logic over HTTP for
system-to-system integration (a policy admin system, a mobile app, a
partner feed); a real claims operation can't be UI-only. It shares one code
path with the web form: both call `app.claim_service.file_claim`, so there
is exactly one place that creates a claim, scores it, and writes the audit
trail, not one per interface.

Auth is a single static API key (`X-API-Key` header, configurable via the
`CLAIMS_API_KEY` env var), enough to demonstrate the pattern without
building out OAuth for a portfolio project.

```bash
curl -H "X-API-Key: dev-api-key-change-me" http://127.0.0.1:5000/api/policies/1

curl -H "X-API-Key: dev-api-key-change-me" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:5000/api/claims \
  -d '{"policy_id": 1, "incident_type": "collision", "incident_date": "2026-08-20", \
       "claimed_amount": 650, "description": "Rear-ended at a stop light."}'

curl -H "X-API-Key: dev-api-key-change-me" \
  "http://127.0.0.1:5000/api/claims?status=pending_review&min_score=50"
```

## Input validation

`app/validation.py` validates every numeric and date field submitted through
the quote form, the claim form, and the JSON API (vehicle year, coverage
limit, prior claims count, ZIP/territory, claimed amount, incident date,
date of birth): type, range, and domain-specific bounds (a claim can't be
dated in the future, a driver must be between 16 and 100, a coverage limit
has a sane floor and ceiling). A failed validator raises `ValidationError`
with a message naming the exact constraint that failed; routes catch it and
either flash the message and re-render the form with the submitted values
intact (web) or return it as a 400 JSON error (API). Nothing reaches the
database until every field passes, and nothing crashes into a raw 500 on
bad input.

## Access control

Every claim, policy, and uploaded photo is scoped to the policyholder who
owns it. A customer can only see, file against, or download attachments for
their own policies; attempting to view or act on someone else's claim
(including by tampering with a form's `policy_id`) returns a 403. Adjusters
can see everything, since that's the job. Every authenticated response also
sends `Cache-Control: no-store` so a browser can never serve a stale,
cached page from a previous login after switching accounts on the same
machine.

## Testing

```bash
pip install -r requirements-dev.txt
pytest -v
```

The suite (`tests/`) covers both layers deliberately differently:

- **Unit tests** (`test_triage.py`, `test_rating.py`, `test_underwriting.py`,
  `test_validation.py`) call the rules engines and validators directly with
  hand-built `Claim`/`Policy` objects: no database, no Flask context, fast
  and exact. Every rule's boundary conditions are pinned down individually
  (e.g. exactly where the amount-to-limit ratio crosses from 0 to 15 to 30
  points).
- **Integration tests** (`test_claims_flow.py`, `test_adjuster_flow.py`,
  `test_quotes.py`, `test_api.py`) drive the Flask test client through real
  HTTP requests against a temporary SQLite database, asserting on routing
  outcomes, audit trail contents, and role/ownership gating (a customer
  hitting an adjuster-only route or another customer's claim gets a 403;
  the API rejects a missing/wrong key).

CI (`.github/workflows/ci.yml`) runs the full suite on every push and pull
request against `main`.

## Running it locally

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

python tools/train_model.py    # optional: trains the secondary ML signal + eval report
python seed.py                 # creates instance/claims.db with sample data
python run.py                  # http://127.0.0.1:5000
```

Log in as `adjuster1` or `adjuster2` (role: adjuster) to see reviewer mode
and the dashboard, or as any seeded customer to file/track claims. The
login page lists every seeded user; there's no password.

## Running it with Docker

```bash
docker compose up --build
```

Builds the image, trains the model, seeds the database, and serves the app
at `http://127.0.0.1:5000`, no local Python environment needed. Seeded
data persists across restarts in a named volume (`instance_data`).

## Stack

- **Flask**: server-rendered templates, no frontend framework
- **SQLAlchemy / SQLite**: `Policyholder`, `Policy`, `Claim`,
  `ClaimStatusEvent`, `User` (see `app/models.py`)
- **scikit-learn**: optional logistic regression secondary signal, with
  held-out evaluation (see Model evaluation above)
- **pytest**: unit + integration test suite, run in CI on every push
- **Docker**: one-command reproducible run
- Session-based pseudo-auth: a `role` field (`customer` / `adjuster`) on
  `User`, no passwords. This is a portfolio project, not a production auth
  system (see `app/auth.py`).

## Project layout

```
app/
  models.py            Data model + claim status lifecycle
  rating.py             Premium calculation for the quote flow
  underwriting.py        Explainable underwriting risk estimate at quote time (Safe/Moderate/Risky)
  validation.py          Numeric/date validators shared by the web forms and the API
  triage.py             Rules-based risk scoring (the centerpiece)
  features.py           Feature extraction shared by triage.py and ml.py
  ml.py                 Optional logistic regression secondary signal
  claim_service.py      Shared intake+triage+audit logic used by the web form and the API
  auth.py               Minimal role-gated pseudo-auth
  routes/               Flask blueprints: quotes, claims, adjuster, auth, dashboard, api
  templates/, static/   Server-rendered views
tests/
  test_triage.py, test_rating.py, test_underwriting.py, test_validation.py   Unit tests, no DB
  test_claims_flow.py, test_adjuster_flow.py, test_quotes.py, test_api.py
                                          Integration tests via the Flask test client
tools/
  train_model.py         Trains app/model.pkl on synthetic data + writes model_metrics.json
seed.py                   Populates the database with sample policies/claims
run.py                    Dev server entry point
Dockerfile, docker-compose.yml   One-command containerized run
.github/workflows/ci.yml         Runs the test suite on every push/PR
```

## What's intentionally out of scope

- Real authentication (passwords, hashing, sessions beyond a cookie)
- A production-grade actuarial rating plan
- Any code path that lets the system deny a claim
- OAuth/JWT for the API (a static key demonstrates the pattern; a real
  integration would need per-partner credentials and scoped permissions)
