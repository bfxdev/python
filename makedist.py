#!/usr/bin/env python
# -*- coding: utf-8 -*-
#        1         2         3         4         5         6         7         8         9        9
# 3456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789

"""
Packs all Python executable scripts and modules into executable modules.
"""

__version__ = "0.1-draft1"

# Revisions
# 0.1-draft1 : First usable version

# Imports
import os, subprocess, zipfile

#import xml.etree.ElementTree as ET
#import bfcommons, zipfile

class ExecutableArchive(zipfile.ZipFile):

  def __init__(self, scriptname):
    """Prepares object for archive creation"""

    assert os.path.isfile(scriptname)

    # Stores parameters for later use
    self.scriptname = scriptname

    # Splits input path
    root, ext = os.path.splitext(scriptname)
    dir, basefile = os.path.split(root)

    # Retrieves version of the script (assuming using bfScriptInterface or similar)
    version = subprocess.check_output(['python', scriptname, 'version']).strip()

    self.dest = os.path.join(dir, "dist", basefile +  "-" + version + ext)

    zipfile.ZipFile.__init__(self, self.dest, 'w')

    print "Packing", self.dest


  def addContent(self, dirs, filenames = []):
    """Adds a list of directories and optionally additional files"""
    # TODO: add support for additional files

    # Adds main script
    self.write(self.scriptname, "__main__.py")

    # Adds directories
    for d in dirs:
      for dirpath, dirnames, names in os.walk(d):
        for name in names:
          self.write(os.path.join(dirpath, name))


if __name__ == '__main__':

  e = ExecutableArchive("regulog.py")
  e.addContent(["bfcommons"])
  e.close()
