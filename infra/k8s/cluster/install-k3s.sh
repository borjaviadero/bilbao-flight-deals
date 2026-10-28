#!/usr/bin/env bash
# Install (or upgrade to) a pinned k3s on the server. Runs ON the server as root:
#   ssh ubuntu@<server> 'sudo bash -s' < infra/k8s/cluster/install-k3s.sh   (make k3s-install)
# Safe to run again: the k3s installer is idempotent and the firewall rules are added once.

set -euo pipefail

K3S_VERSION="${K3S_VERSION:-v1.35.5+k3s1}" # same minor as the local k3d test cluster

echo "==> Firewall: let pod and service traffic through"
# Oracle's Ubuntu images ship iptables rules that reject everything but SSH. k3s pods
# (10.42.0.0/16) and services (10.43.0.0/16) must be able to talk to each other on the
# node; nothing new is opened to the internet (OCI's security list still allows only SSH).
for cidr in 10.42.0.0/16 10.43.0.0/16; do
  iptables -C INPUT -s "$cidr" -j ACCEPT 2>/dev/null || iptables -I INPUT -s "$cidr" -j ACCEPT
done
if command -v netfilter-persistent >/dev/null; then netfilter-persistent save; fi

echo "==> k3s ${K3S_VERSION}"
# --disable traefik,servicelb : no ingress or load balancer needed (nothing is exposed)
# --secrets-encryption        : Kubernetes Secrets encrypted at rest on the server's disk
# --write-kubeconfig-mode 600 : the admin kubeconfig is readable by root only
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" sh -s - server \
  --disable traefik \
  --disable servicelb \
  --secrets-encryption \
  --write-kubeconfig-mode 600

echo "==> Waiting for the node to be Ready"
for _ in $(seq 1 30); do
  if k3s kubectl get nodes 2>/dev/null | grep -q " Ready "; then break; fi
  sleep 5
done
k3s kubectl get nodes -o wide
k3s --version
