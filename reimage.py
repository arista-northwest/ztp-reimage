#!/usr/bin/env python
from __future__ import print_function
import collections
import json
import os
import re
import subprocess
import time
from subprocess import Popen, PIPE, STDOUT

from six import iteritems

FTP_SERVER = "192.168.59.5"
FTP_USER = "arista:arista"

os.environ.update({"TERM": "dumb"})

IMAGES = collections.OrderedDict([
    # <SKU Regex>: (<Image Filename>, <Expected Version Displayed>)
    (r"vEOS", ("vEOS-lab-4.21.2.3F.swi", "4.21.2.3F")),
    #r"DCS-7050QX-32S-F":  ("EOS-4.21.2.3F.swi", "4.21.2.3F"),
    (r"DCS-7508", ("EOS-DPE-4.21.2.3F.swi", "4.21.2.3F-DPE")),
    (r".*", ("EOS-DPE-4.21.2.3F.swi", "4.21.2.3F-DPE"))
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

def get_image(model):
    for (pattern, image) in iteritems(IMAGES):
        if re.match(pattern, model):
            return image
    
    # return the last image if we get here
    return IMAGES.values()[-1]

def main():
    sysinfo = get_sysinfo()
    model = sysinfo["model"]
    running = sysinfo["version"]
    image, version = get_image(model)

    if running != version:
        dest = "/mnt/flash/%s" % image
       
        subprocess.check_output([
            "/usr/bin/curl", "-s",
            "ftp://%s/%s" % (FTP_SERVER, image),
            "-u", FTP_USER,
            "-o", dest])

        #if os.path.exists(dest):
        configure(["boot system flash:%s" % image])
        cli(["reload now"])
    else:
        proc = Popen([
            "curl", "-T", "-", "-u", FTP_USER,
            "ftp://%s/upload/%s" % (FTP_SERVER, sysinfo["serial"])
        ], stdin=PIPE, stdout=PIPE)

        proc.communicate(json.dumps(sysinfo, indent=4, separators=(",", ": ")) + "\n")
        cli(["write erase now", "delete flash:zerotouch-config"])

if __name__ == "__main__":
    main()
