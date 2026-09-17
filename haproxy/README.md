# HAProxy + Keepalived (lb1 + lb2)

This folder holds the **real, deployable configs** for the HA pair — `haproxy.cfg` goes to both load balancers unchanged, and each node gets its own `keepalived-lb*.conf`:

| File | Target host | Notes |
|------|-------------|-------|
| `haproxy.cfg`          | lb1 **and** lb2 | identical on both |
| `keepalived-lb1.conf`  | lb1 (192.168.1.11) | MASTER, priority 100 |
| `keepalived-lb2.conf`  | lb2 (192.168.1.12) | BACKUP, priority 99 |

Shared VIP: **192.168.1.13** (matches the infrastructure plan in the repo README). A `chk_haproxy` track script fails the VIP over to the other node if the local HAProxy process dies — not just when the whole machine goes down.

#### ⚙️ Step 3: Setup HAProxy (lb1 + lb2)

- **Install HAProxy + Keepalived on lb1 and lb2:**

```sh
sudo apt -y install haproxy keepalived openssl
sudo mkdir -p /etc/haproxy/certs
sudo openssl req -new -x509 -days 365 -nodes \
  -out /etc/haproxy/certs/haproxy.pem -keyout /etc/haproxy/certs/haproxy.pem
sudo chmod 600 /etc/haproxy/certs/haproxy.pem
```

- **Deploy HAProxy config (identical on lb1 + lb2):**

```sh
sudo cp haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg
sudo haproxy -c -f /etc/haproxy/haproxy.cfg    # validate before restarting
```

> ⚠️ Change the `stats auth` password in `/etc/haproxy/haproxy.cfg` — port 8404 exposes the whole backend pool state and must never sit on a LAN with a known default password.

- **Deploy Keepalived config (per node):**

```sh
# on lb1:
sudo cp haproxy/keepalived-lb1.conf /etc/keepalived/keepalived.conf
# on lb2:
sudo cp haproxy/keepalived-lb2.conf /etc/keepalived/keepalived.conf

# then on BOTH nodes: adjust `interface` to your actual NIC
ip link                       # find your NIC name (eth0, ens33, ens160, ...)
sudo sed -i 's/ens33/eth0/' /etc/keepalived/keepalived.conf
```

- **Start and verify:**

```sh
sudo systemctl restart haproxy keepalived
sudo systemctl status haproxy keepalived
ip addr show                   # the VIP 192.168.1.13 should float on the MASTER
curl -k https://192.168.1.13/  # served through the VIP
```

- **Test the failover** (the whole point of the pair):

```sh
# on lb1 (MASTER):
sudo systemctl stop haproxy
# within ~2-5s the VIP moves to lb2; check on lb2:
ip addr show    # 192.168.1.13 now floats here
# start it again and watch the VIP return (priority 100 > 99)
sudo systemctl start haproxy
```
