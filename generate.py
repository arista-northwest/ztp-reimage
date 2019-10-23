#!/usr/bin/env python
# -*- coding: utf-8 -*-

import jinja2
import yaml

conf = None
with open("config.yml", "r") as fh:
    conf = yaml.load(fh.read(), Loader=yaml.FullLoader)

def write_file(contents, file):
    with open(file, "w") as fh:
        fh.write(contents)

with open("reimage.py.j2", "r") as fh:
    tpl = jinja2.Template(fh.read())
    out = tpl.render(conf)
    write_file(out, "reimage.py")

with open("startup-config.j2", "r") as fh:
    tpl = jinja2.Template(fh.read())
    out = tpl.render(conf)
    write_file(out, "startup-config")

with open("dhcpd.conf.j2", "r") as fh:
    tpl = jinja2.Template(fh.read())
    out = tpl.render(conf)
    write_file(out, "dhcpd.conf")


