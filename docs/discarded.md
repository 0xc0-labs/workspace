# Discarded — do not propose

Part of the closed design ([the index](design.md)): not reopened without an
explicit decision from the operator.


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
| semantic-release | it releases on every push to a branch, the branch's last commit; a release here promotes the rc staging runs, an earlier commit if main moved on. git-cliff computes the version, one pinned binary where semantic-release is Node and plugins on runners that reach Vault (operator decision, 2026-10-11; workspace#87). An application with no staging does release every push, still with git-cliff, for the second reason: its release job runs on those runners (operator decision, 2026-10-12; workspace#140) |
| Longhorn RWX volumes for applications' files | an NFS share-manager is one more pod and one more single point, and the application still serves its files itself; R2 instead (operator decision, 2026-10-11; workspace#88) |
| Hetzner Object Storage, for now | a fixed monthly fee with 1 TB included, its own hostname with Cloudflare in front anyway, and another provider's keys, where R2 is free up to 10 GB with no egress fees. Reconsidered past about 400 GB, where it costs less (operator decision, 2026-10-11; workspace#88) |
| RustFS or an object store in the cluster, for applications' files | RustFS is run by hand on the node and holds the OpenTofu state; one in the cluster costs memory the cluster does not have to spare (operator decision, 2026-10-11; workspace#88) |
| Manual Stripe tax rates for a tenant's checkout | a manual rate is one fixed rate whatever the customer's country; Stripe Tax applies each country's rate, the EU B2B reverse charge and the OSS reports, at a fee per transaction, and payload already supports it per tenant (`automaticTax` in Site settings → Subscriptions) (operator decision, 2026-10-17; payload#168) |
