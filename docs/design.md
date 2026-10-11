# Closed design — 0xc0-labs

Status: **closed**. Not reopened without an explicit decision from the operator.

This file records the decisions. How the pieces fit together, with diagrams,
is in [`infrastructure/docs/architecture.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/architecture.md).

## Addressing

| Group    | Supernet     | Zones          |
|----------|--------------|----------------|
| control  | 10.10.0.0/22 | mgmt .0, ci .1 |
| platform | 10.10.4.0/24 | platform       |

Three zones (operator decision, 2026-09-24): `mgmt` and `ci`, which build and
reach everything else and never depend on it, and `platform`, which holds the
Kubernetes cluster and its load balancer. Separation inside the cluster is by
namespace and NetworkPolicy, not by zone.

Reserved so they never overlap:
`10.11.0.0/16` node 2 · `10.20.0.0/16` Hetzner Cloud and vSwitch ·
`10.42.0.0/16` RKE2 pods · `10.43.0.0/16` RKE2 services ·
`10.66.66.0/24` future lab.

## Machines

| Zone     | VM           | OS     | Contents                                          |
|----------|--------------|--------|---------------------------------------------------|
| mgmt     | vm-access-01 | Debian | cloudflared connector of the admin tunnel (QUIC)  |
| mgmt     | vm-access-02 | Debian | cloudflared connector of the admin tunnel (QUIC)  |
| ci       | vm-ci-01     | Debian | two ephemeral GitHub Actions runners              |
| ci       | vm-ci-02     | Debian | two ephemeral GitHub Actions runners              |
| platform | vm-lb-01     | Debian | HAProxy + keepalived; public tunnel connector     |
| platform | vm-lb-02     | Debian | HAProxy + keepalived; public tunnel connector     |
| platform | vm-rke2-01   | Rocky  | RKE2 server                                       |
| platform | vm-rke2-02   | Rocky  | RKE2 server                                       |
| platform | vm-rke2-03   | Rocky  | RKE2 server                                       |
| platform | vm-rke2-04   | Rocky  | RKE2 agent                                        |

Sizes and addresses are in `infrastructure/docs/zones.md`.

**The three RKE2 nodes are identical, and all three are servers** (operator
decision, 2026-09-27): each runs the control plane and etcd, and takes
workloads. In Kubernetes the role is configuration, not a different machine;
three servers keep etcd's quorum through the loss of one VM.

**Capacity grows with agents; etcd stays at three servers** (operator
decision, 2026-09-30). An agent runs workloads only, with no control plane or
etcd: a fourth server would tolerate no more failures than three, and two
would tolerate none. `vm-rke2-04` is the first, sized and disked like the
servers, Longhorn included. On one host it adds capacity, not availability.

**Outside the cluster, deliberately:** the vm-access pair is the admin way in,
and the vm-ci pair builds and changes the infrastructure, the cluster included.
Neither may depend on what it has to fix.

**Two CI VMs, identical** (operator decision, 2026-09-29): CI keeps running
while one is down, and a job on one can rebuild the other, so no rebuild of a
CI VM has to run from the laptop.

**The RKE2 nodes run Rocky Linux 10**, the latest release RKE2 supports
(RHEL 10 and its derivatives, with the package that allows `nf_conntrack`;
operator decision, 2026-09-24). They clone their own template chain, from the official
Rocky cloud image, as the Debian VMs do from theirs.

**The load balancer is deployed with the cluster**: the same OpenTofu module
creates the nodes and the two LB VMs, and Ansible writes HAProxy's backends from
the node list. HAProxy fronts the Kubernetes API (6443, 9345) and the ingress
NodePorts; keepalived moves its VIP between the two VMs.

The host (`pve-1`, `pve.0xc0.cc`) holds `.1` in every zone and is the router
and the firewall. `eno1` keeps the public IP. Each zone is an SDN VNet with no
physical port, and egress is SNAT through `eno1` — Hetzner drops unknown MACs
on the public interface, so guests never bridge onto it.

Besides Proxmox, the host runs the base services, **outside IaC**:

- **Traefik** — reverse proxy for the Proxmox UI, PBS and RustFS.
- **RustFS** — S3-compatible store holding the OpenTofu state (`s3.0xc0.cc`).
- **PBS** — backups, with the datastore on a Hetzner Storage Box.

## Transit

The matrix that decides is the `transit` variable in
`infrastructure/environments/prod/terraform.tfvars`: the `zone-firewall` module
computes every rule from it. `infrastructure/docs/zones.md` explains it. In
short:

| From     | To       | Ports                                                   |
|----------|----------|---------------------------------------------------------|
| mgmt     | ci       | 22                                                      |
| mgmt     | platform | 22, 443 (portals), 6443 (Kubernetes API), 8200 (Vault)  |
| mgmt     | node     | 22, 443, 8006                                           |
| mgmt     | mgmt     | 22, between the vm-access connectors                    |
| ci       | platform | 22, 6443                                                |
| ci       | mgmt     | 22, from the CI VMs only: Ansible on the vm-access pair |
| ci       | node     | 443, 8006 (API, not SSH)                                |
| internet | node     | 22, break-glass; closed at the Hetzner firewall         |
| platform | platform | the cluster's own traffic, and VRRP between the LBs     |
| platform | node     | 9100 (node metrics)                                     |

Inside `platform`, the cluster needs more than TCP (VXLAN for the pod network,
VRRP for keepalived), so each entry in the matrix can name its protocol.

The node is on a DROP policy: 22, 443 and 8006 from the admin zones, 22 never
from ci, the metrics port from platform, and from the internet only SSH, as
break-glass (operator decision, 2026-09-26): the Hetzner firewall keeps it
closed until the operator opens it, and sshd is key-only. Traefik (Proxmox UI,
PBS, RustFS) is reached over WARP, where Gateway resolves its hostnames to the
node's address in mgmt. If WARP breaks, the way back is that SSH, then the
Hetzner Rescue system.

No other zone initiates towards mgmt, with one exception: SSH from the CI VMs'
addresses, not the whole `ci` zone, so the pipeline can run the vm-access
playbook (operator decision, 2026-09-29).

## Flows

- **Web**: Cloudflare → public tunnel → cloudflared on the LB VMs → HAProxy
  (layer 4) on 443 → NodePort → Traefik, with CrowdSec's bouncer → service.
  cloudflared talks HTTPS to Traefik and checks its certificate, with the
  request's host as SNI. The client's address reaches Traefik as
  `CF-Connecting-IP`, trusted only from `platform`.
- **TLS** (operator decision, 2026-09-29): it ends at Traefik, on both paths,
  with a Let's Encrypt wildcard per domain (`*.d` and `d`) from cert-manager,
  through DNS-01 challenges in Cloudflare. Port 80 only redirects to HTTPS.
  Domains: `0xc0.cc` and `offby1.cc`; `sergioaten.cloud` once the Cloudflare
  token reaches its zone.
- **Public names**: the tunnel serves every name of the domains in
  `public_domains`, but a name is public only once external-dns gives it a
  record (a proxied CNAME to the tunnel), which it does only for an HTTPRoute
  annotated `gateway.0xc0.cc/public: "true"`. Only zones in the tunnel's own
  Cloudflare account can be public: a CNAME to it from another account's zone
  (`offby1.cc`) fails at the edge (1014). external-dns is part of the platform
  on purpose (operator decision, 2026-09-29).
- **Portals** (OpenObserve, ArgoCD, Headlamp): internal, reached only over WARP.
  None has a public record, and none is published behind Cloudflare Access
  (operator decision, 2026-09-29).
- **Internal services** (operator decision, 2026-09-30): a path of their own,
  separated by network. A second VIP on the LBs, `10.10.4.9`, sends its 443
  to Traefik's `internal` entrypoint; Cloudflare Gateway resolves every
  `*.int.0xc0.cc` name to it for WARP devices, and those names have no public
  record. The public tunnel only ever targets the public VIP, so nothing from
  the internet reaches the internal path. Headlamp, the Kubernetes UI, is
  one, at `headlamp.int.0xc0.cc`, logged into with a short-lived token. The
  internal path has no WAF: CrowdSec's bouncer is on the public entrypoint
  only.
- **Admin**: WARP → admin tunnel → either vm-access connector → any zone. The
  Kubernetes API, SSH, Vault, Proxmox, PBS and RustFS are reached **only** this
  way, never through the public tunnel.
- **Deploy**: infrastructure through the runners on the CI VMs (Proxmox API,
  SSH), OpenTofu, Packer and every Ansible playbook alike (operator decision,
  2026-09-29): `--check`/plan on the PR, the real run on merge behind manual
  approval. Nothing is applied from the laptop. What runs in the cluster goes
  through ArgoCD, from the `gitops` repo.
- **Egress**: VM → `.1` of its zone → NAT behind the public IP.

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
the accepted risk below.

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
linear: `.github → infrastructure → gitops → vault → offby1.cc and app-*`.
Its CI logs in with the job's GitHub OIDC token (JWT auth,
`hashicorp/vault-action`): no Vault credential is stored. A PR plans
read-only from any ref (role `terraform-plan`); only `main`, inside the
`production` environment that waits for the operator, writes (role
`terraform`). Neither policy touches a stored secret. The CI VMs
reach Vault on the internal VIP (`ci → platform: 443`).
The CI can only log in once its auth method and roles exist, so **the first
apply of `vault` is local**: the operator runs it once, over WARP, with the
root token (operator decision, 2026-09-30). It is the one exception to nothing
being applied from the laptop; every change after it goes through the
pipeline. The root token is kept, outside Vault, with the unseal keys
(operator decision, 2026-10-04).

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
copies of its own: a nightly copy to the Storage Box, with a timed restore,
is in place before prod holds real files.

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
inside the cluster (Application delivery, below; workspace#68), and only the
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
decision, 2026-09-29): 9000-9099 for the raw images, 9100-9199 for Packer's.
VMs keep the VMIDs Proxmox assigns. Everything still finds a template by name.
A rebuild deletes it and builds it again under the same VMID;
VMs are full clones and ignore later changes to their template, so moving one
onto a rebuilt template is a deliberate `rebuild`.

## Secrets

**Every secret lives in Vault, and none in a repo** (operator decision,
2026-10-01, .github#6), not even encrypted. SOPS, which held them until then,
is gone.

- **Layout:** the engines by trust boundary (`ci/`, `platform/`, `apps/`) and
  `ops/` for people; the paths, the shared rule and one service per path are
  above, under the stack's Vault.
- **CI:** each job logs in with GitHub's OIDC token. There is one JWT role per
  repo, bound to its repository and to `.github`'s reusable workflows on
  `main`, and a policy that names what it reads. No Vault credential and no
  Actions secret is stored anywhere.
- **The cluster:** each component reads through Vault Secrets Operator, with a
  Kubernetes auth role per namespace. What RKE2 and ArgoCD boot with, Ansible
  reads from Vault in CI.
- **Locally:** the scripts read Vault with the operator's token (`vault login
  -no-print`, over WARP), into the environment only.
- **Writing and rotating:** the operator does it by hand, in Vault (`vault`
  repo, README). The Cloudflare token is the one credential that crosses
  engines: one copy in `ci/shared/cloudflare` and one in
  `platform/shared/cloudflare`, rotated together.
- **Outside Vault:** what restoring Vault takes cannot live in it. The unseal
  keys and root token, PBS and its Storage Box, Hetzner Robot and Rescue,
  Proxmox `root@pam`, RustFS admin, and the Cloudflare, GitHub and Resend
  accounts with their 2FA are kept in the operator's password manager and an offline
  copy (`vault` README, "Recovery credentials: outside Vault").

## Discarded — do not propose

| Discarded           | Reason                                               |
|---------------------|------------------------------------------------------|
| WireGuard           | Cloudflare Access + WARP already covers admin access |
| Coraza              | the OWASP CRS needs hand-tuning; CrowdSec's virtual patching does not |
| open-appsec, for now | every Kubernetes integration runs on retired or unmaintained pieces; can be reconsidered for the public applications (operator decision, 2026-09-29) |
| kube-vip, MetalLB    | the load balancer VMs keep the VIP for WARP and the API (operator decision, 2026-09-29) |
| BunkerWeb           | stores its configuration in SQLite                   |
| OPNsense, VyOS      | fragile network hop and immature providers           |
| VLAN zones now      | one node: an SDN Simple zone isolates the zones; VLAN or EVPN zones come with node 2 |
| Terraform Stacks    | paid                                                 |
| OpenBao             | Vault's BSL does not affect this case                |
| SOPS+age            | replaced by Vault: every secret in one place, read over OIDC, nothing in the repos (operator decision, 2026-10-01) |
| Prometheus + Grafana, Loki, Tempo | replaced by OpenObserve, one light backend for the three signals (operator decision, 2026-10-01) |
| VictoriaMetrics + VictoriaLogs | lighter than LGTM, but three backends to run where OpenObserve is one (operator decision, 2026-10-01) |
| Two K8s clusters    | same hardware, adds no isolation; one cluster, separated by namespace (operator decision, 2026-09-24) |
| A VM per role (vm-edge, vm-apps, vm-data, vm-vault, vm-platform) | replaced by the cluster (operator decision, 2026-09-24) |
| Docker Compose on VMs | replaced by the cluster; `gitops` holds ArgoCD manifests |
| Bug bounty lab      | reserved range, out of scope                         |
| Flux                | operator decision (2026-09-22): GitOps is ArgoCD     |
| One ordered pipeline for the cluster's deployment | the three steps stay apart: OpenTofu creates the VMs, Ansible configures them and installs ArgoCD, ArgoCD syncs gitops (operator decision, 2026-09-30, infrastructure#112) |
| A self-hosted registry (Zot, Distribution), for now | GHCR stores and serves container images free, private ones included; one in the cluster adds TLS, auth, a volume, a containerd mirror on every node, and an outage that stops every reschedule. Reconsidered if GitHub starts billing container storage (operator decision, 2026-10-10) |
| Mend's hosted Renovate | a third party with write access to the private repos, and the token that reads the private npm package kept at Mend, outside Vault; Renovate runs self-hosted from `.github` (operator decision, 2026-10-11; workspace#68) |
| A public Payload API | the frontends render on the server and read it inside the cluster; only the uploaded files are public (operator decision, 2026-10-11; workspace#68) |
| Vault paths per application and environment (`apps/<app>/<env>/`) | the `apps` policy reads `apps/<namespace>/*` by the pod's namespace, and each environment is its own namespace (`<app>`, `<app>-staging`), so one policy covers every application and environment; a path per application and environment needs a policy per application (operator decision, 2026-10-11; workspace#87) |
| Amazon SES, for now | an AWS account, its sandbox, IAM and a bounce-handling circuit are not worth it with no volume; Resend over SMTP instead, so the move is credentials and DNS. Reconsidered when Mautic sends campaigns or the volume outgrows Resend's free plan (operator decision, 2026-10-12; workspace#92) |
| semantic-release | it releases on every push to a branch, the branch's last commit; a release here promotes the rc staging runs, an earlier commit if main moved on. git-cliff computes the version, one pinned binary where semantic-release is Node and plugins on runners that reach Vault (operator decision, 2026-10-11; workspace#87) |
| Longhorn RWX volumes for applications' files | an NFS share-manager is one more pod and one more single point, and the application still serves its files itself; R2 instead (operator decision, 2026-10-11; workspace#88) |
| Hetzner Object Storage, for now | a fixed monthly fee with 1 TB included, its own hostname with Cloudflare in front anyway, and another provider's keys, where R2 is free up to 10 GB with no egress fees. Reconsidered past about 400 GB, where it costs less (operator decision, 2026-10-11; workspace#88) |
| RustFS or an object store in the cluster, for applications' files | RustFS is run by hand on the node and holds the OpenTofu state; one in the cluster costs memory the cluster does not have to spare (operator decision, 2026-10-11; workspace#88) |

## Accepted risks

- Single piece of hardware, with no second node: a hardware failure is an RTO
  of hours.
- Disks in RAID 0 (operator decision, 2026-09-23): one NVMe failure loses the
  whole node. Recovery is a reinstall plus a restore from PBS on the Storage
  Box, which is why that restore has to be tested and timed.
- Dependency on Cloudflare to get in, with Hetzner Rescue as the way out.
- One cluster holds shared services and applications, Vault included: they are
  separated by namespace and NetworkPolicy, not by zone.
- Vault is sealed after every restart until it is unsealed by hand; meanwhile
  applications get no new secrets.
- Inside the cluster Vault's API is plain HTTP, held in by NetworkPolicies,
  until pod-to-pod TLS: tokens and secrets cross from Traefik to the pod
  unencrypted.
- The public tunnel's connectors run on the LB VMs: public traffic enters
  `platform`, never `mgmt`.
- The CI VMs reach the vm-access connectors over SSH, so a compromised CI VM
  reaches the admin way in. It already holds the keys that change the whole
  infrastructure.
- The WAF (CrowdSec) learns nothing and protects only what its rules know:
  virtual patching for known CVEs and IP reputation, not a model of each
  application's normal traffic.
- Longhorn's pods may egress anywhere: restricting it risks breaking storage
  silently, for little gain (operator decision, 2026-09-29, gitops#10).
- cert-manager and external-dns use OpenTofu's Cloudflare token, which can
  also change the tunnels, Zero Trust and Access: whoever reads its Secret in
  the cluster gets all of that (operator decision, 2026-09-29). One token
  serves both, in Vault (`platform/shared/cloudflare`); a DNS-only one was
  turned down (operator decision, 2026-09-30). It also administers R2, so
  whoever reads it can read and delete every application's files; a second
  token for R2 alone was turned down (operator decision, 2026-10-11;
  workspace#88).
- Every secret lives in Vault and nowhere else (operator decision,
  2026-10-01). With the cluster or Vault down, no pipeline runs and no local
  script gets credentials until Vault is restored from PBS and unsealed (the
  runbook is in the `vault` repo's README). PBS's backup of the RKE2 servers is
  the only other copy.
- The control plane's metrics are reachable from the whole `platform` zone
  (operator decision, 2026-10-02; infrastructure#158): etcd's on 2381, plain
  HTTP and unauthenticated, and the scheduler's and controller manager's on
  10259 and 10257, behind the API's authorization. That includes the load
  balancers, whose cloudflared connectors face the internet. They expose
  telemetry, not data or control; narrowing them to the RKE2 VMs needs the
  transit matrix to name cluster VMs as sources.
- A portal on the public path (`websecure`) stays internal only by having no
  public record. Every internal service goes on the internal path instead,
  which the public tunnel cannot reach.

## Repos and policies

`infrastructure` and `.github`: `main` only, PR required, apply behind manual
approval. Applications: each decides whether it has a staging environment; one
that does promotes staging→prod with the same digest, never a rebuild
(Application delivery, below).
ArgoCD points at `gitops/bootstrap/prod/`, which deploys `platform/` and
`apps/`.

## Application delivery

How an application's code goes from a commit to staging and prod, and how a
frontend and the backend it reads stay in step (operator decisions,
2026-10-10 and 2026-10-11; workspace#68). It applies to `payload` and
`artistlabco.com` first; another application adopts it when it gets a
staging environment.

**Trunk-based, versioned from Conventional Commits.** `main` is the trunk:
short-lived branches, squash merges, no release branches. Every merge to
`main` builds an image, `sha-<7>`, and cuts the next release candidate,
`vX.Y.Z-rc.N`, a tag on that commit whose version `git-cliff` computes from
the Conventional Commits since the last release (`feat` a minor, `fix` a
patch, `!` a major). Every rc goes to staging. A release, `vX.Y.Z`, is a
`workflow_dispatch` that the operator or the orchestrator runs: it takes the
rc that staging runs, read from `gitops`, and makes it a GitHub Release on
the same commit, with its changelog. A hotfix is a fix on `main`, its rc and
a release. Versions start at `0.1.0`; while in 0.x a breaking change bumps
the minor, which npm's caret already treats as breaking. `1.0.0` is cut by
hand when the first frontend reaches prod.

**Promotion is a PR in `gitops`, and the image is never rebuilt.** An rc and a
release each tag the same digest with their version, and open a PR in `gitops`
that changes only the environment's pin in its `kustomization.yaml`: the
`images:` entry, tag and digest, and the version beside it, which `gitops`' CI
checks against the tag. Staging's PR is set to merge itself once its checks
pass. Prod's is the operator's merge, and that merge is prod's approval:
GitHub Free gives private repositories no environment reviewers, wait timers,
environment secrets or rulesets. Rolling back is reverting that PR.

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

**The private applications run their whole CI on the self-hosted runners.**
Vault, and with it the Apps' tokens, is reachable only from inside; running
there also spares the GitHub-hosted minutes private repositories pay for.
The runner group admits these repos and the reusable workflows they call,
and the runners build images with rootless BuildKit, with the provenance and
SBOM the GitHub-hosted build gives today. A dependency's code runs on the same
runners that reach Vault, so a dependency version is taken only once it is
three days old (`minimumReleaseAge`, in Renovate and in pnpm), and pnpm runs
the build scripts of the packages it is told to (`allowBuilds`, which
replaced `onlyBuiltDependencies` in pnpm 11) and no others. Public repos
(`offby1.cc`) keep building on GitHub's runners.

**Integration tests bring their own PostgreSQL, from mise** (operator
decision, 2026-10-12; workspace#93). The runners have no Docker, and nothing
they run may listen on the network (`infrastructure`'s `docs/zones.md`,
invariant 10). So an application's tests start a throwaway server themselves:
PostgreSQL from conda-forge through mise (`conda:postgresql`, prod's major,
every package checksummed in `mise.lock` for Linux and macOS), `initdb` in a
temporary directory, no TCP port (`listen_addresses=''`), a Unix socket in
that directory, the repo's migrations, and everything removed when the tests
end. The same `pnpm test` runs on a runner and on a Mac. `node-check` only runs
it, with the tools the caller names. Not Debian's package (trixie ships 17,
and 18 would bake a third-party repo into the runner image), not PGlite (no
Payload adapter, and it does not behave as a server under concurrency), not a
GitHub-hosted job with a service container (Vault and the minutes, above).

**Staging is a second environment of the same application.** In `gitops`,
an application is one folder with one directory per environment:
`apps/<app>/prod/` and, when it has staging, `apps/<app>/staging/`, with
what both share in `apps/<app>/base/`. An application with one environment
keeps all of it in `prod/`; when it gains staging, the shared part moves to
`base/`. The `apps` ApplicationSet makes an Argo CD application of each
environment: prod keeps the application's name and namespace, `<app>`;
staging is `<app>-staging`. Staging has its own database on the shared
server, its own volumes, and its own `apps/<app>-staging/` path in Vault,
which the `apps` role already covers. It is reached over WARP only, at
`<app>-staging.int.0xc0.cc`, and is observed as prod is, its signals tagged
`deployment.environment=staging`. Its data is a seed versioned in `payload`:
tenants, test users and sample content, reset when needed; later, once prod
has content, a copy of prod without its users collection, run by the
operator. Applications without staging (`offby1.cc`, Mautic) move to
`prod/` and stay as they are. Each staging environment doubles its
application's memory in the cluster.

**Migrations run before the new version, from the same image.** An Argo CD
Sync hook in wave 1, before the Deployment in wave 2, runs `payload migrate`
with the digest being deployed: when it fails, the sync stops there and the
running version keeps serving. Not a PreSync hook: on an application's first
sync it runs before its namespace and secrets exist, and never finishes
(gitops#142). Every
migration is expand and contract, so the previous version works on the new
schema and rolling back the image is safe.

**The frontends render on the server.** A frontend is a Next.js application
in the cluster that reads Payload through its internal Service, with a
read-only API key of its tenant, kept in Vault: the browser never calls the
API, and what a page needs from it, a form or a search, goes through the
frontend's own server. Staging's frontend reads staging's Payload, and the
network policies let each Payload be reached only by the frontends of its
environment. The build never reads Payload, and nothing that differs between
environments is baked into the image (no `NEXT_PUBLIC_` value that does), so
one image serves both. Outside, only the uploaded files are public, from R2
at `media.0xc0.cc` (workspace#88); the API, GraphQL and authentication stay
inside, and the admin stays at `payload.int.0xc0.cc`.

**Observable as every application is, in both environments.** Stack's rule
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
origin only, the frontend's server continues it, its call to Payload carries
it, and Payload's spans reach PostgreSQL. Logs are JSON with the trace and
span IDs, so OpenObserve opens a request's logs from its trace. Payload,
itself a Next.js application, and the frontends instrument with OpenTelemetry
through Next.js's instrumentation hook, and each environment's namespace is
admitted in the collector's `otlp-from-senders`.

**Images of private repositories stay private.** The cluster pulls them from
GHCR with a read-only token at `apps/shared/ghcr-pull` in Vault, which Vault
Secrets Operator turns into an `imagePullSecret` in each namespace that
needs one. Images of public repos stay public, as today.

**The backend publishes a versioned contract.** `payload` publishes its
generated types as `@0xc0-labs/payload-types`, a private npm package in
GitHub Packages, with the version of the rc or release that built it: an rc
publishes `X.Y.Z-rc.N` under the `rc` dist-tag, a release `X.Y.Z`. A
frontend pins it in its `package.json`, so a breaking change in the backend
fails the frontend's build, never its users. The backend changes by expand
and contract: it adds (a minor) and deploys, the frontends adopt, and it
removes (a breaking release) only once no deployed frontend uses what goes.

**CI enforces the order between repos:**

1. A frontend release cannot depend on a prerelease of the contract, so the
   backend always reaches prod first.
2. Promoting a frontend to an environment fails unless that environment
   already runs a backend version at least as high as the one the frontend
   depends on, read from `gitops`.
3. Later: a breaking release of the backend does not reach prod while a
   frontend in prod still depends on the previous one.

**Renovate keeps every repo's dependencies current.** It runs as a scheduled
workflow in `.github`, on the self-hosted runners, with
`0xc0-labs-renovate`'s token. A preset in `.github` holds what is common:
the schedule, the grouping, Conventional Commit titles (`chore(deps): …`),
digests pinned, and nothing merged by itself. Each repo opts in with a short
`renovate.json` that extends it and adds its own. Being self-hosted, it runs
`mise lock` after it bumps a tool, so `mise.lock` stays in step. It leaves
alone the pins of the org's own images in `gitops`: promotion owns them.

## How we work

One orchestrator session in the workspace and one session per repo, instead
of one session in the workspace editing every repo (operator decision,
2026-10-10; workspace#74).

**Two roles.**

- **The orchestrator**: `claude -n orchestrator`, in the workspace. It plans,
  opens the issues, hands each repo its part, and checks what crosses repos.
  It edits the workspace repo (the design, the rules) and the board, and no
  other repo's files.
- **A repo session**: `claude -n <name>`, in that repo, opened by the operator
  in its own Herdr workspace when the repo is in play. It loads that repo's
  `CLAUDE.md`, plugins and permissions, works only there, and goes up to a
  draft PR.

A session's name is its repo's, as Herdr takes an agent's: dots to dashes, a
leading dot dropped (`github`, `offby1-cc`, `artistlabco-com`). The same name
goes to Herdr and to `claude -n`, and it is how the orchestrator addresses a
session. The operator works in Herdr: the workspace's own Herdr plugin
(`herdr/`, workspace#76) opens or focuses any repo's session, or the
orchestrator, from one key.

They talk through Claude Code's messages between local sessions. When a
repo's session is not open, the orchestrator asks the operator to open it;
it does not start one on its own.

**Repo sessions take their own work from the board.** One board for every
repo, `artistlabco.com` included (`CLAUDE.md`, Tracking, has how an issue is
filed). An issue turns **Ready** only with a complete contract and with what
it depends on applied: GitHub's "blocked by" orders the sub-issues of a change
across repos, and the orchestrator, or the operator, moves an issue to Ready
once its blockers are closed. Todo holds the rest. A repo session opened as
`claude -n <name> "/0xc0:work-issue"` takes its repo's Ready issue of highest
priority and moves it to In Progress, which is the claim; when it finishes
one, it looks for the next before it stops. A session acts only on a turn, so
one with nothing Ready waits, and the orchestrator, when it moves an issue to
Ready, messages that repo's session to look again. No session polls the board
on a timer: every look is a turn of the model, paid whether or not anything
is there. An issue set Ready by hand, past the orchestrator, is seen at the
session's next look.

**The issue is the contract.** A repo session starts with no memory of the
conversation behind its task, so everything it needs is in its issue: the
outcome, the acceptance criteria, the branch name, the sibling issues and the
merge order. The orchestrator's message points at the issue and adds nothing
the issue lacks. The repo session answers with a short report: the PR, its
checks, what it could not do, and any question for the operator.

**The orchestrator owns integration.** A green PR in every repo is not a
working change. Before a set of PRs is called done, the orchestrator checks
all of them, their merge order, and what one repo does to another: a policy
another repo's plan needs, a setting a repo inherits from the workspace, a
hook a session lacks. Each of those slipped through on 2026-10-10 while every
PR on its own was green.

**Plugins and permissions by kind of repo.** Every repo enables `0xc0` in its
own `.claude/settings.json`. The infrastructure repos (`.github`,
`infrastructure`, `gitops`, `vault`, `claude-config`) work with `0xc0`'s
hooks and skills, with strict permissions. The application repos add
gentle-ai at workspace scope and the official plugins they need, and an
unattended session there may work up to a draft PR (operator decision,
2026-10-10). Inside an application repo, gentle-ai leads the work: its own
workflow plans, writes and reviews the code, with its receipt-driven review
on. `/0xc0:work-issue` is the interface between that repo and the
orchestrator: it starts from `main`, claims the issue on the board and takes
it as the contract, opens the draft PR by the org's rules, reports back, and
keeps its list of what a session never does (operator decision, 2026-10-11;
workspace#68). The cost is accepted: gentle-ai's review asks the operator's
consent in the session's tab for a change of medium or high risk, so those
sessions are not wholly unattended, and its reviewers spend more of the
subscription. The plugin carries no agents (operator decision, 2026-10-11;
workspace#78): each repo's session builds and checks its own changes, and
what a reviewer checked lives in that repo's docs (`infrastructure`'s
`docs/zones.md`, Invariants; `gitops`' `CLAUDE.md`, Before opening a PR).

**What stays the operator's**: marking a PR ready, merging, every apply,
writing and rotating secrets, and which repos' sessions are open.

**Cost.** Every session draws on the operator's Claude subscription, and
several at work spend it faster than one. No `ANTHROPIC_API_KEY` in the
environment and no `--bare`, either of which bills the API instead.

Before anything depends on it, it runs as a pilot on one real change that
crosses repos.
