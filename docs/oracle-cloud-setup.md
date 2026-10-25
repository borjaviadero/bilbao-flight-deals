# Oracle Cloud setup

The project runs on the **Oracle Cloud Infrastructure (OCI) Always Free** tier. This page covers the account; the infrastructure itself is created with Terraform in Phase 3 (see [infra/terraform](../infra/terraform/README.md)).

## Account

| Setting | Value | Why |
|---|---|---|
| Account type | Free Tier (starts as a 30-day Free Trial, then Always Free) | No cost |
| Home region | **Spain Central (Madrid)** | Closest region. Always Free resources only exist in the home region, and it **cannot be changed** later |
| Upgrade to Pay As You Go | **No** | On a free-only account, exceeding free limits stops resources instead of billing |
| MFA | Enabled (TOTP authenticator app) | Required by Oracle on first sign-in |
| Resources created by hand | **None** | Everything is created from code with Terraform |

## Sign-up notes

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/). A card is needed for identity verification only; a small temporary hold may appear.
2. Choose the **Cloud Account Name** (tenancy name) carefully: it is used to sign in and cannot be changed.
3. Choose the **home region** carefully: it cannot be changed.
4. Provisioning takes a few minutes; a confirmation email arrives when the account is ready.
5. On first sign-in at [cloud.oracle.com](https://cloud.oracle.com/), enrol an authenticator app. When using an app other than Oracle Mobile Authenticator, tick **"Offline mode or use another authenticator app"** before scanning the QR code.

> The MFA QR code is a secret: anyone who has it can generate valid codes. Never share it or take screenshots of it.

## Free trial vs Always Free

During the 30-day trial the account has credits and can create paid resources. This project never does: it only uses Always Free resources, so nothing changes when the trial ends. Ignore any prompts to upgrade.

## Always Free compute (Oct 2026)

| Resource | Limit |
|---|---|
| Ampere A1 (ARM) | 1,500 OCPU-hours and 9,000 GB-hours per month — equivalent to **2 OCPU / 12 GB** running continuously |
| AMD micro VMs | 2 × (1/8 OCPU, 1 GB) |
| Block storage | 200 GB total |
| Object storage | 20 GB |

Creating Ampere A1 instances can fail with *Out of host capacity* when the region is busy; the fix is to retry later. This is handled in Phase 3.
