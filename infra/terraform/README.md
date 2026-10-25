# terraform

Infrastructure as Code for Oracle Cloud Always Free, in the home region **Spain Central (Madrid)**. Planned for **Phase 3**. Account setup: [docs/oracle-cloud-setup.md](../../docs/oracle-cloud-setup.md).

- Network (VCN, subnet, security rules)
- ARM VM (within the 2 OCPU / 12 GB free limit)
- Remote state in Oracle Object Storage

Never commit `*.tfvars` or state files — they are ignored by `.gitignore`.
