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

from subprocess import Popen, PIPE, STDOUT, CalledProcessError
from six import iteritems

import Logging

__version__ = "0.2.0"

# BEGIN - SETTINGS
SERVER = "192.168.59.5"
USER = "arista:arista"

IMAGES_URL = "ftp://%s/%s"
REPORTS_URL = "ftp://%s/upload/%s"

IMAGES = collections.OrderedDict([
    # <SKU Regex>, (<Image Filename>, <Expected Version Displayed>, <locator-led>)
    # vEOS
    (r"vEOS", ("vEOS-lab-4.21.2.3F.swi", "4.21.2.3F")),
    
    # 7050QX-32S    4.21.2.3F
    (r"7050QX-32S",  ("EOS-4.21.2.3F.swi", "4.21.2.3F")),
    
    # 7060CX-32S    4.22.1FX-CLI    4.20.3F
    # 7260CX3-64    4.22.1FX-CLI    4.20.3F
    (r"7\d60CX", ("EOS-4.20.3F.swi", "4.20.3F")),
    
    # 7170-64C    4.22.1FX-CLI    4.21.6.1.1F
    (r"7170-64C", ("EOS-4.21.6.1.1F.swi", "4.21.6.1.1F")),

    # 7280QRA-C36M    4.22.1FX-CLI    4.21.2.3F
    (r"7280QRA", ("EOS-4.21.2.3F.swi", "4.21.2.3F")),
    
    # 7280CR2A-60    4.22.1FX-CLI    4.21.2.3F
    (r"7280CR2A", ("EOS-4.21.2.3F.swi", "4.21.2.3F")),
    
    # 7504N, 7508N, 7512N or 7516N  4.22.1FX-CLI    4.21.2.3F
    (r"75\d{2}.?", ("EOS-4.21.2.3F.swi", "4.21.2.3F"))
])

Logging.logD(id="SYS_EVENT_REIMAGE_INFO",
             severity=Logging.logInfo,
             format="%s",
             explanation="[ Informational log message ]",
             recommendedAction=Logging.NO_ACTION_REQUIRED)

Logging.logD(id="SYS_EVENT_REIMAGE_EAPIERR",
             severity=Logging.logError,
             format="%s",
             explanation="[ eAPI command returned an error ]",
             recommendedAction=Logging.NO_ACTION_REQUIRED)

Logging.logD(id="SYS_EVENT_REIMAGE_CALLERR",
             severity=Logging.logError,
             format="%s",
             explanation="[ an attempt to run shell command has failed ]",
             recommendedAction=Logging.NO_ACTION_REQUIRED)

Logging.logD(id="SYS_EVENT_REIMAGE_FAILURE",
             severity=Logging.logError,
             format="%s",
             explanation="[ An unexpected error ]",
             recommendedAction=Logging.NO_ACTION_REQUIRED)

Logging.logD(id="SYS_EVENT_REIMAGE_LED",
             severity=Logging.logWarning,
             format="failed to enable locator LED",
             explanation="[ The led light has failed to turn on ]",
             recommendedAction=Logging.NO_ACTION_REQUIRED)
# END - SETTINGS

os.environ.update({"TERM": "dumb"})

