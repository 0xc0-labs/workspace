# Platform

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

## Stack

Proxmox VE 9 on a Hetzner dedicated server, 2× NVMe in mdadm RAID 0 ·
PBS to a Hetzner Storage Box · RustFS for the OpenTofu state · Cloudflare R2
for the applications' files · Resend for their email · Cloudflare Free
(Tunnel, Access, WARP) · Packer + OpenTofu + Ansible · GitHub Actions with
self-hosted runners · RKE2 on Rocky Linux · HAProxy + keepalived · ArgoCD ·
Traefik with the Gateway API · CrowdSec · cert-manager with Let's Encrypt ·
external-dns · Longhorn · Headlamp · Vault · OpenObserve with the
OpenTelemetry Operator · Hetzner Rescue as the emergency path.

**ArgoCD is installed with the cluster, and everything else in the cluster by
ArgoCD** (operator decision, 2026-09-29, replacing the OpenTofu root of
2026-09-27). The Ansible playbook that brings RKE2 up also writes ArgoCD's
`HelmChart` and its root `Application` into RKE2's manifests directory, and
RKE2's own helm-controller installs it. An OpenTofu root would have needed
Ansible to have run first, and the admin kubeconfig outside the servers;
this needs neither. RKE2's helm-controller keeps managing ArgoCD itself, so
two controllers never fight over it. From there ArgoCD deploys every other
component (Longhorn, Traefik, CrowdSec, Vault, monitoring, applications) from
the `gitops` repo, which is public: no repo credentials. A private repo would
get a read-only GitHub App, its key from Vault through Ansible the same way.

**Vault runs in the cluster** (operator decision, 2026-09-24). A running
cluster never needs Vault to start: the RKE2 token and ArgoCD's admin password
are already in files only root reads on the servers, written there by Ansible,
which reads them from Vault (`ci/infrastructure/*`). ArgoCD deploys Vault, and
the components take their secrets from it through Vault Secrets Operator. No
secret lives in `gitops`, not even encrypted. Vault is unsealed by hand after a
restart. A cluster built from nothing needs Vault restored first, from PBS:
an accepted risk ([accepted risks](../accepted-risks.md)).

**Vault's shape** (at the operator's request, 2026-09-30; gitops#33): three
servers in HA over integrated storage (Raft), one per RKE2 node, each on a
Longhorn volume. Shamir seal: the keys
live in the operator's password manager and offline, never in the cluster or
any repo. It is on the WARP-only path, `https://vault.int.0xc0.cc`; Traefik ends
TLS, and inside the cluster the API is plain HTTP behind NetworkPolicies
(Raft's port is TLS with Vault's own certificates; there is no TLS between
pods on the API). No agent injector: Vault Secrets Operator reads it. The
init and unseal runbook is `gitops/platform/vault/README.md`.

