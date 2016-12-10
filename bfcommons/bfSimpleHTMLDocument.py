#!/usr/bin/env python
# -*- coding: utf-8 -*-
#        1         2         3         4         5         6         7         8         9        9
# 3456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
"""
SimpleHTMLDocument: Text logger with HTML basic formatting such as tables and headers, standard
                     output and optionally storage of the HMTL content in a file.
Version VERSION - BF 2016
"""

__version__ = "0.1-draft2"

# Re-work docstring to insert version from single definition
__doc__ = __doc__.replace("VERSION", __version__)

# Revisions:
# 0.1        : First versions extracted from IMACS-Loads.py
# 0.1-draft2 : Added text formatting options (e.g. color)

# Imports
import string

class SimpleHTMLDocument():
  """Text document accepting formatting such as headers and tables, with  generated as HTML or text"""

  def __init__(self, verbosity, filename=None):
    """Inits an empty document. If verbosity >=1, HTML content is mirrored to standard output
       in ASCII-formatted form."""
    self.filename = filename
    self.text = ""                 # String holding the HTML content
    self.tableHeader = None        # List of strings for current table header
    self.subTableHeader = None     # List of strings for current nested table header
    self.verbosity = verbosity
    self.formatBeginTag = None          # Tag for formatting HTML text, if set

  def start(self):
    """Starts the HTML document, i.e. inserts header"""

    # Sets start values
    self.tableHeader = None
    self.formatBeginTag = None

    # Initializes the output text with HTML header
    self.text = """
    <html>
      <head>
        <style type='text/css'>
          table, td, th {border:1px solid black;border-collapse:collapse;padding:3px;margin:5px;}
          br {mso-data-placement:same-cell}
          th {background-color:lightgrey}
        </style>
      </head>
      <body style='font-family:arial;'>
    """

  def getHTMLText(self, s):
    """Transforms a raw text string into an HTML compliant one (special characters replaced)"""

    # Removes any "<" or ">" from the text, and replaces line ends with <br> tags
    if s is not None:
      res = str(s)
      res = string.replace(res, ">", "&gt;")
      res = string.replace(res, "<", "&lt;")
      res = string.replace(s, "\n", "<br style='mso-data-placement:same-cell;'/>")
    else:
      res = ""

    # Inserts formatting tag around text, if defined
    if self.formatBeginTag:
      res = self.formatBeginTag + res + self.formatEndTag

    return res

  def setHTMLFormat(self, tag):
    """When set, generates HTML tags around text provided in other functions"""

    self.formatBeginTag = tag.strip()
    name = tag.split("<")[1].strip().split(" ")[0]
    self.formatEndTag = "</" + name + ">"

  def resetHTMLFormat(self):
    self.formatBeginTag = None

  def addText(self, s):
    self.text += "<p>" + self.getHTMLText(s) + "</p>\n"
    if self.verbosity >= 1 :
      print s

  def addHeader(self, s):
    self.text += "<h1>" + self.getHTMLText(s) + "</h1>" + "\n"

    if self.verbosity >= 1 :
      print "\n", s, "\n", "-" * len(s), "\n"

  def addSubHeader(self, s):
    self.text += "<h2>" + self.getHTMLText(s) + "</h2>" + "\n"
    if self.verbosity >= 1 :
      print "\n", s, "\n"

  def startTable(self, headerList):
    """Starts a table, i.e. inserts a table header row according to the given list of string"""

    if not self.tableHeader:           # No table started
      self.text += "<table style='page-break-before: auto; page-break-inside: avoid; width:98%; margin:5px;'>\n"
      self.tableHeader = headerList
    elif not self.subTableHeader:      # Table started, no nested table started
      self.text += "<td><table>\n"     # nested table in a table cell
      self.subTableHeader = headerList
    else:                                  # Nested table started, unsupported
      assert False, "Only 2 levels of HTML tables supported"

    self.text += "<tr>"
    for s in headerList:
      self.text += "<th>" + self.getHTMLText(s) + "</th>"
    self.text += "</tr>\n"


  def addTableRow(self, t):
    """Adds a table row according to the given list of string"""

    # Exits if no table was started
    assert self.tableHeader, "No table was started"

    # Retrieves table headers list depending of nesting level
    if self.subTableHeader != None:
      headers = self.subTableHeader
      indent = "    "
    else:
      headers = self.tableHeader
      indent = ""

    # Adds the row in the resulting text
    self.text += "<tr>"
    for s in t:
      self.text += "<td>" + self.getHTMLText(s) + "</td>"
    self.text += "</tr>\n"

    # Prints text on standard output using the table headers
    if self.verbosity >= 1 :
      for i in range(len(t)):
        print indent, headers[i], " : ", t[i]
      print ""

  def startTableRow(self):
    """Starts a new row. No tracking of the position in the table. Deprecated"""
    self.text += "<tr>"

  def addTableCell(self, text):
    """Adds a table cell. No tracking of the position in the table"""
    self.text += "<td>" + self.getHTMLText(text) + "</td>"
    if self.verbosity >= 1 : print text


  def endTableRow(self):
    """Ends row. No tracking of the position in the table. Deprecated"""
    self.text += "</tr>"
    if self.verbosity >= 1 : print " "

  def endTable(self):

    # Exits if no table was started
    assert self.tableHeader, "No table was started"

    # Closes table HMTL tag
    self.text += "</table>"

    # Reset related table header list
    if self.subTableHeader != None:
      self.subTableHeader = None
      self.text += "</td>"            # Nested table in a cell
    else:
      self.tableHeader = None



  def finish(self):
    """Finishes the HTML document, i.e. inserts footer and write data to file, and returns
       the HTML content as a string (same as written to file if any)"""

    self.text += "</html>\n"

    if self.filename != None:
      with open(self.filename, "w") as f:
        f.write(self.text)

    return self.text
