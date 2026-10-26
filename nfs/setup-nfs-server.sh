#!/bin/bash
# Run as root on nfs1 (192.168.1.17). Sets up the shared uploads export.
set -euo pipefail
APP_SUBNET_HOSTS="192.168.1.14 192.168.1.15"
EXPORT_DIR="/srv/dipti/uploads"

apt -y install nfs-kernel-server
mkdir -p "$EXPORT_DIR"
chown nobody:nogroup "$EXPORT_DIR"

cat >/etc/exports <<CONF
$EXPORT_DIR ${APP_SUBNET_HOSTS// /,}(rw,sync,no_subtree_check,no_root_squash) \
CONF
sed -i 's/,/ /g;s/\\//' /etc/exports   # keep one host-per-line style readable
exportfs -ra
systemctl enable --now nfs-kernel-server
echo "NFS export ready: showmount -e 192.168.1.17"
