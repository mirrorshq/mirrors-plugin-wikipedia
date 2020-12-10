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
        runMode = json.loads(sys.argv[1])["run-mode"]
        dataDir = json.loads(sys.argv[1])["storage-file"]["data-directory"]

        if runMode == "init":
            _init(dataDir, sock)
        elif runMode == "update":
            _update(dataDir, sock)
        else:
            assert False


def _init(dataDir, sock):
    # find downloaded tar data file
    dstFile = None
    dstMd5File = None
    if True:
        tlist = glob.glob(os.path.join(dataDir, "*.tar"))
        tlist = [x for x in tlist if os.path.exists(x + ".md5")]
        if len(tlist) > 0:
            dstFile = tlist[-1]
            dstMd5File = dstFile + ".md5"
            _Util.deleteDirContent(dataDir, [dstFile, dstMd5File])
        else:
            _Util.deleteDirContent(dataDir)

    # check tar data file, download if needed
    if dstFile is None or not _Util.verifyFile(dstFile, dstMd5File):
        # clear history
        dstFile = None
        dstFileUrl = None
        _Util.deleteDirContent(dataDir)

        # get tar data file url
        url = "https://mirrors.tuna.tsinghua.edu.cn/wikipedia-monthly"
        resp = urllib.request.urlopen(url, timeout=60, cafile=certifi.where())
        root = lxml.html.parse(resp)
        for trElem in root.xpath(".//table[@id='list']/tbody/tr"):
            aTag = trElem.xpath("./td")[0].xpath("./a")[0]
            m = re.fullmatch("wikipedia-[0-9]+\\.tar", aTag.text)
            if m is not None and (dstFile is None or dstFile < m.group(0)):
                dstFile = os.path.join(dataDir, m.group(0))
                dstFileUrl = os.path.join(url, aTag.get("href"))
                dstMd5File = dstFile + ".md5"
                dstMd5FileUrl = dstFileUrl + ".md5"
        if dstFile is None:
            raise Exception("no tar data file found")

        # download md5 file
        print("Download \"%s\"." % (dstMd5FileUrl))
        _Util.wgetDownload(dstMd5FileUrl, dstMd5File)
        sock.progress_changed(5)

        # download data file
        print("Download \"%s\"." % (dstFileUrl))
        _Util.wgetDownload(dstFileUrl, dstFile)
        if not _Util.verifyFile(dstFile, dstMd5File):
            raise Exception("the downloaded file is corrupt")
    sock.progress_changed(50)

    # extract
    # sometimes tar file contains minor errors
    print("Extract \"%s\"." % (dstFile))
    _Util.shellCallIgnoreResult("/bin/tar -x --strip-components=1 -C \"%s\" -f \"%s\"" % (dataDir, dstFile))
    sock.progress_changed(60)

    # sync
    print("Synchonize.")
    with _TempChdir(dataDir):
        _Util.cmdExec("/usr/bin/repo", "sync")
    sock.progress_changed(99)

    # all done, delete the tar data file and md5 file
    _Util.forceDelete(dstFile)
    _Util.forceDelete(dstMd5File)
    sock.progress_changed(100)


def _update(dataDir, sock):
    with _TempChdir(dataDir):
        _Util.cmdExec("/usr/bin/repo", "sync")


class _Util:

    @staticmethod
    def deleteDirContent(path, fullfnIgnoreList=[]):
        for fn in os.listdir(path):
            fullfn = os.path.join(path, fn)
            if fullfn in fullfnIgnoreList:
                continue
            _Util.forceDelete(fullfn)

    @staticmethod
    def readFile(filename):
        with open(filename) as f:
            return f.read()

    @staticmethod
    def verifyFile(filename, md5Filename):
        with open(filename, "rb") as f:
            thash = hashlib.md5()
            while True:
                block = f.read(65536)
                if len(block) == 0:
                    break
                thash.update(block)
            return thash.hexdigest() == _Util.readFile(md5Filename)

    @staticmethod
    def wgetDownload(url, localFile=None):
        param = _Util.wgetCommonDownloadParam().split()
        if localFile is None:
            _Util.cmdExec("/usr/bin/wget", *param, url)
        else:
            _Util.cmdExec("/usr/bin/wget", *param, "-O", localFile, url)

    @staticmethod
    def wgetCommonDownloadParam():
        return "-q --show-progress -t 0 -w 60 --random-wait -T 60 --passive-ftp"

    @staticmethod
    def forceDelete(filename):
        if os.path.islink(filename):
            os.remove(filename)
        elif os.path.isfile(filename):
            os.remove(filename)
        elif os.path.isdir(filename):
            shutil.rmtree(filename)

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


class _TempChdir:

    def __init__(self, dirname):
        self.olddir = os.getcwd()
        os.chdir(dirname)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        os.chdir(self.olddir)


###############################################################################

if __name__ == "__main__":
    main()
