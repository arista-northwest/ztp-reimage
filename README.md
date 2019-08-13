# ZTP Reimage Sample

## Setup

Subnet: 192.168.59.0/24
HTTP/FTP/DHCP Server: 192.168.59.5
FTP Username/Password: arista/arista

## Installation

```

# Lab only.  insecure :)
setenfoce 0
# disable selinux on reboot
sed -i.bak 's/\(SELINUX\)=enforcing/\1=passive/' /etc/selinux/config
systemctl disable firewalld

yum install -y dhcp
yum install -y vsftpd
yum install –y epel-release
yum install -y nginx

# enable sevices on boot
systemctl enable dhcpd
systemctl enable vsftpd
systemctl enable nginx

# make sure they're all running
systemctl restart nginx
systemctl restart vsftpd

copy etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf

systemctl restart dhcpd

copy startup-config reimage.sh /usr/share/nginx/html/
copy <eos-images> /home/arista
```

## Process

SWITCH | -- DHCP REQUEST            -> | ZTP DHCP Server
SWITCH | <- DHCP OFFER              <- | ZTP DHCP Server
SWITCH | -- HTTP GET startup-config -> | ZTP HTTP Server
SWITCH | -- RELOAD #1               -- | 
SWTICH | -- HTTP GET reimage.sh     -> | ZTP HTTP Server
SWITCH | -- FTP GET <eosimage>      -- | ZTP FTP Server
SWITCH | -- RELOAD #2               -- |
SWTICH | -- HTTP GET reimage.sh     -> | ZTP HTTP Server
SWITCH | -- VERIFY software version -- |
SWITCH | -- ERASE config            -- |
SWITCH | -- SHUTDOWN                -- |
