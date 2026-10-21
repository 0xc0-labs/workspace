# Delivery

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

## Repos and policies

`infrastructure` and `.github`: `main` only, PR required, apply behind manual
approval. Applications: each decides whether it has a staging environment; one
that does promotes staging→prod with the same digest, never a rebuild, and one
that does not releases every push to `main` (Application delivery, below).
ArgoCD points at `gitops/bootstrap/prod/`, which deploys `platform/` and
`apps/`. `gitops` merges through a merge queue (Application delivery, below).

## Application delivery

How an application's code goes from a commit to staging and prod, and how a
frontend and the backend it reads stay in step (operator decisions,
2026-10-10 and 2026-10-11; workspace#68). It applies to `artistlabco.com`,
which has a staging environment, and to `offby1.cc`, which has none (below);
and to `payload`, which has one, until it is retired.

**Trunk-based, versioned from Conventional Commits.** `main` is the trunk:
short-lived branches, squash merges, no release branches. Every merge to
`main` builds an image, `sha-<7>`. In an application with staging, it also
cuts the next release candidate, `vX.Y.Z-rc.N`, a tag on that commit whose
version `git-cliff` computes from the Conventional Commits since the last
release (`feat` a minor, `fix` a patch, `!` a major), and every rc goes to
staging. Its release, `vX.Y.Z`, is a `workflow_dispatch` that the operator or
the orchestrator runs: it takes the rc that staging runs, read from `gitops`,
and makes it a GitHub Release on the same commit, with its changelog. A
hotfix is a fix on `main`, its rc and a release. Versions start at `0.1.0`;
while in 0.x a breaking change bumps the minor, which npm's caret already
treats as breaking. `1.0.0` is cut by hand when the first frontend reaches
prod.

**An application with no staging releases on every push to `main`**
(operator decisions, 2026-10-12; workspace#140). `offby1.cc` is one, a
landing page with no data and no backend, whose image was pinned in `gitops`
by hand from each build's summary (.github#61). It takes the flow above
without staging and without release candidates: with no staging to try an
rc in, every push to `main` is a release, `vX.Y.Z` by the same `git-cliff`
count, with its tag on that commit, its GitHub Release and changelog, the
image's digest tagged with it, and prod's PR in `gitops`. As with staging,
merging that PR is prod's approval, and no one pins a digest by hand. Its
checks and image run on GitHub's runners, and its release, which logs in to
Vault for the promoter's token, on the self-hosted ones (below). How a repo
calls it is in the
[`.github` README](https://github.com/0xc0-labs/.github/blob/main/README.md#application-repos).

**Promotion is a PR in `gitops`, and the image is never rebuilt.** An rc and a
release each tag the same digest with their version, and open a PR in `gitops`
that changes only the environment's pin in its `kustomization.yaml`: the
`images:` entry, tag and digest, and the version beside it, which `gitops`' CI
checks against the tag. Staging's PR is set to merge itself once its checks
pass, through `gitops`' merge queue (below). Prod's is the operator's merge,
and that merge is prod's approval: GitHub Free gives private repositories no
environment reviewers, wait timers, environment secrets or rulesets. Rolling
back is reverting that PR.

**An app repo may build a second image from a subdirectory** (operator
decision, 2026-10-20; workspace#203): `ghcr.io/<repo>-<suffix>`, from
`<suffix>/Dockerfile`. A site's Strapi is the first: `artistlabco.com`'s
`cms/` builds `ghcr.io/0xc0-labs/artistlabco.com-cms`, beside the front's
own image. Both are built from the same commit and released under the
repo's one version, in one promote PR that moves both pins, so a site's
front and its CMS are never at different versions. The shared workflows in
`.github` build each.

**`gitops` merges through a merge queue** (operator decision, 2026-10-12;
workspace#139). Its ruleset requires a branch to be up to date with `main`,
and auto-merge does not update one, so a staging PR that another merge
overtook stayed open (.github#88). With a queue, auto-merge enqueues the PR,
and the queue builds it on top of the latest `main` and of the PRs ahead of
it, runs the required checks on that, and merges it; a PR that does not
apply cleanly leaves the queue and waits for a person. A person's PR to
`gitops` goes through the queue too. GitHub Free offers a queue to an
organization's public repositories, which `gitops` is. Not a workflow that
updates the PR with the promoter's token: that token comes from Vault, which
only the self-hosted runners reach, and `gitops` is outside their group,
while a branch updated with `GITHUB_TOKEN` triggers no checks. Not dropping
the up-to-date rule for `gitops`: it would merge a PR whose checks ran on an
old base.

**Two GitHub Apps open the bots' PRs, and their keys never leave Vault.**
`0xc0-labs-promoter` is installed on `gitops` alone, with contents and pull
requests; `0xc0-labs-renovate`, on every repo. Their private keys are
imported into Transit (`github-promoter-app`, `github-renovate-app`), as the
runners' is: a job signs its App's JWT through Transit with its repo's JWT
role, and exchanges it for an installation token narrowed to the repo and
the permissions it needs. Two Apps rather than one, so that an
application's CI can mint write access to `gitops` and nothing else. The
`issue` check lets a PR through without a linked issue when one of the two
Apps opened it: it names the release or the dependency it moves, and the
board tracks the work of people and sessions.

**Only the jobs that log in to Vault run on the self-hosted runners;
everything else runs on GitHub's** (operator decision, 2026-10-12;
workspace#138). Two Next.js builds on one CI VM, 2 cores and 4 GB shared by
its two runners, hang it, and the node has no memory left to give it: 62 GB,
60 of them allocated to VMs (infrastructure#235). A private repository's
standard GitHub runner has 2 CPUs and 8 GB to itself. So an application's
checks and image, and `packages`' checks and releases, run there: none of
them logs in to Vault. The jobs that do stay on the self-hosted runners, as
Vault is reachable only from inside: an application's rc and release, for
the Apps' tokens, and the pipelines of `infrastructure` and `vault`. The
runner group admits those repos, `offby1.cc` among them for its release, and
the reusable workflows they call. GitHub Free gives private repositories
2,000 minutes a month and, with no payment method, blocks their jobs once
they run out instead of billing them: `payload` used about 320 from
2026-10-01 to 10-12, hung builds included. A dependency's code runs where it
is installed and built: on GitHub's runners, beside the tokens that push an
application's image and publish the org's packages, and on the machines of
people and sessions. An image or a package it poisons reaches the cluster,
or every application that pins it. So a dependency version is taken only
once it is three days old (`minimumReleaseAge`, in Renovate and in pnpm),
and pnpm runs the build scripts of the packages it is told to (`allowBuilds`,
which replaced `onlyBuiltDependencies` in pnpm 11) and no others. Which
runner each job asks for is in the
[`.github` README](https://github.com/0xc0-labs/.github/blob/main/README.md).

**Integration tests bring their own PostgreSQL, from mise** (operator
decision, 2026-10-12; workspace#93). It was decided while the checks ran on
the self-hosted runners, which have no Docker and where nothing may listen on
the network (`infrastructure`'s `docs/zones.md`, invariant 10), and it
stands now that they run on GitHub's (above). An application's tests start a
throwaway server themselves: PostgreSQL from conda-forge through mise
(`conda:postgresql`, prod's major, every package checksummed in `mise.lock`
for Linux and macOS), `initdb` in a temporary directory, no TCP port
(`listen_addresses=''`), a Unix socket in that directory, the repo's
migrations, and everything removed when the tests end. The same `pnpm test`
runs on GitHub's runners and on a Mac. `node-check` only runs it, with the
tools the caller names. Not Debian's package (trixie ships 17, and 18 would
bake a third-party repo into the runner image), not PGlite (no Payload
adapter, and it does not behave as a server under concurrency), not a
service container: it ties the tests to the workflow that starts it, where
the same `pnpm test` must run on GitHub's runners and on a Mac.

**Staging is a second environment of the same application.** In `gitops`,
an application is one folder with one directory per environment:
`apps/<app>/prod/` and, when it has staging, `apps/<app>/staging/`, with
what both share in `apps/<app>/base/`. An application with one environment
keeps all of it in `prod/`; when it gains staging, the shared part moves to
`base/`. The `apps` ApplicationSet makes an Argo CD application of each
environment: prod keeps the application's name and namespace, `<app>`;
staging is `<app>-staging`. Staging has its own database on the shared
server, its own bucket, and its own `apps/<app>-staging/` path in Vault,
which the `apps` role already covers. It is reached over WARP, at
`<app>-staging.int.0xc0.cc` (a front's can also be published behind Access:
[network](network.md)), and is observed as prod is, its signals tagged
`deployment.environment=staging`. Its data is a seed versioned in the
application's repo: test content and users, reset when needed; later, once
prod has content, a copy of prod without its users, run by the operator.
Applications without staging keep everything in `prod/`: `offby1.cc`, with
its pin written by its releases (above). Each staging
environment doubles its application's memory in the cluster. An
application deployed once per site keeps its common base in
`apps/<app>/base/` and one overlay per site at `apps/<app>/<site>/`, in
the namespace `<app>-<site>`, `<site>` being the site's name as a
session's is, dots to dashes (operator decision, 2026-10-13;
workspace#171). Mautic is the first: `apps/mautic/artistlabco-com/`, in
`mautic-artistlabco-com`.

**Migrations run before the new version, from the same image.** An Argo CD
Sync hook in wave 1, before the Deployment in wave 2, runs `payload migrate`
with the digest being deployed: when it fails, the sync stops there and the
running version keeps serving. Not a PreSync hook: on an application's first
sync it runs before its namespace and secrets exist, and never finishes
(gitops#142). Every
migration is expand and contract, so the previous version works on the new
schema and rolling back the image is safe.

**The frontends render on the server, each as a BFF.** A frontend is a
Next.js application in the cluster and a backend for frontend: its own
server is the only backend its pages talk to (operator decision, 2026-10-13;
workspace#168). The browser never calls the CMS, and what a page needs from
it, a form, a search or a member's own page, goes through the frontend's
server, which calls the site's Strapi on its Service in the same namespace.
It reads with an API token kept in Vault at `apps/<namespace>/cms-client`,
and Strapi's public role grants nothing. The frontend writes too, its
forms' submissions and its members' actions. For a member's own actions it
also passes that member's token, which Strapi issues and the frontend keeps
in an httpOnly cookie on its own domain, so no script in the browser reads
it and Strapi decides what the member reaches. Stripe's webhooks need a
public URL, and Strapi's hostname serves the admin alone, so they reach a
route of the frontend, which forwards each one raw to Strapi; Strapi
verifies its signature, which Stripe computes over the exact body.
Staging's frontend reads staging's Strapi. The build never reads the CMS,
and nothing that differs between environments is baked into the image (no
`NEXT_PUBLIC_` value that does), so one image serves both. Outside, only
the uploaded files are public, from R2 (workspace#88), and the admin,
behind Cloudflare Access ([platform](platform.md)); the API and
authentication stay inside. A public CMS API stays
[discarded](../discarded.md). Payload's fronts call it through their
servers the same way while it runs.

**Observable as every application is, in both environments.** The rule in
[platform](platform.md)
(workspace#52) holds for each environment and for the migration Job, and the
delivery adds what ties the signals to it. Every signal carries
`service.name`, the application; `service.version`, the version the
environment runs, `vX.Y.Z-rc.N` in staging and `vX.Y.Z` in prod, set beside
the image in the environment's `kustomization.yaml`; the commit, baked into
the image when it is built, so a trace leads to the code even from an image
run outside `gitops`; and `deployment.environment`, from the environment's
directory. The same image is an rc in staging and a release in prod, so its
version cannot be baked into it. A request is one trace from the browser to
the database: RUM starts it and sends `traceparent` to the frontend's own
origin only, the frontend's server continues it, its call to the CMS carries
it, and the CMS's spans reach PostgreSQL. Logs are JSON with the trace and
span IDs, so OpenObserve opens a request's logs from its trace. The
frontends instrument with OpenTelemetry through Next.js's instrumentation
hook, and a site's Strapi, a Node service, through `@0xc0-labs/observability`
and its inbound spans (packages#31). Each environment's namespace is
admitted in the collector's `otlp-from-senders`.

**Images of private repositories stay private.** The cluster pulls them from
GHCR with a read-only token at `apps/shared/ghcr-pull` in Vault, which Vault
Secrets Operator turns into an `imagePullSecret` in each namespace that
needs one. Images of public repos stay public, as today.

**A backend in a repo of its own publishes a versioned contract.** A
site's Strapi does not: it ships with its front, in the same repo, version
and promote PR (above), so the two have no contract between them and no
order to enforce. `payload`, in a repo of its own, does, until it is retired:
it publishes its generated types as `@0xc0-labs/payload-types`, a private
npm package in GitHub Packages, with the version of the rc or release that
built it: an rc publishes `X.Y.Z-rc.N` under the `rc` dist-tag, a release
`X.Y.Z`. A frontend pins it in its `package.json`, so a breaking change in
the backend fails the frontend's build, never its users. The backend changes
by expand and contract: it adds (a minor) and deploys, the frontends adopt,
and it removes (a breaking release) only once no deployed frontend uses what
goes. `@0xc0-labs/payload-types` and `@0xc0-labs/payload-client` are retired
with Payload (operator decision, 2026-10-20; workspace#203).

**CI enforces the order between a frontend and a backend of another repo:**

1. A frontend release cannot depend on a prerelease of the contract, so the
   backend always reaches prod first.
2. Promoting a frontend to an environment fails unless that environment
   already runs a backend version at least as high as the one the frontend
   depends on, read from `gitops`.
3. Later: a breaking release of the backend does not reach prod while a
   frontend in prod still depends on the previous one.

**Code that two repos need alike lives once, in a versioned package**
(operator decision, 2026-10-12; workspace#121). It is extracted when a second
repo needs the same code, or a behaviour that must stay alike everywhere:
observability, security headers, log format, health checks. Code that only
looks alike but changes for different reasons, a line or two, and
configuration stay in each repo. The packages live in one repo,
`0xc0-labs/packages`, a directory each (`packages/<name>`). Each is published
as `@0xc0-labs/<name>` to GitHub Packages, private, with its own version and
its own release, through a reusable workflow in `.github`. An app pins the
version in its `package.json`, and Renovate, once it runs, bumps it as any
other dependency. The first is `@0xc0-labs/observability`: OpenTelemetry for
Node and Next.js, with the resource attributes, the OTLP exporter and the
kube-probe propagator that payload#30 wrote. A Strapi capability is a
generic plugin of its site's `cms/src/plugins/<capability>`, and moves to
`@0xc0-labs/strapi-plugin-<capability>` as it is, without a rewrite, when a
second site needs it (operator decision, 2026-10-20; workspace#203). Who
notices a candidate, and who decides, is in [how we work](how-we-work.md).

**Renovate keeps every repo's dependencies current.** It runs as a scheduled
workflow in `.github`, on the self-hosted runners, with
`0xc0-labs-renovate`'s token. A preset in `.github` holds what is common:
the schedule, the grouping, Conventional Commit titles (`chore(deps): …`),
digests pinned, and nothing merged by itself. Each repo opts in with a short
`renovate.json` that extends it and adds its own. Being self-hosted, it runs
`mise lock` after it bumps a tool, so `mise.lock` stays in step. It leaves
alone the pins of the org's own images in `gitops`: promotion owns them.
