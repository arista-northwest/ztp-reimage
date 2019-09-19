#!/usr/bin/env python
from __future__ import print_function

import collections
import json
import os
import re
import subprocess
import sys
import datetime

import jsonrpclib
import yaml

from subprocess import Popen, PIPE, STDOUT
from six import iteritems

__version__ = "0.1.3"

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

def cli(cmds, format="json"):
    sess = jsonrpclib.Server("unix:///var/run/command-api.sock")
    result = sess.runCmds(1, cmds, format)

    return result

def configure(cmds):
    return cli(["configure"] + cmds + ["end"])

def get_startup_config():
    result = cli(["show startup-config"], "text")[0]
    if "output" not in result:
        print("Failed to get startup-config")
        sys.exit(1)
    
    return result["output"]

def get_sysinfo():
    result = cli(["show version", "show boot-config"])

    ver = result[0]
    boot = result[1]
    
    # vEOS has no serial use mac address...
    serial = ver["serialNumber"] or re.sub(r"[\:\.]+", "", ver["systemMacAddress"])
    startup = get_startup_config()
    return {
        "model": ver["modelName"],
        "image": boot["softwareImage"],
        "version": ver["version"],
        "serial": serial,
        "internal": ver["internalVersion"],
        "revison": ver["hardwareRevision"],
        "start_empty": False if len(startup) > 0 else True
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
        cli(["write erase now"])

        try:
            cli(["delete flash:zerotouch-config"])
        except jsonrpclib.jsonrpc.ProtocolError:
            pass

        # refresh sysinfo after erasing startup-config
        sysinfo = get_sysinfo()
        
        if not sysinfo["start_empty"]:
            print("Startup config is not empty")
            sys.exit(1)

        if os.path.exists("/mnt/flash/zerotouch-config"):
            print("Failed to delete zerotouch-config")
            sys.exit(1)

        report_ok = send_report(serial, sysinfo)

        if not report_ok:
            print("Failed to upload report")
            sys.exit(1)

        # turn on locator LED
        if locator:
            cli(["locator-led %s" % locator])

if __name__ == "__main__":
    main()
