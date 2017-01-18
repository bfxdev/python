#!/usr/bin/env python
# -*- coding: utf-8 -*-
#        1         2         3         4         5         6         7         8         9        9
# 3456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
"""
RichHTMLDocument: Serializable HTML document with headers, text formatting, tables and graphs.
Version VERSION - BF 2017
"""

__version__ = "0.1-draft1"

# Re-work docstring to insert version from single definition
__doc__ = __doc__.replace("VERSION", __version__)

# Revisions:
# 0.1 : First version

# Imports
import sys
import bfElemTree as ET
#import xml.etree.ElementTree as ET

class RichHTMLDocument(ET.Element):
  """HTML Document with formatting and graphs"""

  def __init__(self):
    """Inits an empty document"""

    ET.Element.__init__(self, 'html')

    self.cursors = list()
    self.cursor = self
    self.saveCursor()

    self.add(tag="head", html="""
        <style type='text/css'>
          table, td, th {border:1px solid black;border-collapse:collapse;padding:3px;margin:5px;}
          br {mso-data-placement:same-cell}
          th {background-color:lightgrey}
        </style>""")

    self.add(tag="body", style="font-family:arial;")

    self.setCursor('body')

  def __str__(self):
    """Returns a string version of the document"""
    self.indent()
    return ET.tostring(self)

  def write(self, file):
    """Stores the document to open file or filename"""

    self.indent()
    ET.ElementTree(self).write(file, method='xml')


  def setCursor(self, searchstring):
    """Sets the cursor to an encapsulating element using searchstring. XML elements
       are searched in the following order: str as id, then as xpath if id not found"""

    # Searche Element using its id, if defined
    res = self.find('.//*[@id="' + searchstring + '"]')

    # If not found, searches as XPath
    if res is None:
      res = self.find(searchstring)

    # If found, sets the cursor, if not raises an exception
    if res is None:
      raise RuntimeError("String '" + searchstring + "' not found in document")
    else:
      self.cursor = res

    return res

  def getCursor(self):
    return self.cursor

  def saveCursor(self):
    self.cursors.append(self.cursor)

  def restoreCursor(self):
    self.cursor = self.cursors.pop()


  def add(self, html=None, text=None, tag=None, id=None, style=None):
    """Adds data at cursor position, i.e. at the end of the pointed tag, depending on arguments:
       - html: if defined, adds given data as text containing formatting tags ("<" and ">"
          not escaped)
       - text: if defined, adds given text as such, and escapes chars wherever necessary
       - tag, id, style: if defined, encloses everything in a tag with id and style"""

    # If html is given, converts data to temporary element
    helem = None
    if html is not None and len(html) > 0:
      helem = ET.fromstring("<dummy>" + html + "</dummy>")
      print ">>helem>>", ET.tostring(helem)


    # If tag is defined, creates a new element with given attributes and retrieve data
    telem = None
    if tag is not None and len(tag)>0:

      # Creates tag with attributes
      attrs = dict()
      if id and len(id) > 0:
        attrs['id'] = id
      if style and len(style) > 0:
        attrs['style'] = style
      telem = ET.Element(tag, attrs)

      # Propagates data from helem if defined
      if helem is not None:
        telem.text = helem.text
        telem.tail = helem.tail     # should be None in all cases
        telem.extend(helem.findall("./*"))
        print ">>telem>>", ET.tostring(telem)

      # Adds the created tag at cursor position
      self.cursor.append(telem)

    # If tag is not defined but helem defined, adds data at end of current location
    elif helem is not None:
      l = self.cursor.findall("./*")
      if helem.text is not None:
        if len(l) == 0:
          self.cursor.text = (self.cursor.text if self.cursor.text is not None else "") + helem.text
        else:
          l[-1].tail = (l[-1].tail if l[-1].tail is not None else "") + helem.text

      self.cursor.extend(helem.findall("./*"))


    # If text is defined appends it
    if text is not None and len(text) > 0:
      ins = self.cursor if telem is None else telem
      l = ins.findall("./*")
      print ">>cursor>>", self.cursor
      print ">>findall>", l
      if len(l) == 0:
        ins.text = (ins.text if ins.text is not None else "") + text
      else:
        l[-1].tail = (l[-1].tail if l[-1].tail is not None else "") + text


  def show(self):

    from PyQt4 import QtGui, QtCore, QtWebKit

    app = QtGui.QApplication(sys.argv)
    d = QtGui.QDialog()
    l = QtGui.QVBoxLayout()
    w = QtWebKit.QWebView()
    w.setHtml(str(self))
    w.setZoomFactor(0.7) # TODO add control widget
    l.addWidget(w)
    w = QtGui.QPushButton("Close")
    w.clicked.connect(d.close)
    l.addWidget(w)
    d.setLayout(l)
    d.setModal(True)
    d.setWindowFlags(d.windowFlags() | QtCore.Qt.WindowMinMaxButtonsHint)
    d.show()
    app.exec_()


def main(argv):
  """Auto-test"""

  print "\n------------------- Document creation --------------"
  doc = RichHTMLDocument()

  print "\n------------------- add ------------------------"

  print "Cursor at", doc.getCursor()
  h = "First <em>heading</em> with formatting and id "
  t = "plus additional text with special characters & < >"
  print "Adding", h, "and", t
  doc.add(tag="h1", html=h, text=t, id="head1")

  h = "<p>first paragraph added as raw input with tag parameter</p>"
  print "Adding", h
  doc.add(html=h)

  h = "second paragraph added with tag and style"
  print "Adding", h
  doc.add(tag="p", html=h, style="font-weight:bold;")


  h =  "Text with formatting <em>emphasis</em> and <b>bold</b> and newline.<br/>"
  h += "Additonally <i>italic</i> end."
  t = " Text with special characters e.g. < or > or & or even <em> to be escaped."
  print "Adding without tag html =", h, "text =", t
  doc.add(html=h, text=t)

  doc.add(tag="p", html="""
  <svg height="150" width="500">
  <defs>
    <radialGradient id="grad1" cx="50%" cy="50%" r="50%" fx="50%" fy="50%">
      <stop offset="0%" style="stop-color:rgb(255,255,255);stop-opacity:0" />
      <stop offset="100%" style="stop-color:rgb(0,0,255);stop-opacity:1" />
    </radialGradient>
  </defs>
  <ellipse cx="200" cy="70" rx="85" ry="55" fill="url(#grad1)" />
  </svg>
  """)


  print "\n------------------- __str__ ----------------"
  print doc

  print "\n------------------- setCursor ----------------"
  doc.saveCursor()
  print "Cursor at", doc.setCursor('head1')
  doc.restoreCursor()


  print "\n------------------- write to test.html file ------------------"
  doc.write("test.html")

  print "\n------------------- show ----------------------------"
  doc.show()


# Real start of the script
if __name__ == "__main__":
  main(sys.argv[1:])
  sys.exit(0)


