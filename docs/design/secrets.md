# Secrets

Part of the closed design ([the index](../design.md)): not reopened without
an explicit decision from the operator.

**Every secret lives in Vault, and none in a repo** (operator decision,
2026-10-01, .github#6), not even encrypted. SOPS, which held them until then,
is gone.

- **Layout:** the engines by trust boundary (`ci/`, `platform/`, `apps/`) and
  `ops/` for people; the paths, the shared rule and one service per path are
  under Vault in [platform](platform.md).
- **CI:** each job logs in with GitHub's OIDC token. There is one JWT role per
  repo, bound to its repository and to `.github`'s reusable workflows on
  `main`, and a policy that names what it reads. No Vault credential and no
  Actions secret is stored anywhere.
- **The cluster:** each component reads through Vault Secrets Operator, with a
  Kubernetes auth role per namespace, except Payload's tenant keys, which it
  reads and writes itself ([platform](platform.md)). What RKE2 and ArgoCD
  boot with, Ansible reads from Vault in CI.
- **Locally:** the scripts read Vault with the operator's token (`vault login
  -no-print`, over WARP), into the environment only.
- **Writing and rotating:** the operator does it by hand, in Vault (`vault`
  repo, README), except a tenant's integration keys, which its admins enter
  in Payload. The Cloudflare token is the one credential that crosses
  engines: one copy in `ci/shared/cloudflare` and one in
  `platform/shared/cloudflare`, rotated together.
- **Outside Vault:** what restoring Vault takes cannot live in it. The unseal
  keys and root token, PBS and its Storage Box, Hetzner Robot and Rescue,
  Proxmox `root@pam`, RustFS admin, and the Cloudflare, GitHub and Resend
  accounts with their 2FA are kept in the operator's password manager and an
  offline copy (`vault` README, "Recovery credentials: outside Vault").
