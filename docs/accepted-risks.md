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
- Payload's pods may reach HTTPS 443 on the public internet, except private,
  reserved and cluster ranges (operator decision, 2026-10-17;
  workspace#187): a tenant picks its integrations in the admin, so no rule
  per provider is possible. Exfiltration is already open through
  Cloudflare's ranges, and internal services stay closed at the network
  layer. Payload refuses an endpoint that is not HTTPS or that resolves to a
  private address.
