terraform {
  # 1.12+ is needed by the main stack's native "oci" state backend; same floor here.
  required_version = ">= 1.12"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 7.0"
    }
  }
}

# Credentials come from the OCI CLI config file (~/.oci/config), never from this repo.
provider "oci" {
  config_file_profile = var.oci_profile
}
