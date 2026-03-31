# stripe-recorder

Create fake stripe checkout flows and then record the webhook callbacks on disk. These can then be used in testing harnesses to replay exact stripe metadata.

## Setup

Make sure you have the local stripe CLI set to the correct remote account:

```bash
stripe login
```

## Getting Started

```bash
stripe listen --forward-to localhost:5084/webhook
```

```bash
uv run uvicorn stripe_recorder.main:app --reload --port 5084
```

Access `http://localhost:5084` in your browser to start a new record session. We capture a new session for as long as the webapp is running, so make sure you close and re-launch it if you want to generate webapp logs for multiple functions.

Use a [fake](https://docs.stripe.com/testing?testing-method=card-numbers#visa) credit card:

```
Number: 4242424242424242
CVC: Any 3 digits
Date: Any future date
```
