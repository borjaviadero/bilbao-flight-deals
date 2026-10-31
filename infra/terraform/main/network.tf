# Network: one VCN with one public subnet. The only way in is SSH from admin_cidr;
# the server can reach the internet (price API, Telegram, image registry).
#
#   internet ─ internet gateway ─ route 0.0.0.0/0 ─ public subnet 10.0.1.0/24 ─ server

locals {
  vcn_cidr    = "10.0.0.0/16"
  subnet_cidr = "10.0.1.0/24"
}

resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.name}-vcn"
  cidr_blocks    = [local.vcn_cidr]
  dns_label      = var.name
}

resource "oci_core_internet_gateway" "main" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.name}-igw"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.name}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.name}-public-sl"

  # Outbound: anything (updates, price API, Telegram, GHCR).
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH, only from the administrator's address.
  ingress_security_rules {
    source      = var.admin_cidr
    protocol    = "6" # TCP
    description = "SSH from admin"

    tcp_options {
      min = 22
      max = 22
    }
  }

  # ICMP "fragmentation needed" (path MTU discovery), as in OCI's default rules.
  ingress_security_rules {
    source      = "0.0.0.0/0"
    protocol    = "1" # ICMP
    description = "Path MTU discovery"

    icmp_options {
      type = 3
      code = 4
    }
  }

  # ICMP "destination unreachable" inside the VCN.
  ingress_security_rules {
    source      = local.vcn_cidr
    protocol    = "1"
    description = "ICMP errors within the VCN"

    icmp_options {
      type = 3
    }
  }
}

resource "oci_core_subnet" "public" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.main.id
  display_name      = "${var.name}-public"
  cidr_block        = local.subnet_cidr
  dns_label         = "public"
  route_table_id    = oci_core_route_table.public.id
  security_list_ids = [oci_core_security_list.public.id]
}
