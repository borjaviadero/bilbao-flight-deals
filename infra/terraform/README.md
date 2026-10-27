# terraform

Infrastructure as Code for Oracle Cloud Always Free, in the home region **Spain Central (Madrid)**. Account and API key setup: [docs/oracle-cloud-setup.md](../../docs/oracle-cloud-setup.md).

| Stack | Folder | Creates | State | Status |
|---|---|---|---|---|
| Bootstrap | [`bootstrap/`](bootstrap) | Project compartment, versioned private bucket for Terraform state, budget alert on any spend | Local file (`bootstrap/terraform.tfstate`, ignored by Git) | ✅ |
| Main | (next PR) | Network (VCN, subnet, security rules) and the ARM VM (2 OCPU / 12 GB) | In the bucket, via the native `oci` backend | Phase 3 |

The bootstrap stack exists because the state bucket cannot hold the state of the stack that creates it. It is small, rarely changes, and every resource in it can be re-imported if its local state is lost.

## Usage

```bash
cp infra/terraform/bootstrap/terraform.tfvars.example infra/terraform/bootstrap/terraform.tfvars
# edit: tenancy_ocid, budget_alert_email
make tf-bootstrap-init
make tf-bootstrap-plan    # review: 4 resources to add
make tf-bootstrap-apply   # type "yes" to confirm
```

The outputs give the compartment OCID and the contents of `backend.hcl` for the main stack.

## Rules

- Credentials are read from `~/.oci/config` (profile `DEFAULT`). Never commit keys, `*.tfvars`, `backend.hcl` or state files — `.gitignore` excludes them.
- Only Always Free resources. The budget emails an alert if anything ever costs money.
- `.terraform.lock.hcl` **is** committed: it pins the exact provider versions.
- CI runs `terraform fmt -check` and `terraform validate` on every stack (no cloud access).
