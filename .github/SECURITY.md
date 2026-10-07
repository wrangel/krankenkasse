# Security Policy

Grundversicherungsrechner is a calculation tool for Swiss basic health
insurance, maintained by one person. This policy exists so that a genuine
security finding reaches me privately instead of arriving as a public issue.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/wrangel/grundversicherungsrechner/security/advisories/new)**

That opens a private advisory visible only to me, so the problem can be fixed
before it is described anywhere public.

If you would rather not use GitHub, email
`contact@grundversicherungsrechner.anonaddy.com` with "security" in the
subject.

## What this application holds

Worth knowing before you look for a data breach: there is nothing to breach.
The app has no accounts, no login, no database and no server-side storage. What
you type — postcode, age, expected healthcare costs — lives in the Streamlit
session for as long as the tab is open and is never written anywhere. Nothing
is sent to third parties; usage statistics are switched off.

The only data the server holds is the BAG's public premium file, cached on
disk. If that ever changes, this section changes with it.

## What helps

- The URL or the file and line, and what an attacker could actually achieve
- Steps to reproduce, ideally the smallest case that shows it

A wrong number is a correctness bug, not a vulnerability — those are very
welcome, but as a normal issue or by email rather than a private advisory.

## What to expect

This is a side project, not a staffed product. I will acknowledge reports as
soon as I reasonably can and fix what is genuinely exploitable, but I am not
promising a response deadline I cannot keep. There is no bug bounty.

Reports that are clearly automated scanner output with no demonstrated impact
will usually be closed without a detailed reply.

## Scope

In scope: this repository's source, and the deployed instance at
<https://grundversicherungsrechner.ch>.

Out of scope: the third-party services this depends on — the BAG's data
delivery via opendata.swiss, Docker Hub, Streamlit itself, and Let's Encrypt —
which should be reported to those vendors directly.

Please do not run automated scanners or load tests. It runs on a small home
server; a scan is indistinguishable from an outage.

## Versions

There are no released versions to support. The site runs whatever is currently
on `main`, deployed as a Docker image, so fixes apply to the live site rather
than to a version range.
