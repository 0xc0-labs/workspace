# Accepted risks

Part of the closed design ([the index](design.md)): not reopened without an
explicit decision from the operator.


- Everything but the sandbox node runs on `pve-2` (operator decision,
  2026-11-25; workspace#285): its loss stops the estate until it returns or
  is restored from PBS onto `pve-1`, an RTO of hours, with `ct-base-01` first
  since it holds the OpenTofu state. That restore has to be tested and timed.
- `pve-1` alone has no quorum (operator decision, 2026-11-23; workspace#285,
  votes 2 and 1): it starts nothing and its configuration is read-only until
  `pve-2` returns.
- A guest on `pve-1` loses its egress while `pve-2` is down (operator decision,
  2026-11-25; workspace#285, no egress per node): the gateways and the SNAT are
  `pve-2`'s. `pve-1` itself is reached on its public SSH.
- Longhorn with two replicas (operator decision, 2026-11-25; workspace#285):
  while a node reboots, the volumes with a copy on it run on one copy until it
  is rebuilt.
- `pve-2`'s NVMe are worn (accepted on 2026-11-25; workspace#285): 73 % of
  their rated life used, and one has 23 media and data integrity errors. The
  system and the VM disks are on them, and RAID 1 survives one failing. The
  operator will ask Hetzner to replace it, in his words of 2026-11-24: «si lo
  pediré, pero más tarde/otro día, nosotros seguimos adelante».
- Grafana's alerts reach nobody until a contact point is chosen (accepted on
  2026-11-25; workspace#290): the sixteen rules are evaluated and listed in
  Grafana, but its notification policy has no destination, so a volume
  filling, a node not ready or a sealed Vault shows only to whoever opens
  Grafana. A contact point carries secrets, so it comes from Vault in a later
  change. What limits it is that Grafana's `Alerting` lists what fires. What
  ends it is the contact point: email through Resend, as the applications
  send, or a chat webhook, to be chosen.
- Grafana's admin login is a password generated into Vault at the operator's
  request (accepted on 2026-11-25; workspace#290), an exception to the
  operator writing every secret himself. He asked the orchestrator to create
  the secrets' paths empty for him to fill («créame tú los secretos vacíos pls
  y yo los relleno») and, for Grafana's, said: «el de grafana créalo tú mismo,
  admin password al azar que tú generes». The orchestrator generated it with
  `openssl rand` straight into Vault, and it was never shown. It is one local
  admin account, the fallback since 2026-11-26, when people began to sign in
  through Cloudflare Access ([platform](design/platform.md#access-for-operators)),
  with no second factor, whose value lives in Vault alone. What limits it is
  that Grafana is reached over WARP only, and that the secret, at
  `platform/grafana/admin`, is read by the `monitoring` role alone, apart from
  an admin's own login. What ends it is the operator writing a new value, which
  Vault Secrets Operator takes to Grafana by restarting it.
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
  is the admins alone, and that inside the cluster only the panel, the API,
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
  `apps/matchmark/claude-subscription`, and in that pod and, from phase 2, in
  the sandboxes' namespace too (see below). What ends an incident is the
  operator revoking the token and writing a new one in Vault. The detail is
  in `gitops`'
  [`apps/matchmark/README.md`](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-factory-worker)
  and its
  [route](https://github.com/0xc0-labs/gitops/blob/main/apps/matchmark/README.md#the-subscription-route).
- The containers of `vm-rke2-06`, the sandbox node, run without an SELinux
  label (accepted by the operator on 2026-11-20; workspace#266, narrowed to
  that node alone on 2026-11-25; workspace#288): gVisor's `runsc`, which
  isolates the sandboxes Matchmark's coding agents run in, refuses a container
  that carries a label, and containerd labels all of a node's containers or
  none. Every pod of that node runs unlabelled, so SELinux would not hold a
  container that broke out of its runtime from the others' files there. What
  limits it is that nothing but the sandboxes and the per-node agents runs on
  that node, its taint keeping every other pod off, so the shared PostgreSQL,
  MariaDB, Vault and Plane, and every other node's containers, label as
  before; that a sandbox is disposable, with no volume on the node, which is
  left out of the backup; that the host stays Enforcing; and that the pods keep
  their Pod Security level, seccomp and dropped capabilities. What ends it is a
  runtime for the sandboxes that runs with labels. The detail is in
  `infrastructure`'s
  [README](https://github.com/0xc0-labs/infrastructure/blob/main/README.md#gvisor-on-the-sandbox-node),
  section "gVisor on the sandbox node".
- Nothing but Matchmark's own code stops its factory from merging a pull
  request in `matchmark-playground` (accepted by the operator on 2026-11-20;
  workspace#272): the factory acts on GitHub as an App, `matchmark-bot`, that
  can write contents, which it needs to create a branch and a commit; the
  repo is private, in a free organization, which cannot have a ruleset; and
  an App that can push can merge. What limits it is that the factory's port
  to the Git host has no operation that merges, approves or force-pushes, and
  its adapter sends a fixed list of requests; that the App has no `workflows`
  permission, so GitHub refuses its pushes to `.github/workflows`; and that
  nothing of value lives in that repo. What the operator accepted is that
  repo alone: the App must be installed on the repos it works on and no
  others, selected one by one, never on all of the organization's, and
  before the factory works in any other repo, a lock that GitHub itself
  enforces must exist. What ends it is that lock. The detail is in
  `matchmark`'s
  [`docs/factory/git-host.md`](https://github.com/0xc0-labs/matchmark/blob/main/docs/factory/git-host.md#it-opens-pull-requests-and-never-merges),
  section "It opens pull requests and never merges".
- A sandbox of Matchmark's coding agent holds the token of the operator's
  Claude subscription (accepted by the operator on 2026-11-20;
  workspace#272): in the operator's workspace the coding agent is the Claude
  Agent SDK, paid by that subscription, and it runs inside the sandbox, so
  the token is where the agent's own commands run. Vault delivers it to the
  sandboxes' namespace, `matchmark-sandboxes`, which reads that one path and
  nothing else (vault#95, applied on 2026-11-20). A coding agent that is
  manipulated by what it reads could read the token. What limits it is that
  the commands the agent runs do not inherit the token (the runner sets
  `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`), which lowers the risk and does not
  remove it; that the sandbox's network reaches Matchmark's gateway and a
  proxy with a fixed list of hosts, and nothing else, DNS included; that the
  worker looks for the token in the change before it pushes anything; and
  that the token can only make model requests. What ends an incident is the
  operator revoking the token and writing a new one in Vault. The detail is
  in `matchmark`'s
  [`docs/architecture/sandbox.md`](https://github.com/0xc0-labs/matchmark/blob/main/docs/architecture/sandbox.md#what-the-sandbox-holds),
  section "What the sandbox holds".