**OpenObserve for metrics, logs and traces** (operator decision, 2026-10-01;
gitops#44), the lightest way to have all three: one backend, single node, on
a Longhorn volume, with its own dashboards and alerts, and PromQL for the
metrics. It replaces Prometheus + Grafana, and lifts the discard of logs and
traces. The OpenTelemetry Operator runs the collectors: one agent per node
for every container's logs and the nodes' and pods' metrics, and one gateway
for traces over OTLP, Kubernetes events, and every Prometheus target, which
each component declares with a ServiceMonitor and its target allocator finds.
The control plane's metrics (etcd, scheduler, controller manager) are exposed
on the RKE2 servers for it. Retention is 30 days. The open-source edition
has no SSO: its own users, on the WARP-only path, `https://o2.int.0xc0.cc`.

**Every application is observable from the day it is deployed** (operator
decision, 2026-10-03; workspace#52). The change that deploys it ships all of
this, never a follow-up:
- **logs:** to stdout or stderr, with a level the collector can parse. A log
  the application writes to a file is followed onto stdout by a sidecar
  (Mautic's).
- **metrics:** at least Traefik's per-route traffic and the kubelet's per-pod
  resources, on the "Apps" dashboard; its own endpoint, with a ServiceMonitor,
  when it has one.
- **traces:** OTLP to the collector's gateway, joined to Traefik's trace
  through `traceparent`. That means egress to the gateway, and the namespace
  admitted in the collector's `otlp-from-senders`.
- **RUM, when it has a frontend:** OpenObserve's browser SDK, sending through
  the application's own name (`/rum/v1/default/rum`, POST only, rate limited,
  with a ReferenceGrant to OpenObserve). It stores nothing on the visitor's
  browser and records no session replay, so it needs no consent banner. The
  client token is public by design, and lives in Vault like any credential.

**Vault Secrets Operator, not External Secrets Operator** (operator decision,
2026-09-30). Vault is the only backend, so ESO's reach across backends buys
nothing, while VSO renews dynamic secrets' leases (the data services'
short-lived credentials) and restarts what uses a secret when it changes,
with no Reloader beside it. No global access: each namespace brings its own
`VaultAuth`, bound to a Kubernetes auth role named after it, which reads only
its own paths.

**Secrets are laid out by trust boundary** (operator decision, 2026-09-30):
one KV v2 engine each, `platform/` (the shared services), `apps/` (the
applications) and `ci/` (the pipelines), with paths `<engine>/<owner>/<name>`,
the owner being the namespace or the repo. A fourth, `ops/`, holds what only
people use, UI logins and passwords in clear, and no machine has a policy on
it (operator decision, 2026-10-02). A credential both need gets a form for
each: the machine the bcrypt or the htpasswd line, the person the password. A
secret belongs to the service it is for, not to its reader: ArgoCD's is
`platform/argocd/admin`, granted by name to infrastructure's CI, which writes
it into the cluster. Keys inside are `snake_case`, and
every secret carries `owner` and `rotated_at` metadata. A policy scopes to one
owner; the `vault` repo defines engines, roles and policies, never values. A
secret more than one consumer uses is not copied: it lives once, at
`<engine>/shared/<name>`, and each consumer's policy grants it by name
(operator decision, 2026-09-30).
There are no dynamic engines (`pki/`, `database/`); one is added when
something needs it. `apps/` has one Kubernetes auth role, `apps`, for every
namespace labelled `vault.0xc0.cc/apps`, and one templated policy, which
reads the path of the namespace the login comes from instead of one policy
each (noted 2026-10-01), plus `apps/shared/openobserve-rum` by name. The
full standard is in the `vault` repo's README.

**Vault is configured with OpenTofu from its own repo, `vault`** (operator
decision, 2026-09-30; .github#6): auth methods and roles, policies, secret
engines. It is downstream of `gitops`, which deploys Vault, so the order stays
linear: `.github → infrastructure → gitops → vault →` the applications
(`offby1.cc`, `artistlabco.com`, and `payload` until it is retired).
Its CI logs in with the job's GitHub OIDC token (JWT auth,
`hashicorp/vault-action`): no Vault credential is stored. A PR plans
read-only from any ref (role `terraform-plan`); only `main`, inside the
`production` environment that waits for the operator, writes (role
`terraform`). Neither policy touches a stored secret. The CI VMs
reach Vault on the internal VIP (`ci → platform: 443`).
The CI can only log in once its auth method and roles exist, so **the first
apply of `vault` is local**: the operator runs it once, over WARP, with the
root token (operator decision, 2026-09-30). With `.github`'s bootstrap (its
README, Bootstrap), it is one of the two exceptions to nothing being applied
from the laptop; every change after them goes through the pipeline. The root
token is kept, outside Vault, with the unseal keys (operator decision,
2026-10-04).

