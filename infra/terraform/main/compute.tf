# The server: one Always Free VM with Ubuntu 24.04 — Ampere A1 (ARM) or AMD micro, chosen
# with var.server_type. Creating A1 instances often fails with "Out of host capacity";
# `make tf-apply-retry` keeps trying.

locals {
  shape = var.server_type == "arm" ? "VM.Standard.A1.Flex" : "VM.Standard.E2.1.Micro"
}

data "oci_identity_compartment" "project" {
  id = var.compartment_ocid
}

data "oci_identity_availability_domains" "all" {
  compartment_id = data.oci_identity_compartment.project.compartment_id # the tenancy
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = local.shape # only images compatible with the shape (ARM or x86)
  state                    = "AVAILABLE"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "server" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.all.availability_domains[var.availability_domain_index].name
  fault_domain        = var.fault_domain # null: OCI chooses
  display_name        = var.name
  shape               = local.shape

  # Only flexible shapes (A1) take a size; the micro shape is fixed.
  dynamic "shape_config" {
    for_each = var.server_type == "arm" ? [1] : []
    content {
      ocpus         = var.ocpus
      memory_in_gbs = var.memory_gbs
    }
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id # newest Ubuntu 24.04 for the shape
    boot_volume_size_in_gbs = var.boot_volume_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    hostname_label   = var.name
    display_name     = "${var.name}-vnic"
  }

  metadata = {
    ssh_authorized_keys = trimspace(file(pathexpand(var.ssh_public_key_path)))
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }

  preserve_boot_volume = false # `terraform destroy` removes the disk too

  lifecycle {
    # A newer Ubuntu image or an edited cloud-init must not replace a running server;
    # they apply to servers created from then on.
    # The fault domain only matters when creating (the retry script rotates it).
    ignore_changes = [source_details[0].source_id, metadata["user_data"], fault_domain]
  }
}
