#!/bin/sh

FTP_SERVER=192.168.59.5
FTP_USER=arista:arista
IMAGE=vEOS-lab-4.21.2.3F.swi
VERSION=4.21.2.3F

SHVER=`Cli -p 15 -c 'show version'`
RUNNING=`echo "${SHVER}" | grep -oP 'Software image version:\s+\K[^$]+'`
SERIAL=`echo "${SHVER}" | grep -oP 'Serial number:\s+\K[^$]+'`

if [ -z ${SERIAL} ]; then
    SERIAL=`echo "${SHVER}" | grep -oP 'System MAC address:\s+\K[^$]+'`
fi

if [ "${RUNNING}" != "${VERSION}" ]; then
    curl -s ftp://${FTP_SERVER}/${IMAGE} -u ${FTP_USER} -o /mnt/flash/${IMAGE}
    cat << EOF | Cli -p 15
configure
boot system flash:${IMAGE}
reload now
EOF
else
    echo "${SHVER}" | curl -T - -u ${FTP_USER} ftp://${FTP_SERVER}/upload/${SERIAL} && \
    sleep 60 && \
    rm /mnt/flash/startup-config && \
    rm /mnt/flash/zerotouch-config && \
    sudo shutdown now
fi