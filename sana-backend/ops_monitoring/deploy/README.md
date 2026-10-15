# GPS network capture permissions (Ubuntu)

The Django backend must continue running as the unprivileged `iraj` account. Do **not** run the backend as root and do not grant broad packet-capture capabilities to the Python interpreter.

First pull the backend change and wrapper script, then install the fixed-filter, root-owned wrapper and allow only that command through sudo:

```bash
cd ~/Desktop/SANA
git pull --ff-only origin main
sudo install -o root -g root -m 0755 sana-backend/ops_monitoring/deploy/sana-gps-network-capture /usr/local/sbin/sana-gps-network-capture
printf '%s\n' 'iraj ALL=(root) NOPASSWD: /usr/local/sbin/sana-gps-network-capture' | sudo tee /etc/sudoers.d/sana-gps-network-capture >/dev/null
sudo chown root:root /etc/sudoers.d/sana-gps-network-capture
sudo chmod 0440 /etc/sudoers.d/sana-gps-network-capture
sudo visudo -cf /etc/sudoers.d/sana-gps-network-capture
```

The wrapper accepts no arguments and captures only TCP port 9000 and UDP port 9001. Verify it can start (stop it with Ctrl+C after confirming output):

```bash
sudo -n /usr/local/sbin/sana-gps-network-capture
```

Then restart only the Django API service:

```bash
sudo systemctl restart sana-backend.service
sudo systemctl status sana-backend.service --no-pager
```

The GPS listener itself does not need to restart for this permission change. Access to the monitoring page remains restricted to site administrators.