def call(cmd, data=None):
    # Cll runs a shell command and capture output
    # return a tuple containing (stdout, stderr)
    stdout = None
    stderr = None
    err = None

    try:
        proc = Popen(cmd.split(), stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate(data)
        proc.wait()
        code = proc.returncode
        if code > 0:
            err = "'%s' returned error code %d" % (cmd, code)
    except CalledProcessError as e:
        err = e.message
    except IOError as e:
        err = e.strerror

    return stdout, stderr, err

# def cli(cmds):
#     proc = subprocess.Popen(["/usr/bin/Cli", "-p", "15"],
#                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
#
#     for cmd in cmds:
#         proc.stdin.write('%s\n' % cmd)
#
#     proc.stdin.close()
#     proc.wait()
#
#     out = proc.stdout.read()
#     return out

def configure(cmds):
    return eapi(["configure"] + cmds + ["end"])

def cleanup():
    pass

def eapi(cmds, format="json"):
    result = {}
    err = None

    sess = jsonrpclib.Server("unix:///var/run/command-api.sock")

    try:
        result = sess.runCmds(1, cmds, format)
    except jsonrpclib.jsonrpc.ProtocolError as e:
        err = "Error [%d]: %s" % e.message

    return result, err

def enable_locator():
    locators = ["chassis", "module Supervisor1", "module Supervisor2"]

    for l in locators:
        _, err = eapi("locator-led %s" % l)
        if not err:
            return True
    
    return False

def find_image(model):

    for (pattern, details) in iteritems(IMAGES):
        if re.search(pattern, model):
            return details, None

    return None, "No EOS version matched for this SKU"

def get_startup_config():
    result, err = eapi(["show startup-config"], "text")
    if result:
        result = result[0].get("output")

    return result, err

def get_sysinfo():
    result, err = eapi(["show version", "show boot-config"])

    if err:
        return result, err
    
    ver = result[0]
    boot = result[1]
    
    # vEOS has no serial use mac address...
    serial = ver["serialNumber"] or re.sub(r"[\:\.]+", "", ver["systemMacAddress"])
    startup = get_startup_config()
    result = {
        "model": ver["modelName"],
        "image": boot["softwareImage"],
        "version": ver["version"],
        "serial": serial,
        "internal": ver["internalVersion"],
        "revison": ver["hardwareRevision"],
        "start_empty": False if len(startup) > 0 else True
    }
    #logger.debug("Sysinfo: " + str(result))
    return result, err

# def reset():
#     call("rm /mnt/flash/zerotouch-config")
#     call("cat /dev/null > /mnt/flash/startup-config")

def send_report(serial, sysinfo, status="ok", message=""):

    data = {
        "timestamp": datetime.datetime.utcnow(),
        "status": status, 
        "message": message,
        "sysinfo": sysinfo
    }

    data = yaml.safe_dump(data, default_flow_style=False)

    url = REPORTS_URL % (SERVER, serial)
    
    output, stderr, err = call("curl -s -T - -u %s %s"
                               % (USER, url, serial), data)

    if err:
        err = "Failed to upload report: %s" % err
    
    return output, err

def main():
    Logging.log(SYS_EVENT_REIMAGE_INFO, "Getting system info")
    sysinfo, err = get_sysinfo()

    if err:
        # send_report(serial, sysinfo, status="failed",
        #             message=err)
        Logging.log(SYS_EVENT_REIMAGE_EAPIERR, err)
        return 1

    model = sysinfo["model"]
    running = sysinfo["version"]
    serial = sysinfo["serial"]

    # set hostname for logging
    configure(["hostname %s" % serial])

    Logging.log(SYS_EVENT_REIMAGE_INFO, "Sysinfo: SN:%s, Model:%s, Image:%s" %
                (serial, model, running))
    result, err = find_image(model)

    if err:
        Logging.log(SYS_EVENT_REIMAGE_FAILURE, err)
        return 1

    image, version = result

    if running != version:
        Logging.log(SYS_EVENT_REIMAGE_INFO, "loading image '%s'" % image)
        dest = "/mnt/flash/%s" % image
        
        url = IMAGES_URL % (SERVER, image)
        
        _, _, err = call("/usr/bin/curl -s -u %s -o %s %s"
            % (USER, dest, url))
        
        if err:
            Logging.log(SYS_EVENT_REIMAGE_CALL, "failed to copy image: %s" % err)
            return 1

        _, err = configure(["boot system flash:%s" % image])
        if err:
            Logging.log(SYS_EVENT_REIMAGE_EAPIERR, err)
            return 1
        
        Logging.log(SYS_EVENT_REIMAGE_INFO,
                        "system will now reboot to image '%s'" % image)
        
        _, _, err = call("sudo shutdown -r +1")
        if err:
            Logging.log(SYS_EVENT_REIMAGE_FAILURE, err)
            return 1
        Logging.log(SYS_EVENT_REIMAGE_INFO, "system reloading in 1 minute")
    else:
        Logging.log(SYS_EVENT_REIMAGE_INFO, "New image running, erasing configuration...")
        _, err = eapi(["write erase now"])
        if err:
            Logging.log(SYS_EVENT_REIMAGE_FAILURE, err)
            return 1

        Logging.log(SYS_EVENT_REIMAGE_INFO, "startup-config erased")

        eapi(["delete flash:zerotouch-config"])

        Logging.log(SYS_EVENT_REIMAGE_INFO, "zerotouch provisioning re-enabled")
        
        # refresh sysinfo after erasing startup-config
        sysinfo, err = get_sysinfo()
        if err:
            Logging.log(SYS_EVENT_REIMAGE_FAILURE, err)
            return 1
        
        if os.path.exists("/mnt/flash/zerotouch-config"):
            Logging.log(SYS_EVENT_REIMAGE_FAILURE, "Failed to delete zerotouch-config")
            return 1

        _, err = send_report(serial, sysinfo)

        if err:
            Logging.log(SYS_EVENT_REIMAGE_FAILURE, err)
            return 1

        # turn on locator LED
        if enable_locator():
            Logging.log(SYS_EVENT_REIMAGE_INFO, "locator LED enabled")
        else:
            Logging.log(SYS_EVENT_REIMAGE_LED)
        
        Logging.log(SYS_EVENT_REIMAGE_INFO, "reimage complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
