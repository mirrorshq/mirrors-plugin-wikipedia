#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import json
import time
import glob
import shutil
import hashlib
import certifi
import subprocess
import lxml.html
import urllib.request
import mirrors.plugin


def main():
    with mirrors.plugin.ApiClient() as sock:
        dataDir = json.loads(sys.argv[1])["storage-file"]["data-directory"]

        dumpsDataDir = os.path.join(dataDir, "dumps")
        dumpsRsyncSource = "rsync://ftp.acc.umu.se/mirror/wikimedia.org/dumps"
        _Util.cmdExec("/usr/bin/rsync", "-v", "-a", "-z", "-H", "--delete", dumpsRsyncSource, dumpsDataDir)

        # FIXME
        # step 1: download dumps files
        # step 2: auto newest import dumps files into mariadb


class _Util:

    @staticmethod
    def cmdExec(cmd, *kargs):
        # call command to execute frontend job
        #
        # scenario 1, process group receives SIGTERM, SIGINT and SIGHUP:
        #   * callee must auto-terminate, and cause no side-effect
        #   * caller must be terminate AFTER child-process, and do neccessary finalization
        #   * termination information should be printed by callee, not caller
        # scenario 2, caller receives SIGTERM, SIGINT, SIGHUP:
        #   * caller should terminate callee, wait callee to stop, do neccessary finalization, print termination information, and be terminated by signal
        #   * callee does not need to treat this scenario specially
        # scenario 3, callee receives SIGTERM, SIGINT, SIGHUP:
        #   * caller detects child-process failure and do appopriate treatment
        #   * callee should print termination information

        # FIXME, the above condition is not met, _Util.shellExec has the same problem

        ret = subprocess.run([cmd] + list(kargs), universal_newlines=True)
        if ret.returncode > 128:
            time.sleep(1.0)
        ret.check_returncode()

    @staticmethod
    def shellCallIgnoreResult(cmd):
        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            time.sleep(1.0)


###############################################################################

if __name__ == "__main__":
    main()
