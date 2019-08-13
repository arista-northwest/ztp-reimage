#!/bin/sh

FTP_SERVER=192.168.59.5
FTP_USER=arista:arista
IMAGE=vEOS-lab-4.21.2.3F.swi
VERSION=4.21.2.3F

RUNNING=`Cli -p 15 -c 'show version' | grep 'Software image version:' | awk '{print $NF}'`

if [ ${RUNNING} != ${VERSION} ]; then
    curl -s ftp://${FTP_SERVER}/${IMAGE} -u ${FTP_USER} -o /mnt/flash/${IMAGE}
    cat << EOF | Cli -p 15
configure
boot system flash:${IMAGE}
reload now
EOF
else
    sleep 60 && \
    rm /mnt/flash/startup-config && \
    rm /mnt/flash/zerotouch-config && \
    sudo shutdown now
fi