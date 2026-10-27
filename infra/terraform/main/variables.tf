variable "oci_profile" {
  description = "Profile of ~/.oci/config used for authentication (it also sets the region)."
  type        = string
  default     = "DEFAULT"
}

variable "compartment_ocid" {
  description = "Project compartment, from the bootstrap stack output compartment_ocid."
  type        = string

  validation {
    condition     = startswith(var.compartment_ocid, "ocid1.compartment.")
    error_message = "compartment_ocid must start with \"ocid1.compartment.\"."
  }
}

variable "admin_cidr" {
  description = "Only this address range may reach the server over SSH, e.g. your public IP as \"203.0.113.10/32\"."
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must be a valid CIDR and must not open SSH to the whole internet."
  }
}

variable "ssh_public_key_path" {
  description = "Public SSH key installed for the default user (ubuntu)."
  type        = string
  default     = "~/.ssh/oci_dealhunter.pub"
}

variable "name" {
  description = "Name of the server; also its hostname and the prefix of the network resources."
  type        = string
  default     = "dealhunter"
}

# Always Free Ampere A1: 2 OCPU and 12 GB in total for the whole tenancy (Oct 2026).
variable "ocpus" {
  description = "ARM cores of the server (Always Free limit: 2 in total)."
  type        = number
  default     = 2
}

variable "memory_gbs" {
  description = "Memory of the server in GB (Always Free limit: 12 in total)."
  type        = number
  default     = 12
}

variable "boot_volume_gbs" {
  description = "Boot disk size in GB (Always Free block storage: 200 GB in total)."
  type        = number
  default     = 50
}

variable "availability_domain_index" {
  description = "Which availability domain to use (0 = first). Madrid has one."
  type        = number
  default     = 0
}
