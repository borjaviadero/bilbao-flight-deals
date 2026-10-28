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
  value       = "VM.Standard.A1.Flex · ${var.ocpus} OCPU · ${var.memory_gbs} GB · ${var.boot_volume_gbs} GB disk"
}
