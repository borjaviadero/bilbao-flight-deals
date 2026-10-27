# Bootstrap stack: what must exist before the main stack can run.
#
#   compartment  isolates every resource of the project (easy to see, limit and delete)
#   bucket       stores the main stack's Terraform state (versioned, private)
#   budget       emails an alert if the project ever costs money (it should never)
#
# This stack keeps its own small state locally (terraform.tfstate here, ignored by Git):
# it cannot store its state in a bucket it has not created yet.

resource "oci_identity_compartment" "project" {
  compartment_id = var.tenancy_ocid
  name           = var.project_name
  description    = "Resources of ${var.project_name} (managed by Terraform)"
  enable_delete  = true # allow `terraform destroy` to remove it
}

data "oci_objectstorage_namespace" "this" {
  compartment_id = var.tenancy_ocid
}

resource "oci_objectstorage_bucket" "tfstate" {
  compartment_id = oci_identity_compartment.project.id
  namespace      = data.oci_objectstorage_namespace.this.namespace
  name           = "${var.project_name}-tfstate"
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  versioning     = "Enabled" # every state change keeps the previous version
}

# Always Free never bills, but a budget makes that verifiable: any actual spend in the
# compartment, however small, triggers an email.
resource "oci_budget_budget" "project" {
  compartment_id = var.tenancy_ocid
  display_name   = "${var.project_name}-budget"
  description    = "Alert on any cost in the ${var.project_name} compartment"
  amount         = 1
  reset_period   = "MONTHLY"
  target_type    = "COMPARTMENT"
  targets        = [oci_identity_compartment.project.id]
}

resource "oci_budget_alert_rule" "any_spend" {
  budget_id      = oci_budget_budget.project.id
  display_name   = "any-actual-spend"
  type           = "ACTUAL"
  threshold_type = "PERCENTAGE"
  threshold      = 1 # 1% of a budget of 1 = the first cent
  recipients     = var.budget_alert_email
  message        = "${var.project_name}: the Always Free compartment has started to cost money."
}