**The ingress is Traefik, with the Gateway API, and the WAF is CrowdSec**
(operator decision, 2026-09-29). open-appsec was the plan, and it was set aside:
every Kubernetes integration it has runs on something retired or unmaintained
(ingress-nginx, retired in March 2026; Kong, with no free images since 3.10;
Istio 1.23-1.26 and Envoy 1.32-1.34, all end of life; APISIX on unmaintained
etcd images). Cloudflare Free covers DDoS and the most exploited CVEs; what it
leaves, application attacks on public apps without Access, is CrowdSec's:
Traefik's bouncer checks every request against CrowdSec's AppSec component
(virtual-patching rules, no CRS to tune) and its community blocklist, shared in
return for the attacking IPs, never request contents. The load balancers stay
layer 4, with no WAF of their own. open-appsec can be reconsidered for the
public applications.

**Longhorn is the cluster's storage** (operator decision, 2026-09-29): the
default `StorageClass`, three replicas on different nodes, on each RKE2 node's
two data disks, the agents' included. It has no backup target of its own: **PBS backs the VMs up whole**,
data disks included, and that is what the timed restore tests.

**The applications' files live in Cloudflare R2** (operator decision,
2026-10-11; workspace#88), the one object store for them: uploads and
anything else an application keeps as objects. Longhorn keeps the databases
and what needs a filesystem; RustFS keeps only the OpenTofu state. One bucket
per application and environment, named `<namespace>-<purpose>`
(`artistlabco-com-media`, `artistlabco-com-staging-media`), created by
`infrastructure`'s Cloudflare root with a western Europe location hint, its
`r2.dev` URL off. A bucket whose files are public is attached to a hostname
of ours (`media.artistlabco.com`) and served through Cloudflare's cache,
with `nosniff` and a `default-src 'none'` CSP, so the application behind it
need not be public. Staging's buckets have no hostname: the application
serves their files, over WARP. Each application reads its bucket with an R2
token scoped to that bucket, created by the operator in Cloudflare and kept
in `apps/<namespace>/`, or, for a site's Strapi, entered in its admin and
kept where its integrations' keys are (below). With no files on disk, a
volume no longer ties an application to one replica or to stopping before
each rollout. R2 is free up to 10 GB, with no egress fees, and about 15 USD
per TB beyond. It keeps no copies of its own, and nothing copies it elsewhere
([accepted risks](../accepted-risks.md)).

