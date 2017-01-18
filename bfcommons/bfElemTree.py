#!/usr/bin/env python
# -*- coding: utf-8 -*-
#        1         2         3         4         5         6         7         8         9        9
# 3456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
"""
ElemTree: Wrapper for ElementTree library 2.7 with additional functions to support:
           - XML pretty printing
           - CDATA

Import it in place of ElementTree with: import bfcommons.bfElemTree as ET

BF 2016
"""

__version__ = "0.1.1"

# TODO find/findall with more complex XPath

# Revisions:
# 0.1.0 : First version
# 0.1.1 : Explicit declaration of some of the classes to support code completion in editor

# Imports
import xml.etree.ElementTree as ET
from types import MethodType
import sys, inspect

# Copies the content of the ET module into this one
g = globals()
for name, obj in inspect.getmembers(ET):
  if name[:2] != "__":
    #print "copies", name, ":", obj
    g[name] = obj

# Affectations done another time to support contextual help while editing
tostring = ET.tostring
fromstring = ET.fromstring
dump = ET.dump
Element = ET.Element
ElementTree = ET.ElementTree
SubElement = ET.SubElement


# ------------------------- CDATA support adapted from gist.github.com/zlalanne/5711847
# Defines new function to be added as method, appending a new Element to the current one
def appendCDATA(self, text):
  """Appends a CDATA object containing the given text, returns CDATA Element"""

  # Adds new Element with tag "![CDATA["
  element = SubElement(self, '![CDATA[')
  element.text = text
  return element

# Adds method as "unbound method" to Element
Element.appendCDATA = MethodType(appendCDATA, None, Element)

# Saves original serialize method
_original_serialize_xml = _serialize_xml

# Defines new function to replace standard serialize function
def _serialize_xml(write, elem, encoding, qnames, namespaces):
  if elem.tag == '![CDATA[':
    write("<%s%s]]>%s" % (elem.tag, elem.text, elem.tail if elem.tail else ""))
    return
  return _original_serialize_xml(write, elem, encoding, qnames, namespaces)

# Replace global function in original module
ET._serialize_xml    = _serialize_xml
ET._serialize['xml'] = _serialize_xml
# --------------------------------------------

# -- XML pretty print adapted from http://effbot.org/zone/element-lib.htm
def indent(self, level=0):

  # Defines prefix to add to line depending on level
  itail = "\n" + level*"  "

  # TODO Explicit cases and re-check if all combinations produce the wanted output
  # Case of Element containing other elements
  if len(self) and self[0].tag != '![CDATA[':

    if not self.text or not self.text.strip():
      self.text = itail + "  "
    if not self.tail or not self.tail.strip():
      self.tail = itail
    for elem in self:
      indent(elem, level+1)
    if not elem.tail or not elem.tail.strip():
      elem.tail = itail
  else:
    if level and (not self.tail or not self.tail.strip()):
      self.tail = itail

Element.indent = MethodType(indent, None, Element)

# -------------------------


def main(argv):
  """Main procedure for command line processing and/or HMI"""

  template = """<RegulogEvents xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'
                xsi:noNamespaceSchemaLocation='regulog.xsd'/>"""

  #template = """<RegulogEvents/>"""

  elem = fromstring(template)

  elem.append(Element("Data1"))
  elem.append(Element("Data2"))
  elem.append(Element("Data3"))
  elem.find("Data2").appendCDATA("Data2 text in CDATA")
  elem.find("Data3").text = "Text before CDATA"
  elem.find("Data3").appendCDATA("Text in CDATA").tail = "Text after CDATA"
  elem.text = "RegulogEvents text"

  print "\nwrite to stdout before indent:"
  ElementTree(elem).write(sys.stdout, 'utf-8', True)

  print "\n\ntostring before indent:\n", tostring(elem)

  print "\ndump before indent:"
  dump(elem)

  elem.indent()

  print "\nwrite to stdout after indent:"
  ElementTree(elem).write(sys.stdout, 'utf-8', True)

  print "\n\ntostring after indent:\n", tostring(elem)

  print "dump after indent:"
  dump(elem)


# Real start of the script
if __name__ == "__main__":
  main(sys.argv[1:])
  sys.exit(0)


