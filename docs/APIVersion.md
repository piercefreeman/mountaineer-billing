# API Version

Stripe has two relevant notions of API version: the version configured on your Stripe account, and the version used by the installed `stripe` Python package. For consistency we refer to these as the `AccountVersion` and the `LibraryVersion`, respectively.

Webhook notifications from Stripe to your application will use the `AccountVersion`. Requests made through the local library use the `LibraryVersion`, which is determined by the installed `stripe` package. If you keep stripe unpinned, that will usually mean the latest library-supported version. This model is intuitive for outbound calls: if your local function calls typecheck and validate against the installed library, Stripe will accept that request shape on the remote end.

Receiving data is trickier, because inbound payloads may arrive in a shape that the local `stripe` package no longer models or validates. We address that by shipping our own [models](./Static-Analysis.md), which preserve older Stripe versions for analysis and validation. For _outbound_ requests, though, we defer to the installed Stripe library defaults, so pushed data follows the `LibraryVersion` rather than the `AccountVersion`.
