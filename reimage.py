#!/usr/bin/env python
from __future__ import print_function

import collections
import json
import os
import re
import subprocess
import sys
import datetime
import yaml

from subprocess import Popen, PIPE, STDOUT

from six import iteritems

__version__ = "0.1.1"

FTP_SERVER = "192.168.59.5"
FTP_USER = "arista:arista"

os.environ.update({"TERM": "dumb"})

IMAGES = collections.OrderedDict([
    # <SKU Regex>, <Image Filename>, <Expected Version Displayed>, <locator-led>
    # vEOS
    (r"vEOS", ("vEOS-lab-4.21.2.3F.swi", "4.21.2.3F", "")),
    
    # 7050QX-32S    4.21.2.3F
    (r"7050QX-32S",  ("EOS-4.21.2.3F.swi", "4.21.2.3F", "chassis")),
    
    # 7060CX-32S    4.22.1FX-CLI    4.20.3F
    # 7260CX3-64    4.22.1FX-CLI    4.20.3F
    (r"7\d60CX", ("EOS-4.20.3F.swi", "4.20.3F", "chassis")),
    
    # 7170-64C    4.22.1FX-CLI    4.21.6.1.1F
    (r"7170-64C", ("EOS-4.21.6.1.1F.swi", "4.21.6.1.1F", "chassis")),

    # 7280QRA-C36M    4.22.1FX-CLI    4.21.2.3F
    (r"7280QRA", ("EOS-4.21.2.3F.swi", "4.21.2.3F", "chassis")),
    
    # 7280CR2A-60    4.22.1FX-CLI    4.21.2.3F
    (r"7280CR2A", ("EOS-4.21.2.3F.swi", "4.21.2.3F", "chassis")),
    
    # 7504N, 7508N, 7512N or 7516N  4.22.1FX-CLI    4.21.2.3F
    (r"75\d{2}.?", ("EOS-4.21.2.3F.swi", "4.21.2.3F", "module Supervisor 1")),

    (r".*", (None, None, ""))
])

def cli(cmds):
    proc = subprocess.Popen(["/usr/bin/Cli", "-p", "15"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    
    for cmd in cmds:
        proc.stdin.write('%s\n' % cmd)
    
    proc.stdin.close()
    proc.wait()

    out = proc.stdout.read()
    return out

def configure(cmds):
    return cli(["configure"] + cmds + ["end"])

def get_sysinfo():
    ver = json.loads(cli(["show version | json"]))
    boot = json.loads(cli(["show boot-config | json"]))
    
    # vEOS has no serial use mac address...
    serial = ver["serialNumber"] or re.sub(r"[\:\.]+", "", ver["systemMacAddress"])
    
    return {
        "model": ver["modelName"],
        "image": boot["softwareImage"],
        "version": ver["version"],
        "serial": serial,
        "internal": ver["internalVersion"],
        "revison": ver["hardwareRevision"]
    }

def find_image(model):
    for (pattern, details) in iteritems(IMAGES):
        if re.search(pattern, model):
            return details

    return IMAGES.values()[-1]

def send_report(serial, sysinfo, status="ok", message=""):

    data = {
        "timestamp": datetime.datetime.utcnow(),
        "status": status, 
        "message": message,
        "sysinfo": sysinfo
    }
    
    proc = Popen([
        "curl", "-T", "-", "-u", FTP_USER,
        "ftp://%s/upload/%s" % (FTP_SERVER, serial)
    ], stdin=PIPE, stdout=PIPE)

    proc.communicate(yaml.safe_dump(data, default_flow_style=False))

    proc.wait()
    code = proc.returncode

    return True if code == 0 else False

def main():
    sysinfo = get_sysinfo()
    model = sysinfo["model"]
    running = sysinfo["version"]
    serial = sysinfo["serial"]

    image, version, locator = find_image(model)
    
    if not image:
        send_report(serial, sysinfo, status="failed",
            message="No EOS version matched for this SKU")
        sys.exit(1)

    if running != version:
        dest = "/mnt/flash/%s" % image
       
        subprocess.check_output([
            "/usr/bin/curl", "-s",
            "ftp://%s/%s" % (FTP_SERVER, image),
            "-u", FTP_USER,
            "-o", dest])

        if not os.path.exists(dest):
            send_report(serial, sysinfo, status="failed", message="failed to copy image")
            sys.exit(1)

        configure(["boot system flash:%s" % image])
        cli(["reload now"])
    else:
        send_report(serial, sysinfo)
        cli(["write erase now", "delete flash:zerotouch-config"])

        # turn on locator LED
        if locator:
            cli(["locator-led %s" % locator])

if __name__ == "__main__":
    main()
