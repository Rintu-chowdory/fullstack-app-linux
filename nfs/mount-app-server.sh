#!/bin/bash
# Run as root on app1/app2. Mounts the shared uploads dir from nfs1.
set -euo pipefail
NFS_SERVER="${NFS_SERVER:-192.168.1.17}"
MOUNT_POINT="/opt/dipti/uploads"

apt -y install nfs-common
mkdir -p "$MOUNT_POINT"
grep -q "$NFS_SERVER:/srv/dipti/uploads" /etc/fstab || \
  echo "$NFS_SERVER:/srv/dipti/uploads $MOUNT_POINT nfs4 defaults,_netdev 0 0" >>/etc/fstab
mount "$MOUNT_POINT"
echo "Mounted: $(findmnt -n -o SOURCE,TARGET $MOUNT_POINT)"
echo "Set UPLOAD_DIR=$MOUNT_POINT in the backend .env on this host."
