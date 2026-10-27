variable "oci_profile" {
  description = "Profile of ~/.oci/config used for authentication (it also sets the region)."
  type        = string
  default     = "DEFAULT"
}

variable "tenancy_ocid" {
  description = "OCID of the tenancy (root compartment): ocid1.tenancy.oc1..xxxx"
  type        = string

  validation {
    condition     = startswith(var.tenancy_ocid, "ocid1.tenancy.")
    error_message = "tenancy_ocid must start with \"ocid1.tenancy.\"."
  }
}

variable "project_name" {
  description = "Prefix for the names of the resources created here."
  type        = string
  default     = "bilbao-flight-deals"
}

variable "budget_alert_email" {
  description = "Address that receives an email if the project ever costs money."
  type        = string
}
