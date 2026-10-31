output "public_ip" {
  description = "Public IPv4 address of the server."
  value       = oci_core_instance.server.public_ip
}

output "ssh_command" {
  description = "How to log in."
  value       = "ssh -i ${pathexpand(trimsuffix(var.ssh_public_key_path, ".pub"))} ubuntu@${oci_core_instance.server.public_ip}"
}

output "image" {
  description = "Operating system image the server was created from."
  value       = data.oci_core_images.ubuntu.images[0].display_name
}

output "shape" {
  description = "Shape and size of the server."
  value       = var.server_type == "arm" ? "VM.Standard.A1.Flex · ${var.ocpus} OCPU · ${var.memory_gbs} GB · ${var.boot_volume_gbs} GB disk" : "VM.Standard.E2.1.Micro · 1/8 OCPU · 1 GB (+2 GB swap) · ${var.boot_volume_gbs} GB disk"
}
