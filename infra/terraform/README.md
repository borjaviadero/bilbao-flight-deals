# terraform

Infrastructure as Code for Oracle Cloud Always Free, in the home region **Spain Central (Madrid)**. Account and API key setup: [docs/oracle-cloud-setup.md](../../docs/oracle-cloud-setup.md).

| Stack | Folder | Creates | State | Status |
|---|---|---|---|---|
| Bootstrap | [`bootstrap/`](bootstrap) | Project compartment, versioned private bucket for Terraform state, budget alert on any spend | Local file (`bootstrap/terraform.tfstate`, ignored by Git) | ✅ |
| Main | [`main/`](main) | Network (VCN, internet gateway, route table, security list, public subnet) and the ARM VM: Ubuntu 24.04, 2 OCPU / 12 GB, 50 GB disk | In the bucket, via the native `oci` backend (with locking) | ✅ |

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

Then the main stack:

```bash
make tf-main-config   # writes main/backend.hcl and main/terraform.tfvars (compartment + your public IP)
make tf-init          # state backend: the bucket
make tf-plan          # review: 6 resources to add
make tf-apply         # type "yes"; prints the server's public IP
make tf-ssh           # log in as ubuntu
```

| Main stack file | Contents |
|---|---|
| `network.tf` | VCN `10.0.0.0/16`, internet gateway, default route, security list (SSH **only from `admin_cidr`**, ICMP for path MTU), public subnet `10.0.1.0/24` |
| `compute.tf` | Newest Ubuntu 24.04 ARM image, `VM.Standard.A1.Flex` instance with public IP and the SSH key; image and cloud-init changes do not replace a running server |
| `cloud-init.yaml` | First boot: system updates, automatic security updates, UTC, no password logins |
| `outputs.tf` | Public IP, SSH command, image and shape |

**Your IP changes** (home connections usually do): run `make tf-main-config && make tf-apply` to update the SSH rule.

**Out of host capacity**: Ampere A1 capacity in a region is sometimes exhausted, for minutes or hours. Nothing is wrong with the code; the network is created and only the server is missing. `make tf-apply-retry` ([`scripts/apply-until-capacity.sh`](scripts/apply-until-capacity.sh)) retries every 3 minutes (up to 60 times; `ATTEMPTS` and `WAIT_SECONDS` change it). It applies without asking, so it only proceeds when the plan is exactly "create the server" and stops on any other plan or error.

## Rules

- Credentials are read from `~/.oci/config` (profile `DEFAULT`). Never commit keys, `*.tfvars`, `backend.hcl` or state files — `.gitignore` excludes them.
- Only Always Free resources. The budget emails an alert if anything ever costs money.
- `.terraform.lock.hcl` **is** committed: it pins the exact provider versions.
- CI runs `terraform fmt -check` and `terraform validate` on every stack (no cloud access).
