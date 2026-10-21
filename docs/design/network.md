# Network

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

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

The VMs, their roles, sizes and addresses:
[`infrastructure/docs/zones.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/zones.md). What follows is why
they are so.

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
computes every rule from it, and
[`infrastructure/docs/zones.md`](https://github.com/0xc0-labs/infrastructure/blob/main/docs/zones.md) explains it, port by
port.

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
  Domains: those in `public_domains` (`infrastructure`'s
  `terraform.tfvars`).
- **Public names**: the tunnel serves every name of the domains in
  `public_domains`, but a name is public only once external-dns gives it a
  record (a proxied CNAME to the tunnel), which it does only for an HTTPRoute
  annotated `gateway.0xc0.cc/public: "true"`. Only zones in the tunnel's own
  Cloudflare account can be public: a CNAME to it from another account's zone
  fails at the edge (1014), so every public zone lives in that account
  (`offby1.cc` was moved into it). external-dns is part of the platform
  on purpose (operator decision, 2026-09-29).
- **Portals** (OpenObserve, ArgoCD, Headlamp): internal, reached only over WARP.
  None has a public record, and none is published behind Cloudflare Access
  (operator decision, 2026-09-29).
- **A front's staging behind Access** (operator decision, 2026-10-13;
  workspace#176): a front's staging can be published on a
  public name of its own domain, `staging.<domain>`, behind a Cloudflare
  Access application, for people without WARP. The first is
  `staging.artistlabco.com`, for ARTIST LAB's founders. Its viewers log in
  with a one-time PIN sent to their email, and the session lasts 24 hours.
  The application and its policy are OpenTofu's, in `infrastructure`. The
  viewers are an Access group that the operator manages in Cloudflare's
  dashboard: OpenTofu creates the group and ignores its membership, so
  adding a person needs no change in any repo. The Access application exists
  before the name has a public record: `infrastructure` is applied before
  `gitops` routes the name. The internal name ([delivery](delivery.md))
  stays. Nothing else is published this way but a site's CMS admin
  ([platform](platform.md)).
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
  approval. Nothing is applied from the laptop but the two bootstraps that
  create CI's own access (`.github`'s and `vault`'s first applies;
  [platform](platform.md)). What runs in the cluster goes
  through ArgoCD, from the `gitops` repo.
- **Egress**: VM → `.1` of its zone → NAT behind the public IP.
