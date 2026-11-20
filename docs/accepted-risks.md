# Accepted risks

Part of the closed design ([the index](design.md)): not reopened without an
explicit decision from the operator.


- Single piece of hardware, with no second node: a hardware failure is an RTO
  of hours.
- Disks in RAID 0 (operator decision, 2026-09-23): one NVMe failure loses the
  whole node. Recovery is a reinstall plus a restore from PBS on the Storage
  Box, which is why that restore has to be tested and timed.
- Dependency on Cloudflare to get in, with Hetzner Rescue as the way out.
- One cluster holds shared services and applications, Vault included: they are
  separated by namespace and NetworkPolicy, not by zone.
- Vault is sealed after every restart until it is unsealed by hand; meanwhile
  applications get no new secrets. A site's Strapi keeps its integrations'
  keys only in memory, read from Vault, so a Strapi pod that starts in that
  window has none (operator decision, 2026-10-17; workspace#187, for Payload;
  restated for Strapi, 2026-10-21; workspace#203): the site's payments,
  video, community, mail and storage answer as not configured until the
  unseal, and come back on their own once Vault is unsealed. There is
  nothing to unseal automatically with, so it stays by hand.
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
- The applications' files in R2 have no copy outside Cloudflare: PBS does
  not see them, and a nightly copy to the Storage Box was turned down. A
  deleted bucket or object, by mistake or through the shared Cloudflare
  token, is lost (operator decision, 2026-10-12; workspace#89).
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
- A site's Strapi pods may reach HTTPS 443 on the public internet, except
  private, reserved and cluster ranges (operator decision, 2026-10-17;
  workspace#187, for Payload; restated for Strapi, 2026-10-21;
  workspace#203): a site picks its integrations in its admin, so no rule per
  provider is possible. Exfiltration is already open through Cloudflare's
  ranges, and internal services stay closed at the network layer. Strapi
  refuses an endpoint that is not HTTPS or that resolves to a private
  address.
- The controller of Matchmark's agentgateway reads the Secrets and
  ConfigMaps of every namespace (accepted on 2026-11-19: the operator was
  told and left it to the orchestrator; workspace#252): its chart cannot
  narrow its `ClusterRole`, so whoever compromises that pod reads every
  Secret of the cluster. What limits it is that the controller writes in
  `matchmark` alone, builds its configuration from that namespace alone, and
  takes no connection from outside it. The detail is in `gitops`'
  [`apps/matchmark/README.md`](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#what-the-controller-can-reach).
- Temporal's panel in Matchmark has no login of its own, until Zitadel is
  deployed in Matchmark's phase 4 (accepted by the operator on 2026-11-20;
  workspace#260): Temporal ships with no authentication, and the cluster has
  no identity provider to log in against yet. Whoever reaches the panel sees
  every run with its input and its output, and can start, cancel or terminate
  one. What limits it is that the panel is reached over WARP only, which today
  is the operator alone, and that inside the cluster only the panel, the API,
  the worker and the Job that creates Temporal's namespace reach its
  frontend. What ends it is the panel logging in through Zitadel, which
  Temporal's UI supports (OIDC), with the server asking for a token. The
  detail is in `gitops`'
  [`apps/matchmark/README.md`](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#temporal).
- The pod of Matchmark's factory worker holds the token of the operator's
  Claude subscription (accepted by the operator on 2026-11-20;
  workspace#260): the operator's own workspace runs on the Claude Agent SDK,
  paid by that subscription, and the SDK's process needs the token where it
  runs. Whoever gets into that pod, or reads its Secret, can spend the
  operator's plan from elsewhere until the token is revoked. What limits it is
  that the token can only make model requests and lasts one year; that
  nothing connects to the worker; that the agents it runs today have no
  tools, so an idea that tries to manipulate one has nothing to read the
  token with; and that the token is in Vault, at
  `apps/matchmark/claude-subscription`, and in that pod and nowhere else.
  What ends an incident is the operator revoking the token and writing a new
  one in Vault. The detail is in `gitops`'
  [`apps/matchmark/README.md`](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-factory-worker)
  and its
  [route](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-subscription-route).
- The containers of `vm-rke2-04` run without an SELinux label (accepted by
  the operator on 2026-11-20; workspace#266): gVisor's `runsc`, which
  isolates the sandboxes Matchmark's coding agents will run in, refuses a
  container that carries a label; containerd labels all of a node's
  containers or none; and the Proxmox host has no room for a node of the
  sandboxes' own. Every pod of that node runs unlabelled, the shared
  PostgreSQL, MariaDB, a Vault replica and Plane among them, so SELinux
  would not hold a container that broke out of its runtime from the others'
  files. What limits it is that the host stays Enforcing; that the pods keep
  their Pod Security level, seccomp and dropped capabilities; that the three
  server nodes label their containers as before; and that no service on the
  cluster is critical yet, in the operator's words. What ends it is a node
  of the sandboxes' own, or moving the data services to the nodes that
  label (measured on 2026-11-20: about 1 CPU and 3.5 GiB to move, which fits
  in the other three), which the operator turned down for now: "B de
  momento.. no nos sobran recursos". The detail is in `infrastructure`'s
  [README](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#gvisor-on-vm-rke2-04),
  section "gVisor on vm-rke2-04".
