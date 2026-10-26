#!/bin/sh
set -e
: "${STATS_USER:=admin}"
: "${STATS_PASSWORD:=change-me-stats}"
: "${APP1_HOST:=app1-frontend}"
: "${APP2_HOST:=app2-frontend}"

if [ "${KEEPALIVED_ENABLED:-0}" = "1" ]; then
    sed -e "s/@ROLE@/${KEEPALIVED_ROLE:-BACKUP}/" \
        -e "s/@PRIORITY@/${KEEPALIVED_PRIORITY:-100}/" \
        -e "s/@VIP@/${KEEPALIVED_VIP}/" \
        -e "s/@SELF_IP@/${KEEPALIVED_SELF_IP}/" \
        -e "s/@PEER_IP@/${KEEPALIVED_PEER_IP}/" \
        -e "s/@VRRP_PASSWORD@/${VRRP_PASSWORD:-dipti-vrrp}/" \
        /etc/keepalived/keepalived.conf.template > /etc/keepalived/keepalived.conf
    echo "starting keepalived (role=${KEEPALIVED_ROLE:-BACKUP}, vip=${KEEPALIVED_VIP})"
    keepalived -f /etc/keepalived/keepalived.conf --dont-fork --log-console &
fi

echo "starting haproxy"
exec haproxy -db -f /usr/local/etc/haproxy/haproxy.cfg
