output "compartment_ocid" {
  description = "Compartment for every project resource (input of the main stack)."
  value       = oci_identity_compartment.project.id
}

output "state_bucket" {
  description = "Bucket holding the main stack's state."
  value       = oci_objectstorage_bucket.tfstate.name
}

output "namespace" {
  description = "Object Storage namespace of the tenancy."
  value       = data.oci_objectstorage_namespace.this.namespace
}

output "backend_config" {
  description = "Contents for infra/terraform/backend.hcl (main stack state backend)."
  value       = <<-EOT
    bucket    = "${oci_objectstorage_bucket.tfstate.name}"
    namespace = "${data.oci_objectstorage_namespace.this.namespace}"
    key       = "main/terraform.tfstate"
  EOT
}