**The applications send email through Resend, over SMTP** (operator
decision, 2026-10-12; workspace#92): `smtp.resend.com:587` with STARTTLS,
region `eu-west-1`, never a provider's own API or DSN scheme, so moving to
Amazon SES once the volume asks for it (Mautic's campaigns, or more than the
free plan's 100 a day) changes credentials and DNS, never code. The
platform's own mail (a CMS admin's invitations and password resets, internal
tools) goes out from `0xc0.cc`; a site's mail to its public, from that
site's domain, verified on its own: a site never sends as `0xc0.cc`, nor the
platform as a site. Each sending domain's DKIM, its MAIL FROM subdomain
(`send.`, so the apex keeps Cloudflare Email Routing's MX and SPF) and its
DMARC record are OpenTofu's, in `infrastructure`. Each application and
environment sends with its own key, sending access only and limited to its
domain, created by the operator in Resend and kept at
`apps/<namespace>/email`. Staging sends real
mail, all of it to the operator's inbox (`EMAIL_REDIRECT_TO`, from Vault),
marked as staging's: nothing reaches a test address or a real user.

**Non-negotiable: a tested restore.** If the RTO is not measured in writing,
it is not tested.

**One shared MariaDB for the applications that need MySQL** (operator
decision, 2026-10-02; gitops#71): one server in `platform/mariadb`, one
database and one user per application, never a server per application.
MariaDB over MySQL: fully GPL, lighter at rest, and both Mautic and WordPress
support it. A plain StatefulSet from the official image, **no operator**: it
costs memory the cluster does not have to spare. PBS's backup restores the
server whole, every database at once, so a nightly logical dump per database
lets one application be restored alone. An application that needs another
engine version gets its own server, as the exception.

**One Mautic per site that turns on marketing automation** (operator
decision, 2026-10-13; workspace#171), not one shared instance as decided on
2026-10-02 (gitops#73): a contact can belong to several sites, and one
Mautic cannot keep each site's contacts, consent and unsubscribes apart;
each site's contacts belong to that site's business; and Mautic has one
mailer per instance, so a shared one cannot send with each domain's own
key. The shared instance at `mautic.0xc0.cc` is retired. Every instance is
deployed from one common base in `gitops`, with its own database in the
shared MariaDB and its own sending key on its site's domain (email,
above). In each, the official image's three roles (web, cron, worker) run
as containers of one pod, sharing one Longhorn RWO volume, so there is no
RWX volume and no NFS share-manager. What contacts reach is public on the
site's domain, at `mautic.<site domain>`. Every admin path (`/s`, the
installer, the API) answers 403 there, with no hint of the internal name
(operator decision, 2026-10-02; gitops#78), and is reached only at the
instance's own name under `int.0xc0.cc`, WARP only, so its login is never
on the internet. Each runs from `apps/`, under the applications' narrower
`AppProject`.

**Each site runs its own Strapi, in its own repo** (operator decision,
2026-10-20; workspace#203): Strapi 5, in `cms/` beside the site's front,
deployed in the site's namespaces with its own database, buckets, keys and
admin. It replaces the one multi-tenant Payload instance (operator decision,
2026-10-09; workspace#64), the backend of several fronts through Payload's
multi-tenant plugin: a client who buys a site cannot manage Payload's admin,
and Strapi's is friendlier and can be branded. The multi-tenant Payload is
[discarded](../discarded.md). `artistlabco.com`'s is the first Strapi, due
before ARTIST LAB's launch on 1 November; Payload keeps running until
workspace#204 retires it, once that Strapi runs in prod. A site's front calls
its Strapi inside the cluster, as its BFF ([delivery](delivery.md)), with an
API token: Strapi's public role grants nothing, and the API is never public.
Only the uploaded files are public, from R2, and the admin: the public
hostname serves the admin alone, at `cms.<site domain>` in prod and
`cms-staging.<site domain>` in staging, behind a Cloudflare Access
application, so the editors need no WARP, unlike Mautic's admin (operator
decision, 2026-10-21; workspace#203). The application and its policy are
OpenTofu's, in `infrastructure`, and its viewers are managed in Cloudflare's
dashboard, as a front's staging's are ([network](network.md)). Strapi's
telemetry is off.

**A site's Strapi is the whole backend of its site** (operator decision,
2026-10-13; workspace#168, carried to Strapi 2026-10-20; workspace#203), not
only its content: members, subscriptions, forms and leads, and gated
resources too. **Every capability is generic**: a site's Strapi takes each one
from a plugin with nothing of the site in its code, either reused from Strapi
or its community, pinned and wrapped if needed, or one of ours in
`0xc0-labs/packages`, `@0xc0-labs/strapi-plugin-<capability>`
([delivery](delivery.md)) (operator decision, 2026-10-21; workspace#202). The
site's `cms/` holds only its configuration, its own content types and blocks,
and the files of its admin views and roles. What is the site's, its copy,
plans, roles and IDs, is set in the admin or is content, so a new site that
uses what exists needs no new code. **A site's Strapi carries the capabilities
it uses and no others**: with one Strapi per site there is no tenant to switch
a capability on for, which replaces the per-tenant switch of 2026-10-13
(workspace#171), and some sites will not need one (marketing automation and
its Mautic, for one). **A capability requires only what it cannot work
without** (operator decision, 2026-10-16; workspace#184): anything gated by
identity (resources, videos, community roles) requires `members`, and nothing
more. **A membership says who belongs to a site, never who pays** (operator
decision, 2026-10-18; workspace#197): payments are read from the subscriptions
when access is decided. Where the site uses `subscriptions`, a gated record
names its audience: every member, every subscriber, or some plans, as Ghost's
visibility levels do (members, paid members, specific tiers), and community
roles follow the same levels. Without `subscriptions`, every `active` member
gets in. Who gets in is decided in one place in the site's Strapi, which every
gated capability uses.

**Leads reach Mautic through the site's Strapi** (operator decision,
2026-10-13; workspace#168, carried to Strapi 2026-10-20; workspace#203). A
site's forms and their submissions are content in its Strapi. A job in it
upserts each submission's contact in the site's own Mautic, through the API
on that Mautic's internal Service, then adds it to the segment and tags its
form names. Strapi reads that Mautic's URL and credentials from what the
site entered in its admin (below), not from one platform-wide setting
(workspace#171). So a frontend talks to its Strapi alone, and a submission
is stored before Mautic sees it. It is one way: nothing comes back from
Mautic, and unsubscribes stay Mautic's.

**A site's integrations are set in its Strapi's admin, with nothing per
site in gitops or Vault** (operator decision, 2026-10-17; workspace#187, for
Payload; carried to Strapi 2026-10-21; workspace#203). The platform keeps
what Strapi needs to start and what is the operator's: the database
(`apps/<namespace>/database`), Strapi's own secrets and the admin's own
mail key (`apps/<namespace>/cms`), the front's API token
(`apps/<namespace>/cms-client`), RUM, `ghcr-pull`, each site's Mautic as a
deployment, and the network. Everything else a site needs from an outside
service, it sets in the admin, choosing the integration of each capability
and entering its keys: payments (Stripe), video (Bunny), community
(Discord), marketing automation (Mautic's URL and credentials), the site's
own email (Resend), and the storage of its media and of its resources.
Another integration is added in its plugin, without a change to the
capability that picks it. What holds no secret (library IDs, plans,
content) is set in the admin too.

**Each site brings its own accounts** (operator decision, 2026-10-17;
workspace#187, without tenants since 2026-10-20; workspace#203). Its
Stripe, Bunny, Discord, Resend and storage are the site's, billed to it,
and the platform lends none of its own; each site's Mautic, deployed by the
platform, stays as it is. Integrations the platform provides, such as
Stripe Connect, one platform bot, or the platform's own video, storage or
mail with a quota per site, are not built until there are sites that pay
for them. Each would be one more integration of the same port, beside the
site's own.

**A key entered in the admin lives in Vault, written and read by Strapi.**
Strapi logs in with its own Kubernetes identity and a role of its own in the
`vault` repo, `cms`, for the namespaces labelled `vault.0xc0.cc/cms`, which
reaches only `integrations/` under its own namespace. It keeps a key at
`apps/<namespace>/integrations/<name>` (`apps/artistlabco-com/` in prod,
`apps/artistlabco-com-staging/` in staging) and resolves it by the
integration's name; Vault Secrets Operator does not sync them. The database
never holds a value, only who set it and when, and the admin never shows
one back. A new integration needs no change in gitops or Vault. The mail a
site sends to its public, magic links and confirmations, goes out from that
site's domain with the key the site entered, not the admin's, so the
platform still never sends as a site (email, above).

**A site's storage is its own, in any S3-compatible provider**: one bucket
for its media and one for its resources, each per environment. Media may
have a public URL, and without one Strapi serves the files. Its buckets are
R2's, named by the rule above and created by `infrastructure`: new ones, not
the ones Payload used.

**Strapi's egress is HTTPS on 443 to the public internet**, except private,
reserved and cluster ranges (operator decision, 2026-10-17; workspace#187,
for Payload; carried to Strapi 2026-10-21; workspace#203): the services a
site picks are outside, and the cluster needs no rule per provider.
Internal services stay closed at the network layer, and Strapi refuses an
endpoint that is not HTTPS or that resolves to a private address, with
timeouts and size limits. An in-cluster integration (a site's Mautic) or
one on another port keeps its own rule. The risk is taken knowingly
([accepted risks](../accepted-risks.md)).

**One shared PostgreSQL for the applications that need it** (operator
decision, 2026-10-09; workspace#64): one server in `platform/postgres`, with
the same rules as the shared MariaDB: one database and one role per
application, named after its namespace, a plain StatefulSet from the
official image with no operator, and a nightly logical dump per database.
It was added because Payload does not support MySQL or MariaDB. It stays
for Strapi, which supports it: the server, its network policy and its dumps
already exist, so each site's Strapi is one more database and role on it,
and no second engine or server runs for it.

**Application repos carry the `app` topic** (operator decision,
2026-10-09), set in `.github`'s `terraform.tfvars` with the others.

Zones are Proxmox SDN: one Simple zone, a VNet and a subnet per zone, the host
as `.1` and SNAT for egress, all in OpenTofu through `bpg/proxmox`. Zones
spanning nodes do not exist: there is one node. Native Proxmox firewall through the same
provider.

## The admin, for the people who edit

The reason for the switch from Payload binds every capability of a site's
Strapi (operator decision, 2026-10-21; workspace#203): the editors, a site's
founders today and a client later, run the whole site from the admin
without help, in the language each picks in their profile, Spanish by
default and English complete (operator decision, 2026-10-22;
workspace#209). Strapi still stores content as content types; what
makes its admin friendly is configured, and part of it is written as the
site's own admin pages. Every capability brings its admin part, in the same
change:

- **Their words, in their language**: every content type, field and block
  has a display name and a help text that says what it does on the site, in
  Spanish and in English; errors read in plain words in the user's
  language. A list field's options are shown as stored, since Strapi does
  not translate them. Spanish lives in the site's views, English beside it
  in the site's translations, and each shared plugin carries both; the
  translation ids are in the
  [`strapi-plugin-admin-setup` README](https://github.com/0xc0-labs/packages/tree/main/packages/strapi-plugin-admin-setup#readme).
- **Only what they use**: internal types (magic links, Stripe events,
  plumbing) are hidden from the Content Manager. An Editor role sees
  content, members and forms, never settings or a key's value; the operator
  is the super admin.
- **Views laid out for the task**: field order, widths, groups and list
  columns chosen per type. The layout lives in the repo and is applied at
  startup, so every environment matches; nothing is configured by hand in
  one environment only.
- **A page builder that reads like the page**: blocks with names, icons and
  a one-line description in the user's language, and Strapi's Preview
  beside the form showing the real front.
- **Actions where the thing is**: buttons in the edit view, through Strapi's
  injection zones, such as resending a member's sign-in link.
- **Integraciones**: a settings page of the site's own, one card per
  capability (payments, video, community, mail, marketing, storage), with
  its state (configured, missing, failing), a button to test the connection,
  help on where each key is found at the provider, and who set it and when,
  never the value.
- **Inicio as a dashboard**: widgets on Strapi's home with new members,
  active subscriptions, the latest form submissions, the next event, and any
  integration missing or failing.

## Templates

Every VM clones a template baked by Packer (operator decision, 2026-09-24).
Each chain starts from an official cloud image, which OpenTofu imports through
the Proxmox API as a raw template that no VM clones:

- **Debian**: `debian-13-cloud` → `debian-13-base` (the `base` role: guest
  agent, SSH hardening) → `debian-13-runner`.
- **Rocky**, for the RKE2 nodes: the Rocky cloud image → its base template,
  with the same `base` role, which then supports both families.

What is per VM or secret, the VM's role included, stays with cloud-init and
Ansible.

Templates carry no version. Each takes a fixed VMID from its range (operator
decision, 2026-09-29): 9000-9099 for the raw images, 9100-9149 for Packer's,
and that ID plus 50 for a template's next build. VMs keep the VMIDs Proxmox
assigns. Everything still finds a template by name. A rebuild builds
`<name>-next` beside the template and swaps it in only once it succeeds,
keeping its VMID (infrastructure#207); VMs are full clones and ignore later
changes to their template, so moving one onto a rebuilt template is a
deliberate `rebuild`.
