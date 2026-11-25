# Platform

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

## Stack

Proxmox VE 9 on two Hetzner dedicated servers in one cluster, each with 2×
NVMe in mdadm RAID 1 · PBS to a Hetzner Storage Box · RustFS for the OpenTofu
state, in an LXC · Cloudflare R2 for the applications' files · Resend for their
email · Cloudflare Free (Tunnel, Access, WARP) · Packer + OpenTofu + Ansible ·
GitHub Actions with self-hosted runners · RKE2 on Rocky Linux · HAProxy +
keepalived · ArgoCD · Traefik with the Gateway API · CrowdSec · cert-manager
with Let's Encrypt · external-dns · Longhorn · Headlamp · Vault · Prometheus,
Loki, Tempo and Grafana behind the OpenTelemetry Operator's collectors ·
Hetzner Rescue as the emergency path.

**Two Proxmox nodes in one cluster, `pve-2` the main one** (operator
decisions, 2026-11-23 to 2026-11-25; workspace#285). The cluster is named
`cluster`: two nodes, no QDevice, no HA, `pve-2` with 2 votes and `pve-1` with
1, so `pve-2` keeps quorum alone and `pve-1` alone has none. Corosync runs on
a vSwitch of its own, VLAN 4000, `10.20.0.0/24`. On the votes, the operator
(2026-11-23): «meteremos el nuevo nodo al cluster de proxmox y no añadiremos
qdevice, luego a uno de ellos (ya elegirimos cual) le daremos voto de 2».
- **`pve-2`**, the main node: i9-9900K, 16 threads, 125 GB. Two NVMe in mdadm
  RAID 1 (storage `local`) hold the system and the VM disks, and two SATA SSDs
  in RAID 1 (storage `sata`) hold Longhorn's data disks. It runs every guest
  but one, the sandbox node, and holds every zone's gateway, forwarding, the
  SNAT to its public address and the MSS clamp, and PBS, which backs up to the
  Storage Box. The operator kept it as the main node on 2026-11-25, when
  `pve-1` was back and empty:
  «vamos a dejar al principal que sea el tocho, movamos las VMs solo que sean
  necesarias al otro y listo». That replaced the choice of the day before that
  `pve-1` would take the role back.
- **`pve-1`**: 12 threads, 62.6 GB. Reinstalled on 2026-11-24/25 with its two
  NVMe in RAID 1 and rejoined. It runs one guest, the sandbox node
  `vm-rke2-06` (below), and carries the zones' bridges with no address on
  them; when `pve-2` is down it is reached on its public SSH.

RAID 1 on the NVMe replaces the RAID 0 of 2026-09-23 on both nodes. `pve-2`'s
have used 73 % of their rated life and one has logged 23 media errors, and at
level 1 the array survives one drive failing: replacing it needs no reinstall
and no restore, as the array rebuilds onto the new drive. The operator chose
it on 2026-11-23: «RAID1 si». `pve-1` was reinstalled for it. **The guests are
not spread over the two nodes**, but for the sandbox node: etcd and Vault have
three members each and need two, so neither survives the loss of either node,
and spreading them or the VM pairs only changes which node is critical; the
runners, the load balancers and the WARP connectors do nothing on `pve-1`
without what `pve-2` holds ([discarded](../discarded.md)). How a node is
installed, joined and rejoined, and where each thing runs, is `infrastructure`'s:
[`docs/architecture.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/architecture.md),
[`docs/zones.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/zones.md) and its README, in
[Adding a node](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#adding-a-node) and
[A node that rejoins](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#a-node-that-rejoins).

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

**The cluster runs on three node pools, the infrastructure, the applications
and the sandboxes each apart** (operator decisions, 2026-11-25; workspace#288).
A node's pool is its label `0xc0.cc/pool`:

| Pool | Nodes | Host | Size | Taint | Runs |
|---|---|---|---|---|---|
| `infra` | `vm-rke2-01`, `-02`, `-03`, the servers | `pve-2` | 6 vCPU / 16 GiB | none | the control plane, etcd, Vault, Longhorn, Prometheus, Loki, Tempo, Grafana, PostgreSQL, MariaDB, Argo CD, CrowdSec and everything else under `gitops`' `platform/` |
| `apps` | `vm-rke2-04`, `-05` | `pve-2` | 4 vCPU / 12 GiB | `0xc0.cc/pool=apps:NoSchedule` | everything under `gitops`' `apps/` |
| `sandbox` | `vm-rke2-06` | `pve-1` | 10 vCPU / 32 GiB, a 150 GiB root, no Longhorn | `0xc0.cc/pool=sandbox:NoSchedule` | Matchmark's sandboxes under gVisor, and nothing else |

What the operator decided, on 2026-11-25:
- **The infrastructure apart from the applications, and a big sandbox node
  among the workers**: «hay que hacer 2 cosas, revisar el cluster y
  diferenciar entre apps e infrastructura para redimensionar los nodos y luego
  a parte los nodos worker (apps) dentro de estos estará el nodo de sandbox
  (gordo)».
- **Shared databases go with the infrastructure**, and what belongs to one
  application goes with it (Plane's Valkey, RabbitMQ and object store,
  Matchmark's RustFS). Put to him as the rule, he answered «ok vale me
  convences».
- **A second application node and a hard taint**: «pues creamos otro nodo de
  apps y hacemos taint fuerte y listo no?». The cost put to him was one
  maintenance window: Longhorn's system components take a new toleration only
  with every volume detached, so the taint needs the cluster's workloads
  stopped once, and the window joined the servers' resize, which restarts them
  and needs Vault unsealed anyway. His answer: «sin problema, vale». The window
  ran on 2026-11-25. A soft taint is [discarded](../discarded.md).
- **The names**: «mejor 04 y 05 apps y 06 sandbox».
- **No PVC for the sandboxes** ([discarded](../discarded.md)): by Matchmark's
  design a sandbox is disposable, with `emptyDir` only, deleted at the end of
  each attempt. What survives is in Temporal, in Matchmark's RustFS and in git.

**Why** (the inventory of 2026-11-25): the infrastructure was 85 % of the
memory and 96 % of the CPU the cluster used, and the applications about 0.1 CPU
and 4 GiB. The sandboxes shared `vm-rke2-04` with a Vault pod, PostgreSQL,
MariaDB and OpenObserve, and gVisor made that whole node run without SELinux
labels. Taking the infrastructure off that node adds about 5 GiB to the
servers, hence 16 GiB each. After the change `pve-2` keeps about 40 GB free and
`pve-1` about 30 GB.

**Placement is one rule**: shared services, databases included, go with the
infrastructure, and what belongs to one application goes with that
application. It comes to this:
- Every workload under `gitops`' `apps/` is pinned to `pool=apps` and tolerates
  its taint, from one shared component, `apps/_components/pool-apps`.
- The infrastructure needs no placement: it has none of its own, both other
  pools reject it, and it lands on the servers.
- The sandboxes reach `pool=sandbox` through the RuntimeClass `gvisor`, which
  selects the pool and tolerates its taint, so a workload sets
  `runtimeClassName` and nothing else.
- The per-node agents tolerate the taints they must. Longhorn, CrowdSec's
  agent, Traefik and the log collector's agent tolerate the `apps` taint; the
  log collector's agent alone tolerates the `sandbox` one, as that node has no
  Longhorn disk.

How each is set is `gitops`': the
[Longhorn README](https://github.com/0xc0-labs/gitops/blob/main/platform/longhorn/README.md#the-apps-taint)
for its toleration, and the
[gVisor README](https://github.com/0xc0-labs/gitops/blob/main/platform/gvisor/README.md)
for the RuntimeClass. The pools, their labels and taints, and the window's
steps are `infrastructure`'s: its README,
[Node pools](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#node-pools)
and
[the window](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#the-apps-taint-and-the-servers-size-a-maintenance-window),
and
[`docs/zones.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/zones.md#machines),
for the nodes.

**The sandbox node, `vm-rke2-06`, is the one node that runs gVisor**, as a
second container runtime, for Matchmark's sandboxes (operator decision,
2026-11-20; workspace#270, from the test in workspace#266; moved to a node of
its own on 2026-11-25; workspace#288). `runsc` refuses a container that
carries an SELinux label, and containerd labels all of a node's containers or
none, so that node labels none: an [accepted risk](../accepted-risks.md), as
small as the node, since nothing but the sandboxes runs there. `vm-rke2-04`,
which ran gVisor as the shared worker from 2026-11-20, has its labels back; the
operator let it leave before the window, 2026-11-25: «no pasa nada, si
matchmark no esta en produccion, dale». A small file- and process-heavy
workload took 2.8 times as long under gVisor as under the default runtime. The
node has no Longhorn volume and is left out of the daily PBS backup, as a
sandbox is disposable; its egress leaves through `pve-2`, like every guest on
`pve-1`. With the node down the sandboxes wait in Temporal and resume when it
returns. What Matchmark's design asks of the node is in its
[`docs/architecture/deployment.md`](https://github.com/0xc0-labs/matchmark/blob/main/docs/architecture/deployment.md);
what the cluster runs for it, in `gitops`'
[`platform/gvisor/README.md`](https://github.com/0xc0-labs/gitops/blob/main/platform/gvisor/README.md);
how the node is built, with the way back from gVisor, in `infrastructure`'s
[README](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#gvisor-on-the-sandbox-node).

**Vault runs in the cluster** (operator decision, 2026-09-24). A running
cluster never needs Vault to start: the RKE2 token and ArgoCD's admin password
are already in files only root reads on the servers, written there by Ansible,
which reads them from Vault (`ci/infrastructure/*`). ArgoCD deploys Vault, and
the components take their secrets from it through Vault Secrets Operator. No
secret lives in `gitops`, not even encrypted. Vault is unsealed by hand after a
restart. A cluster built from nothing needs Vault restored first, from PBS:
an accepted risk ([accepted risks](../accepted-risks.md)).

**Vault's shape** (at the operator's request, 2026-09-30; gitops#33): three
servers in HA over integrated storage (Raft), one per RKE2 server, each on a
Longhorn volume. Shamir seal: the keys
live in the operator's password manager and offline, never in the cluster or
any repo. It is on the WARP-only path, `https://vault.int.0xc0.cc`; Traefik ends
TLS, and inside the cluster the API is plain HTTP behind NetworkPolicies
(Raft's port is TLS with Vault's own certificates; there is no TLS between
pods on the API). No agent injector: Vault Secrets Operator reads it. The
init and unseal runbook is `gitops/platform/vault/README.md`.

**Observability is Prometheus, Loki, Tempo and Grafana, behind one
OpenTelemetry gateway** (operator decision, 2026-11-25; workspace#290). It
replaces OpenObserve (operator decision, 2026-10-01; gitops#44), which was the
lightest way to have the three signals while the cluster was one node with
little memory left. With two nodes and servers of 16 GiB that reason no longer
held, and OpenObserve's cost showed on 2026-11-25: its volume reached 3.3
million files, and containerd relabels a volume recursively when a container
starts on a node that labels its containers, for longer than kubelet allows,
so the start looped (workspace#288). What the move brings is community
dashboards for nearly everything that runs (Kubernetes, Longhorn, Traefik, Argo
CD, Vault, CrowdSec) in place of hand-written ones, the standard query
languages (PromQL, LogQL, TraceQL), and Grafana's correlation between the
signals. The comparison was put to the operator, who answered «ok pues
seguramente cambiemos a ese stack, lo veremos después de lo que estamos ya»
and, leaving the choices to the orchestrator, «recuerda que eres full
autónomo, incluso si quieres ir desplegando el stack de grafana eres libre,
prioriza tú mismo». The plan was a week of both before the cut-over, and it
took none: since OpenObserve's volume was recreated on 2026-11-25 its
collectors' exports failed with `Unauthenticated`, so Prometheus, Loki and
Tempo alone held the data, and OpenObserve was removed that day.
- **Metrics: kube-prometheus-stack.** Prometheus, one replica, keeps 30 days on
  a 20 Gi Longhorn volume. It scrapes every ServiceMonitor and PodMonitor
  itself, and takes the applications' OTLP metrics through the gateway;
  node-exporter and kube-state-metrics report the nodes and the objects, and
  the control plane's metrics are exposed on the RKE2 servers for it. Not
  Mimir, which is built to scale out on object storage: at about 39,000 series
  Prometheus is one process. A block is a handful of files every two hours, so
  its volume does not bring the relabel loop back.
- **Logs and traces: Loki (30 days) and Tempo (14 days), monolithic, on two
  private R2 buckets**, their keys in Vault. Tempo's metrics generator answers
  the TraceQL metrics the trace dashboards read. R2 and not a Longhorn volume,
  because Loki writes a file per chunk and the relabel loop would be back; and
  not an object store in the cluster, which costs memory and a volume, nor
  Hetzner's, which only costs less past about 400 GB: R2 is cents a month with
  no egress fee ([discarded](../discarded.md)). The orchestrator chose it,
  under the delegation above.
- **Alerts are Grafana's, with no Alertmanager** (operator, 2026-11-25: «no se
  podría usar mejor grafana alerts? me gustan más»): one place for rules,
  silences and destinations, with rules over Loki as well as Prometheus. Sixteen
  Grafana-managed rules, provisioned from git, cover volumes filling, nodes not
  ready, pods restarting, Vault sealed, certificates expiring, etcd, Deployments
  short of replicas, targets down and the collectors failing to export, and one
  over Loki's error lines; the chart's default Kubernetes rules stay in
  Prometheus, and Grafana lists them read only. There is no contact point yet,
  so an alert shows in Grafana and reaches nobody ([accepted
  risks](../accepted-risks.md)).
- **One neutral collector is the entry point.** The applications and Traefik
  send OTLP to `otel-gateway.opentelemetry.svc.cluster.local` and never know
  the backends (operator, 2026-11-25: «las apps iban a apuntar al collector
  (endpoint centralizado) y estos reparten a loki prometheus y tempo», and of
  the name, «Sí me parece genial»). The OpenTelemetry Operator runs two
  collectors, named after no backend: a gateway on the `infra` pool, which
  sends traces to Tempo, metrics to Prometheus, and logs and Kubernetes events
  to Loki, and makes the service graph; and an agent on every node, tainted
  pools included, which reads the containers' logs from `/var/log/pods`, keeps
  its offsets on the node and sends them to Loki. No collector scrapes. Alloy
  stays out ([discarded](../discarded.md)).
- **Grafana** is at `grafana.int.0xc0.cc`, over WARP only like every portal.
  Its admin login is read from Vault (`platform/grafana/admin`), with no SSO:
  OIDC through Zitadel is for later. Its data sources and dashboards come from
  git and are read only in the UI: the chart's Kubernetes ones, imported ones
  for Argo CD, Longhorn, Traefik, Vault and CrowdSec, and rebuilt ones for the
  applications, Matchmark, the traces and Kubernetes events, which replace
  every dashboard OpenObserve had.

What runs, how it is checked and what the operator writes are `gitops`'
[`kube-prometheus-stack`](https://github.com/0xc0-labs/gitops/blob/main/platform/kube-prometheus-stack/README.md),
[`loki`](https://github.com/0xc0-labs/gitops/blob/main/platform/loki/README.md),
[`tempo`](https://github.com/0xc0-labs/gitops/blob/main/platform/tempo/README.md)
and
[`opentelemetry-collector`](https://github.com/0xc0-labs/gitops/blob/main/platform/opentelemetry-collector/README.md)
READMEs; the keys at each secret's path, `vault`'s README.

**Every application is observable from the day it is deployed** (operator
decision, 2026-10-03; workspace#52). The change that deploys it ships all of
this, never a follow-up:
- **logs:** to stdout or stderr, with a level the node agent can parse; an
  application of ours writes the org's JSON line, with the trace and span IDs,
  that `@0xc0-labs/observability` provides. A log the application writes to a
  file is followed onto stdout by a sidecar (Mautic's).
- **metrics:** at least Traefik's per-route traffic and the kubelet's per-pod
  resources, on Grafana's `Apps` dashboard; its own endpoint, with a
  ServiceMonitor, when it has one.
- **traces:** OTLP to `otel-gateway`, joined to Traefik's trace through
  `traceparent`. That means egress to the gateway, and the namespace admitted
  in the collector's `otlp-from-senders`.
- **RUM, when it has a frontend: Faro, which is pending** (workspace#290,
  phase 3). Until it lands no site sends RUM, and no trace starts in the
  visitor's browser. What self-hosted Faro gives is events and measurements in
  Loki and traces in Tempo, with dashboards of ours; Grafana's Frontend
  Observability app and Session Replay are Grafana Cloud's, so OpenObserve's
  RUM screen and session replay go with it. The phase has to check whether Faro
  keeps anything in the visitor's browser: OpenObserve's SDK stored nothing,
  and so needed no consent banner.

**Plane is the exception to the rule above** (operator decision, 2026-11-19;
workspace#250): it has only what the cluster takes of every pod and route,
its logs through the collector and the metrics of its route and pods. It
sends no traces and no RUM, and nothing is built for it. It is a third-party
tool the org uses to track Matchmark's projects, an external piece that could
be any other tracker.

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
each (noted 2026-10-01). The full standard is in the `vault` repo's README.

**Vault is configured with OpenTofu from its own repo, `vault`** (operator
decision, 2026-09-30; .github#6): auth methods and roles, policies, secret
engines. It is downstream of `gitops`, which deploys Vault, so the order stays
linear: `.github → infrastructure → gitops → vault →` the applications
(`offby1.cc` and `artistlabco.com`).
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
default `StorageClass`, on the data disks of the servers and the application
nodes, never the sandbox node's.
**It keeps two replicas, not three** (operator decision, 2026-11-25;
workspace#285, answering «si»). Every node with a Longhorn disk runs on
`pve-2`, so all the copies are on one host, on its RAID 1, and each protects
against something different: a failing disk, the RAID; `pve-2` failing, PBS's
daily backups,
since every copy is on that host; an RKE2 VM rebooting or breaking, which is
what happens in practice, Longhorn's replicas, as the volume's pod starts on
another node from the other copy and Longhorn rebuilds the second. A third
copy only covers two VMs failing at once, which in practice is the host
failing, where it does not help. Two replicas give 50 % more room for volumes
and a third fewer writes to the drives that hold them. What they do not cover:
while a node reboots, the volumes with a copy on it run on one copy until it is
rebuilt ([accepted risk](../accepted-risks.md)). The data disks live on
`pve-2`'s SATA RAID 1 (storage `sata`), 300 GiB a node, moved there on
2026-11-25 when the cluster's inventory found Longhorn short of room
(0xc0-labs/infrastructure#310); about 480 GiB of volumes fit. How it is set up
is `gitops`'
[`platform/longhorn/README.md`](https://github.com/0xc0-labs/gitops/blob/main/platform/longhorn/README.md).
Longhorn has no backup target of its own: **PBS backs the VMs up whole**,
data disks included, and that is what the timed restore tests.

**The applications' files live in Cloudflare R2** (operator decision,
2026-10-11; workspace#88), the one object store for them: uploads and
anything else an application keeps as objects. Longhorn keeps the databases
and what needs a filesystem; RustFS keeps only the OpenTofu state. Plane's
attachments and Matchmark's artifacts are the two exceptions, each in an
object store of its own in the cluster (Plane and Matchmark, below). One
bucket per application and environment, named `<namespace>-<purpose>`
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
[discarded](../discarded.md). `artistlabco.com`'s is the first Strapi
(0xc0-labs/workspace#202). A site's front calls its Strapi inside the
cluster, as its BFF ([delivery](delivery.md)), with an API token: Strapi's
public role grants nothing, and the API is never public.
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
(`apps/<namespace>/cms-client`), `ghcr-pull`, each site's Mautic as a
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
R2's, named by the rule above and created by `infrastructure`.

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

**Plane is Matchmark's tracker, not the org's** (operator decisions,
2026-11-18; workspace#247): Matchmark's software factory will read and write
its work there, and the org's board stays the source of truth for the org's
work. It is on the WARP-only path, `https://plane.int.0xc0.cc`, and never
public: no public name and no Cloudflare Access application. Its database is
one more on the shared PostgreSQL, as every application's. Its Valkey,
RabbitMQ and object store are its chart's own, in its namespace, `plane`.
The object store is for Plane's attachments alone, the first of the two
exceptions to the [discarded](../discarded.md) object store in the cluster:
Plane signs every upload with a presigned POST, and R2 signs only GET, HEAD,
PUT and DELETE. Its namespace enforces `baseline`, not `restricted`, because
its images declare no user and run as root and its chart sets no security
context; tightening it is a later change, 0xc0-labs/gitops#418. How it is
deployed and operated is `gitops`' own, in its
[`apps/plane/README.md`](https://github.com/0xc0-labs/gitops/blob/main/apps/plane/README.md).

**Matchmark is one application in `gitops`, with a gateway of its own**
(operator decisions, 2026-11-19; workspace#252): `apps/matchmark/prod`, in
the namespace `matchmark`, reached over WARP only. `api.matchmark.int.0xc0.cc`
is its API, `app.matchmark.int.0xc0.cc` will be its console, and
`matchmark.int.0xc0.cc` is kept for the product's future front;
`matchmark.dev` is not used yet. The wildcard for `*.int.0xc0.cc` covers one
label, so those names have a certificate and a listener of their own on
Traefik's Gateway, `internal-matchmark` (0xc0-labs/gitops#425).
agentgateway 1.7.0 is part of the application, not a shared service: its
controller, its CRDs and its Gateway are deployed from the application's
folder. That is an exception to the rule that a cluster-scoped kind an
application needs goes through `platform/`: Matchmark's Application alone
has an Argo CD project, `matchmark`, that admits `CustomResourceDefinition`,
`ClusterRole` and `ClusterRoleBinding` besides `Namespace`
(0xc0-labs/gitops#427). The cost is that a change under
`apps/matchmark/prod` can create cluster-wide permissions, so every PR there
is reviewed with that in mind; what the controller reads is an
[accepted risk](../accepted-risks.md). Its database is one more on the
shared PostgreSQL, as every application's, with no server of its own
(0xc0-labs/gitops#423). Its artifacts are in a RustFS, one server in its
namespace with a 10Gi Longhorn volume, the second exception to the
[discarded](../discarded.md) object store in the cluster: its design asks
for it, and the operator decided for it "for this application, for now", not
R2 (0xc0-labs/gitops#429). Its API signs its agent tokens with a Transit key
generated inside Vault, `matchmark-agent-tokens`; the pipeline's roles have
nothing on Transit's keys, so a key is created by hand, imported or
generated (0xc0-labs/vault#91), as the
[`vault` README](https://github.com/0xc0-labs/vault/blob/main/README.md#transit-keys-that-never-leave-vault)
says. Its agents run in that namespace too, since its phase 1
(workspace#255). **Temporal** is a second Argo CD Application,
`matchmark-temporal`, from `apps/matchmark-temporal/prod`, a folder that
follows `apps/<application>/<environment>/` as every application's does
(operator decision, 2026-11-20; workspace#262), in the namespace
`matchmark` (operator decision, 2026-11-19: the same namespace, because the
API talks to that Temporal as it does to the gateway; 0xc0-labs/gitops#451).
Its two databases are two more on the shared PostgreSQL, with no pooler in
front until one is needed (operator decision, 2026-11-19;
0xc0-labs/gitops#450, 0xc0-labs/vault#93). Temporal's own connection pools
are bounded in its chart's values, so that it cannot take every connection of
the shared server, and the operator kept that bound on 2026-11-20
(workspace#260); the figures stay in `gitops`'
[README](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#temporal).
Its panel is `temporal.matchmark.int.0xc0.cc`, reached over WARP only, with
no login of its own, as the
[`gitops` README](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#temporal)
says: an [accepted risk](../accepted-risks.md) until Zitadel (operator
decision, 2026-11-20; workspace#260). **The factory worker** is one
Deployment of the application, `factory-worker`, that takes runs from that
Temporal and runs each agent through the namespace's gateway
(0xc0-labs/gitops#468). The operator's own workspace runs on the Claude Agent
SDK, paid by the operator's Claude subscription (operator decision,
2026-11-19; the harness is chosen per workspace, as
[`matchmark`'s `docs/platform/workspaces.md`](https://github.com/0xc0-labs/matchmark/blob/main/docs/platform/workspaces.md)
records it): the worker reads that subscription's token from Vault,
`apps/matchmark/claude-subscription`, which the operator writes, and nothing
else mounts it
([the worker](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-factory-worker),
[the route](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-subscription-route)).
**The gateway answers over WARP under the API's name**,
`api.matchmark.int.0xc0.cc`, for the model routes alone, so that `mm`,
Matchmark's command, runs an agent from the operator's machine through the
same gateway as the worker (0xc0-labs/gitops#456;
[the route](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-gateway-over-warp)).
What phase 1 showed and measured is in Matchmark's own
[`docs/roadmap.md`](https://github.com/0xc0-labs/matchmark/blob/main/docs/roadmap.md)
and
[`docs/open-decisions.md`](https://github.com/0xc0-labs/matchmark/blob/main/docs/open-decisions.md).
How it is deployed and operated is `gitops`' own, in its
[`apps/matchmark/README.md`](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md).

**Application repos carry the `app` topic** (operator decision,
2026-10-09), set in `.github`'s `terraform.tfvars` with the others.

Zones are plain Linux bridges over Hetzner vSwitches, with no SDN (operator
decision, 2026-11-23; 0xc0-labs/infrastructure#271): one vSwitch per zone
(`mgmt` 4001, `ci` 4002, `platform` 4003), and on each node a VLAN interface
on the public NIC and a bridge named after the zone, both at MTU 1400, which a
vSwitch carries at most. Every guest is at 1400 and the pod network at 1350.
`pve-2` holds each zone's `.1` and does the SNAT for egress; `pve-1`'s bridges
are layer 2 only. EVPN, and an SDN zone per node, were put to the operator
first, and bridges over vSwitches do the same with less: «si vamos a ahcerlo
asi mas sencillo, adelante, vamos co ello» ([discarded](../discarded.md)). The
bridges and the native Proxmox firewall are OpenTofu's through `bpg/proxmox`;
the gateway's SNAT, forwarding and MSS clamp are lines written by hand on
`pve-2`, explained in `infrastructure`'s
[`docs/zones.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/zones.md).

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
