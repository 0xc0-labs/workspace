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
(`offby1.cc`, `payload`, `artistlabco.com`).
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
(`payload-media`, `payload-staging-media`), created by `infrastructure`'s
Cloudflare root with a western Europe location hint, its `r2.dev` URL off. A
bucket whose files are public is attached to a hostname of ours
(`media.0xc0.cc`) and served through Cloudflare's cache, with `nosniff` and a
`default-src 'none'` CSP, so the application behind it need not be public.
Staging's buckets have no hostname: the application serves their files, over
WARP. Each application reads its bucket with an R2 token scoped to that
bucket, created by the operator in Cloudflare and kept in
`apps/<namespace>/`. With no files on disk, a volume no longer ties an
application to one replica or to stopping before each rollout. R2 is free up
to 10 GB, with no egress fees, and about 15 USD per TB beyond. It keeps no
copies of its own, and nothing copies it elsewhere
([accepted risks](../accepted-risks.md)).

**The applications send email through Resend, over SMTP** (operator
decision, 2026-10-12; workspace#92): `smtp.resend.com:587` with STARTTLS,
region `eu-west-1`, never a provider's own API or DSN scheme, so moving to
Amazon SES once the volume asks for it (Mautic's campaigns, or more than the
free plan's 100 a day) changes credentials and DNS, never code. The
platform's own mail (Payload's resets and invitations, internal tools) goes
out from `0xc0.cc`; a site's mail to its public, from that site's domain,
verified on its own: a site never sends as `0xc0.cc`, nor the platform as a
site. Each sending domain's DKIM, its MAIL FROM subdomain (`send.`, so the
apex keeps Cloudflare Email Routing's MX and SPF) and its DMARC record are
OpenTofu's, in `infrastructure`. Each application and environment sends with
its own key, sending access only and limited to its domain, created by the
operator in Resend and kept at `apps/<namespace>/email`. Staging sends real
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

**Mautic runs as one instance, no tenants** (operator decision, 2026-10-02;
gitops#73).
The official image's three roles (web, cron, worker) run as containers of one
pod, sharing one Longhorn RWO volume, so there is no RWX volume and no NFS
share-manager. Its database is in the shared MariaDB. It is public at
`mautic.0xc0.cc` for what contacts reach. Every admin path (`/s`, the
installer, the API) answers 403 there, with no hint of the internal name
(operator decision, 2026-10-02; gitops#78), and is reached only at
`mautic.int.0xc0.cc`, WARP only, so its login is never on the internet. It runs from `apps/`, under its own narrower
`AppProject`.

**Payload CMS runs as one multi-tenant instance** (operator decision,
2026-10-09; workspace#64), the backend of several frontends: one tenant
per frontend, through Payload's multi-tenant plugin. Its code is the
`payload` repo, private like `artistlabco.com`. The frontends read its API
inside the cluster ([delivery](delivery.md); workspace#68), and only the
uploaded files are public, served from R2 at `media.0xc0.cc`: nothing of
Payload itself is (workspace#88). The admin is reached only at
`payload.int.0xc0.cc`, WARP only, as Mautic's admin is. With its media in R2
it keeps nothing on disk, so a rollout starts the new pod before stopping the
old one; one replica for now.

**One shared PostgreSQL for the applications that need it** (operator
decision, 2026-10-09; workspace#64): Payload does not support MySQL or
MariaDB. One server in `platform/postgres`, with the same rules as the
shared MariaDB: one database and one role per application, a plain
StatefulSet from the official image with no operator, and a nightly
logical dump per database.

**Application repos carry the `app` topic** (operator decision,
2026-10-09), set in `.github`'s `terraform.tfvars` with the others.

Zones are Proxmox SDN: one Simple zone, a VNet and a subnet per zone, the host
as `.1` and SNAT for egress, all in OpenTofu through `bpg/proxmox`. Zones
spanning nodes do not exist: there is one node. Native Proxmox firewall through the same
provider.

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
