# NFS shared storage (nfs1)

The 6-node lab stores student photos on NFS so both app servers see the same
uploads directory.

## On nfs1 (192.168.1.17)

```bash
sudo ./setup-nfs-server.sh
```

(or install `nfs-kernel-server` yourself and copy `exports` to `/etc/exports`)

## On app1 (192.168.1.14) and app2 (192.168.1.15)

```bash
sudo ./mount-app-server.sh
```

Then set `UPLOAD_DIR=/opt/dipti/uploads` in the backend environment on both app
servers so photos are written to the share.

In `docker-compose.prod.yml` the shared `uploads_nfs` volume plays the role of
nfs1 on a single machine.
