#!/usr/bin/env python
# -*- coding: utf-8 -*-
#        1         2         3         4         5         6         7         8         9        9
# 3456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
"""
ScriptInterface: common user interface for scripts supporting command-line and GUI (PyQt4)
Version VERSION - BF 2016
"""

__version__ = "0.4.12"

# Re-work docstring to insert version from single definition
__doc__ = __doc__.replace("VERSION", __version__)

# Revisions:
# 0.1        : First usable version defined as separate file in bfcommons module and multi-threading
# 0.2-draft1 : De-activation of widgets when thread is started
# 0.2-draft2 : Addition of line wrap checkbox, and Reset button for MIP and MIF
# 0.2-draft3 : Addition of expand button, lbool not displayed if empty
# 0.2-draft4 : Add display HTML (displayResult)
# 0.2-draft5 : Implemented checkValueValidity and colorization of entry widgets
# 0.2        : Clean-up and small fixes for release
# 0.3-draft1 : Added values verification per command
# 0.3-draft2 : Fix drop down lists for verbosity order and font control in expanded mode
# 0.3        : Fix cursor location when user clicks in console
# 0.4-draft1 : Catch and display exception raised in thread, fixed cursor jump by manual edit
# 0.4-draft2 : Added MIDF support
# 0.4.3      : Added support for multiple selections of input files
# 0.4.4      : Added 'R' for regular expressions
# 0.4.5      : Added parameter "newline" to addOption to put several widgets on same line
# 0.4.6      : Replaced QtextEdit by QPlainTextEdit for console, removed common freeze issue
# 0.4.7      : Added 'T' for text, replaced QPushButton by QToolButton to save space on dialog
# 0.4.8      : Added search field, removed never-used font selection combo, added widget format
# 0.4.9      : Improved formatting of tooltips, correct display of "<", ">", "&" and newlines
# 0.4.10     : Deactivated kill button
# 0.4.11     : Re-implemented search buttons using QPlainTextEdit.find
# 0.4.12     : Improved scroll bar management with auto scroll if slider is at bottom


# TODO Display a count of matched searched items
# TODO Change multi-threading to multi-processing for support of "kill" button (now hanging)
# TODO Add grep mode
# TODO Set command buttons to disabled if inputs not valid
# TODO Add graphical element showing that thread is still alive
# TODO Improve performance, remove all HMI freeze issues if lots of data is passed to the console
# TODO Adds String check per regular expression
# TODO Ability to reset default value
# TODO Implement missing types
# TODO Differentiate enumerations as string or number

# Imports
import os, sys, getopt, time, traceback, re #, subprocess
from PyQt4 import QtGui, QtCore, QtWebKit


class ScriptInterface:
  """Common user interface for scripts supporting command-line (getopt) and GUI (PyQt4)"""

  ###### Inner base class of Option and Command ########

  class VisibleItem:
    """Base class of Option and Command. The format string is a semicolon-separated list of
        modifiers defined as following for a modification on left or top of widget:
        - S: stretched space
        - N: new line
        - L: separating line
        - G<name>: Group box started
        - E: End of group box
        - W<width>: minimum width of the editable part of the widget
        - H<height>: fixed height of the editable part of the widget
    """

    def __init__(self, name, format):
      self.name = name
      self.format = dict()
      for f in format.split(';'):
        if len(f)>0:
          self.format[f[0]] = f[1:]
          if f[0] in ['W', 'H']:
            self.format[f[0]] = int(self.format[f[0]])

    def getHTMLString(self, s):
      """Helper function to format description in tooltips"""

      res =   s.replace("&", "&amp;")
      res = res.replace("<", "&lt;")
      res = res.replace(">", "&gt;")
      res = res.replace("\n", "<br/>")

      return res


  ################## Inner class Option ############

  class Option(VisibleItem):
    """Inner class of ScriptInterface used to store options"""

    class PossibleValue:
      def __init__(self, value, name, description):
        self.value, self.name, self.description = value, name, description

    def __init__(self, name, description, type, shortid = None, longid = None, value = None,
                 format='N'):
      """Creates object with initial values for class members (same names for class members):
          - name: Human-readable name of the option, used for tooltips and usage text
          - description: Description of the purpose of the option
          - type: Type of the option resulting in differentiated checks and GUI elements:
            - B: Boolean displayed as a check box or a command-line option without argument
            - IF: Input file, OF: Output file, ID: Input dir, OD: Output dir
            - MID: Semicolon separated multiple input dirs, MIF: Multiple input files
            - E;id1:name1:descr1;id2:name2:descr2;etc: Enumeration
            - MIDF: Semicolon separated multiple input dirs and files
            - R: Regular expression, T: Multiline text, S: Generic string, DT: Date and time
            - I;min:max: Integer number (possibly negative), F;min;max: Floating point number
          - shortid: Single letter to identify the option on command line, e.g. "h" for "-h"
          - longid: String to identify the option on command-line, e.g. "infile" for "--infile="
          - value: Default value given to this option, keeping None if undefined except for
                    booleans always set to False if nothing is given
          - format: only for GUI, semicolon-separated list of format modifiers (see VisibleItem)
      """

      # Calls constructor of parent class
      ScriptInterface.VisibleItem.__init__(self, name, format)

      # Sets members
      self.description = description
      self.shortid = shortid
      self.longid = longid

      # Gets type (split for enumerations)
      typelist = type.split(";")
      self.type = typelist[0]

      # Enumeration
      if self.type is 'E':
        self.possibleValues = list()
        for e in typelist[1:]:
          el = e.split(":")
          self.possibleValues.append(self.PossibleValue(el[0], el[1], el[2]))

      # Sets default value, forcing boolean to false (otherwise not activable per command line)
      if self.type is 'B': self.setValue(False)
      else: self.setValue(value)


    def setValue(self, value):
      """Sets the value, depending on type (no verification at this stage)"""

      # Case of default value set to None (undefined or false for booleans)
      if value is None or value == "": self.value = None if self.type is not 'B' else False

      # Case of non-string types (value to be stored as is)
      elif self.type in ['B', 'I', 'F']:
        self.value = value

      # Converts to Python string in most cases (otherwise QString if taken from a widget)
      else:
        self.value = str(value)

    def checkValueValidity(self):
      """Verifies self.value according to type definition, returns a string explaining
         why value is invalid or None if value is valid"""

      # If not set
      if self.value is None:
        return self.name + ": value not set"

      # Enumeration
      if self.type is 'E':
        if self.value not in map(lambda a: a.value, self.possibleValues):
          res = self.name + ": \"" + self.value + "\" invalid, possible values: "
          for v in self.possibleValues:
            res += "\n" + v.value + " : " + v.name + " - " + v.description
          return res

      # Boolean
      if self.type is 'B':
        if type(self.value) is not bool:
          return self.name + ": boolean internal type not properly set"

      if self.type is 'R':
        try:
          re.compile(self.value)
        except Exception as e:
          return str(e)

      # Input file/directory, preparation for test with multiple input files/directories
      if self.type in ['IF', 'ID', 'OF', 'OD']: pathList = [self.value]
      elif self.type in ['MIF', 'MID', 'MIDF']: pathList = self.value.split(";")

      # Input/ouput file(s)/directory(ies)
      if self.type in ['IF', 'MIF', 'ID', 'MID', 'OF', 'OD', 'MIDF']:
        for path in pathList:
          if self.type in ['IF', 'MIF'] and not os.path.isfile(path):
            return self.name + ": given path is not an existing file \"" + path + "\""
          if self.type in ['ID', 'MID', 'OD'] and not os.path.isdir(path):
            return self.name + ": given path is not an existing directory \"" + path + "\""
          if self.type is 'MIDF' and not os.path.isfile(path) and not os.path.isdir(path):
            return self.name + ": given path is not an existing file or directory \"" + path + "\""
          if self.type in ['ID', 'MID', 'IF', 'MIF', 'MIDF'] and not os.access(path, os.R_OK):
            return self.name + ": given path is not readable \"" + path + "\""
          if self.type is 'MIDF' and not os.access(path, os.R_OK):
            return self.name + ": given path is not readable \"" + path + "\""
          dp = os.path.dirname(path)
          if self.type is 'OD' and not os.access(path, os.W_OK) or \
             self.type is 'OF' and not os.access(dp if len(dp) > 0 else '.', os.W_OK):
            return self.name + ": given path is not writable \"" + path + "\""

      # If self.value is OK
      return None

    def onEditButtonClick(self):
      """Called by the "Edit" button of a multiline Text widget, displays a simple text editor"""

      # Local function called when user clicks on close
      def onClose():
        v = str(editor.toPlainText())
        self.setValue(v if len(v)>0 else None)
        self.updateWidgetFromValue()
        d.close()

      # Creates a modal dialog with text editor
      d = QtGui.QDialog()
      l = QtGui.QVBoxLayout()
      editor = QtGui.QPlainTextEdit()
      editor.setPlainText(self.value if self.value else "")
      l.addWidget(editor)
      w = QtGui.QPushButton("Save and Close")
      w.clicked.connect(onClose)
      l.addWidget(w)
      d.setLayout(l)
      d.setModal(True)
      d.show()
      d.exec_()


    def onFileDialogButtonClick(self, fileMIDF=False):
      """Called upon click on a button displayed for this option (e.g. file dialog)"""

      # Calls a file dialog depending on type
      for t,f in [['ID',   QtGui.QFileDialog.getExistingDirectory],
                  ['IF',   QtGui.QFileDialog.getOpenFileName],
                  ['OD',   QtGui.QFileDialog.getExistingDirectory],
                  ['OF',   QtGui.QFileDialog.getSaveFileName],
                  ['MID',  QtGui.QFileDialog.getExistingDirectory],
                  ['MIF',  QtGui.QFileDialog.getOpenFileNames],
                  ['MIDF', QtGui.QFileDialog.getExistingDirectory]]:

        if self.type is t:

          # Case of MIDF called from file button (2 buttons for MIDF)
          if fileMIDF: f = QtGui.QFileDialog.getOpenFileNames

          # Prepares value, i.e. gets last path in case of multiple paths
          v = self.value
          if (self.type in ['MID', 'MIF', 'MIDF']) and v:
            t = v.split(";")
            v = t[len(t)-1]

          # Calls file dialog
          try:
            if self.value:
              v = f(directory=v)
            else:
              v = f()
          except Exception as err: print err

          # Splits values given from multiple selection
          if type(v) is QtCore.QStringList:
            res = ""
            for s in v:
              res += (";" if len(res)>0 else "") + str(s)
            v = res

          # Update value if something was selected
          if v:
            if (self.type in ['MID', 'MIF', 'MIDF']) and self.value:
              self.setValue(self.value + ";" + os.path.normpath(str(v)))
            else:
              self.setValue(os.path.normpath(str(v)))

      self.updateWidgetFromValue()


    def addGUI(self, layout):
      """Adds a set of widgets for this option to a given Qt layout using addWidget"""

      # Adds a checkbox for a boolean (typically put on one line)
      if self.type is 'B':
        self.widget = QtGui.QCheckBox(self.name)
        self.widget.stateChanged.connect(self.updateValueFromWidget)
        self.widget.setToolTip(self.getHTMLDescription())
        layout.addWidget(self.widget)

      # Adds combo box for an enumeration
      elif self.type is 'E':
        layout.addWidget(QtGui.QLabel(self.name))
        self.widget = QtGui.QComboBox()
        for v in self.possibleValues:
          self.widget.addItem(v.value + " - " + v.name)
        self.widget.currentIndexChanged.connect(self.updateValueFromWidget)
        self.widget.setToolTip(self.getHTMLDescription())
        self.widget.setEditable(False)
        self.widget.setFixedHeight(17)
        layout.addWidget(self.widget)

      # Adds a text field and a button for the other types
      else:
        w = QtGui.QLabel(self.name)
        w.setToolTip(self.getHTMLDescription())
        layout.addWidget(w)
        self.widget = QtGui.QLineEdit()
        if self.type is 'T':
          self.widget.setReadOnly(True)
          font = self.widget.font()
          font.setItalic(True)
          self.widget.setFont(font);
        self.widget.textChanged.connect(self.updateValueFromWidget)
        self.widget.setToolTip(self.getHTMLDescription())
        layout.addWidget(self.widget)
        # Adds a "Select" button for file/path-related options
        if self.type in ['IF', 'OF', 'ID', 'OD', 'MID', 'MIF', 'MIDF', 'T']:
          if   self.type is 'T': name = "Edit"
          elif self.type is 'IF': name = "Select input file"
          elif self.type is 'OF': name = "Select output file"
          elif self.type is 'ID': name = "Select input directory"
          elif self.type is 'OD': name = "Select output directory"
          elif self.type is 'MID': name = "Add input directory"
          elif self.type is 'MIF': name = "Add input file"
          elif self.type is 'MIDF':
            w = QtGui.QToolButton()
            w.setText("Add input file")
            w.clicked.connect(lambda: self.onFileDialogButtonClick(True))
            w.setToolTip(self.getHTMLDescription())
            layout.addWidget(w)
            name = "Add input directory"
          w = QtGui.QToolButton()
          w.setText(name)
          w.setMinimumWidth(0)
          w.clicked.connect(self.onEditButtonClick if self.type=='T' else self.onFileDialogButtonClick)
          w.setToolTip(self.getHTMLDescription())
          layout.addWidget(w)
          if self.type in ['MID', 'MIF', 'MIDF', 'T']:
            w = QtGui.QToolButton()
            w.setText("Reset")
            w.clicked.connect(lambda: self.widget.setText(""))
            w.setToolTip("Remove content of this field")
            layout.addWidget(w)

      # Sets width and height
      if 'W' in self.format and self.type is not 'B':
        self.widget.setMaximumWidth(self.format['W'])
      if 'H' in self.format and self.type is not 'B':
        self.widget.setMaximumHeight(self.format['H'])

      # General settings
      self.updateWidgetFromValue()


    def updateValueFromWidget(self):
      """Called when a widget was changed manually (not via a file dialog)"""

      # Boolean
      if self.type is 'B':
        self.setValue(bool(self.widget.checkState()))

      # Enumeration from drop down box
      elif self.type is 'E':
        self.setValue(self.possibleValues[self.widget.currentIndex()].value)

      # Strings
      else:
        s = self.widget.text()
        self.setValue(None if s is None or len(s) == 0 else s)

      # Updates widget in case value is not valid
      self.updateWidgetFromValue(colorizeOnly=True)

    def updateWidgetFromValue(self, colorizeOnly = False):

      val = self.checkValueValidity()

      # Colorizes the widget if the value is not valid
      if not hasattr(self, 'defaultPalette'):   # Creates a copy of original palette
        self.defaultPalette = QtGui.QPalette(self.widget.palette())
      pal = QtGui.QPalette(self.defaultPalette)
      self.widget.setAutoFillBackground(True)
      if self.value is None:    # Lightgray if value is not set
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor(250, 250, 250))
        self.widget.setToolTip(self.getHTMLDescription())
      elif val is not None:     # Lightred if value is invalid
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor(255, 220, 220))
        self.widget.setToolTip(val)
      else:
        self.widget.setToolTip(self.getHTMLDescription())
      self.widget.setPalette(pal)

      # Sets value in widget from self.value if wished
      if not colorizeOnly:

        # Updates widget value - Boolean
        if self.type is 'B':
          self.widget.setChecked(self.value if self.value is not None else False)

        # Enumeration
        elif self.type is 'E':
          if self.value is None:
            self.widget.setCurrentIndex(-1)
          else:
            found = False
            for i in range(len(self.possibleValues)):
              if self.possibleValues[i].value == self.value:
                self.widget.setCurrentIndex(i)
                found = True
            if not found: raise ValueError("Attempt to set enumeration with invalid value")

        # String-like
        else:
          self.widget.setText(self.value if self.value is not None else "")


    def getHTMLDescription(self):
      """Returns a description usable for the tooltip"""

      # Name of the option
      res = "<strong>" + self.name + "</strong><br/>"

      # Short ID if defined
      if self.shortid:
        res += "<em>-" + self.shortid
        if self.type is not 'B': res += " val"
        res += "</em>"

      # Long ID if defined
      if self.shortid and self.longid: res += " / "
      if self.longid:
        res += "<em>--" + self.longid
        if self.type is not 'B': res += "=val"
        res += "</em>"

      # Adds provided description
      res += "<br/>" + self.getHTMLString(self.description)

      # Adds description of possible values for an enumeration
      if self.type is 'E':
        for v in self.possibleValues:
          res += "<br/>" + v.value + ": " + v.name + " - " + v.description

      return res


  ################## Inner class Command ############

  class Command(VisibleItem):
    """Inner class of ScriptInterface used to store commands"""

    def __init__(self, name, description, id, callback, moptions, foptions, format = ''):
      """Creates object with initial values for class members (same names for class members):
          - name: Human-readable name of the command, used for tooltips and usage text
          - description: Description of the purpose of the command
          - id: ID of the command for usage on command line, e.g. "store"
          - callback: function to be called back when this command is selected
          - moptions: list of option objects necessary for running the command
          - foptions: list of option objects that can be used for this command, checked if set
          - format: only for GUI, semicolon-separated list of format modifiers (see VisibleItem)
      """

      # Calls constructor of parent class
      ScriptInterface.VisibleItem.__init__(self, name, format)

      # Sets members
      self.description = description
      self.id = id
      self.callback = callback
      self.gcallback = None
      self.moptions = moptions
      self.foptions = foptions

    def setGUICallback(self, callback):
      """Sets an alternative callback to be called in GUI mode"""
      self.gcallback = callback


    def addGUI(self, layout):
      """Adds a push button for execution of this command to the provided layout. Another
         callback function can be provided to replace the original one."""

      self.widget = QtGui.QPushButton(self.name)
      self.widget.setToolTip(self.getHTMLDescription())
      self.widget.clicked.connect(self.gcallback if self.gcallback else self.callback)

      # Sets width and height
      if 'W' in self.format and self.type is not 'B':
        self.widget.setMaximumWidth(self.format['W'])
      if 'H' in self.format and self.type is not 'B':
        self.widget.setMaximumHeight(self.format['H'])

      layout.addWidget(self.widget)


    def getHTMLDescription(self):
      """Returns a description usable for the tooltip"""

      # Name of the option
      res = "<strong>" + self.name + "</strong><br/>"
      res += "<em>" + self.id + "</em><br/>"
      res += self.getHTMLString(self.description)

      return res

  ######### Inner class ScriptThread and ConsoleStream ##################

  class ScriptThread(QtCore.QThread):
    """Helper object to start a QThread and catch stdout, run() executes the provided callback"""

    class ConsoleStream(QtCore.QObject):
      """Stream to redirect stdout to QTextEdit console on main window (and log file TODO)"""

      output = QtCore.pyqtSignal(str)

      def __init__(self, console):
        QtCore.QObject.__init__(self)
        self.output.connect(self.processText)
        self.console = console
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

      def write(self, text):
        self.output.emit(text)

      def processText(self, str):

        # Improves processing for large amounts of text
        self.console.setUpdatesEnabled(False)

        # Gets scroll bar value
        scrollbar = self.console.verticalScrollBar()
        curval = scrollbar.value()
        tracking = (curval == scrollbar.maximum())

        # Prints text
        self.console.moveCursor(QtGui.QTextCursor.End)
        self.console.insertPlainText(str)

        # Adapts slider if tracking is wished
        if tracking:
          self.console.ensureCursorVisible()
        else:
          scrollbar.setValue(curval)

        # Re-activation of updates
        self.console.setUpdatesEnabled(True)


    def __init__(self, callback, console):
      QtCore.QThread.__init__(self)
      self.callback = callback
      self.constream = self.ConsoleStream(console)
      self.bstdout = None

    def run(self):
      self.bstdout = sys.stdout
      sys.stdout = self.constream
      try:
        self.callback()
      except Exception:
        print "\n\n************************* EXCEPTION IN THREAD *************************"
        print traceback.format_exc()
        print     "***********************************************************************\n\n"

      if self.bstdout: sys.stdout = self.bstdout

    def terminate(self):
      QtCore.QThread.terminate(self)
      self.wrapup()

    def wrapup(self):
      if self.bstdout: sys.stdout = self.bstdout
      self.bstdout = None


  ##################################################


  def __init__(self, title, description, version, file):

    # List of options and commands
    self.options = list()
    self.commands = list()
    self.items = list()

    # Holds names of common options
    self.commonOptions = None

    # Stores parameters for GUI creation
    self.title = title
    self.description = description
    self.version = version
    self.file = os.path.basename(file)
    self.command = None
    self.console = None
    self.verbosity = 1              # Default verbosity level, changed internally if common options
    self.thread = None
    self.result = None              # Result HTML content
    self.mainWidget = None          # To track if a main window is created


  def addOption(self, name, description, type, shortid = None, longid = None, value = None,
                format="N"):
    """Adds an option (i.e. extra setting for a command), refer to the __init__ method of
           ScriptInterface.Option:
        - name: Human-readable name of the option, used for tooltips and usage text
        - description: Description used in tooltips and usages text
        - type: Type of the option resulting in differentiated checks and GUI elements. Refer to
                  the addOption method of ScriptInterface.Option
        - shortid: Single letter to identify the option on command line, e.g. "h" for "-h"
        - longid: String to identify the option on command-line, e.g. "infile" for "--infile="
        - value: Default value given to this option, keeping None if undefined except for
                  booleans always set to False if nothing is given (may raise ValueError)
        - format: For HMI, defines how the widget will be placed
    """

    o = self.Option(name, description, type, shortid, longid, value, format)
    self.options.append(o)
    self.items.append(o)

  def addCommonOptions(self):
    """Adds a couple of options that are necessary most of the time"""
    self.addCommand("Help", "Returns help on this script", "help",
                    lambda: self.println(self.usage()))
    self.addCommand("Version", "Returns the software version", "version",
                    lambda: self.println(self.version))
    type = "E;0:Quiet:Minimal output;1:Normal:Informational output;2:Debug:Debug-level output"
    self.addOption("Verbosity", "Verbosity level", type, "v", "verbosity", "1", format='')

    self.commonOptions = ["Help", "Version", "Verbosity"]


  def addCommand(self, name, description, id, callback, mandatoryOptions=[], facultativeOptions=[],
       format=''):
    """Adds a command, with:
        - name: Human-readable name of the command used for tooltips and usage text
        - description: Description of command used for tooltips and usage text
        - id: ID of the command for usage on command line, e.g. "store"
        - callback: function to be called back when this command is selected
        - mandatoryOptions: List of options (referenced by name, long ID or short ID) that are
                             necessary to be set before running the command
        - facultativeOptions: List of options that can be set. If set (i.e. not None), then
                             value is checked.
        - format: For HMI, defines how the widget will be placed
    """

    # Searches all options and finds corresponding option object
    moptions = list()
    foptions = list()
    for l,opts in [[moptions, mandatoryOptions], [foptions, facultativeOptions]]:
      for n in opts:
        found = False
        for o in self.options:
          if o.name is n or o.longid is n or o.shortid is n:
            l.append(o)
            found = True
        if not found:
          raise ValueError("Unknown option " + n)

    # Inits and stores command object
    c = self.Command(name, description, id, callback, moptions, foptions, format)
    self.commands.append(c)
    self.items.append(c)


  def parseCommandLine(self):
    """Parses the command line, using the defined options and commands. Returns the recognized
       command (or None if nothing given). A ValueError exception may be raised if input
       arguments are invalid.
    """

    # Prepares data structures for getopt
    short = ""
    long = []
    for o in self.options:
      if o.shortid:
        short += o.shortid
        if o.type is not 'B':
          short += ":"
      if o.longid:
        l = o.longid
        if o.type is not 'B':
          l += "="
        long.append(l)

    # Parses command line arguments, propagates exception in case of invalid syntax
    try:
      opts, args = getopt.getopt(sys.argv[1:], short, long)
    except getopt.GetoptError as err:
      raise ValueError(err)

    # Analyses input options and retrieve values if found
    for opt, arg in opts:
      for o in self.options:
        if opt == ("-" + o.shortid) or opt == ("--" + o.longid):
          if o.type is 'B': o.setValue(True)
          else: o.setValue(arg)

    # Retrieves given command
    if len(args) == 0:
      return None
    if len(args) > 1:
      raise ValueError("Only one command can be executed")
    cmd = args[0]

    # Checks if command is known, raise exception if not
    for c in self.commands:
      if cmd == c.id:
        self.command = cmd
        return self.command
    raise ValueError("Command " + cmd + " not recognized")


  def getValue(self, name):
    for o in self.options:
      if o.name is name or o.longid is name or o.shortid is name:
        if o.type is 'B' or o.value is None:
          return o.value
        else:
          return str(o.value)

    raise ValueError("Unknown option " + name)


  def getValues(self):
    """Returns a dict with name/value pairs, where name is the option name and ids"""
    res = dict()
    for o in self.options:
      v = self.getValue(o.name)
      res[o.name] = v
      if o.longid: res[o.longid] = v
      if o.shortid: res[o.shortid] = v

    return res

  def checkOptionValuesValidity(self, command = None):
    """Checks validity of options of given command, returns None if all mandatory options and
       all set facultative options are valid, otherwise reason as string. If no command
       is given, check all set options"""

    if command:
      # Check mandatory options (value must be set)
      for o in command.moptions:
        val = o.checkValueValidity()
        if val is not None:
          return val

      # Check facultative options (value verified only if set)
      for o in command.foptions:
        if o.value is not None:
          val = o.checkValueValidity()
          if val is not None:
            return val

    else:
      # Check all options (value verified only if set)
      for o in self.options:
        if o.value is not None:
          val = o.checkValueValidity()
          if val is not None:
            return val

    return None

  # TODO : add possible values for enumerations
  # TODO : improve formatting
  def usage(self):
    """Returns a string containing the script description and the possible options and commands"""

    # Standard text at the beginning, use data given with common options if available
    res = "\n" + self.description + "\n"
    res += "Version: " + self.version + "\n"
    res += "\nUsage: " + self.file + " <options> command\n"

    # Evaluates the maximum string length of options and commands (for aligned text output)
    maxLenOptions = 0
    for o in self.options:
      if len(o.longid) > maxLenOptions:
        maxLenOptions = len(o.longid)
    maxLenCommands = 0
    for c in self.commands:
      if len(c.id) > maxLenCommands:
        maxLenCommands = len(c.id)

    # Display options
    res += "\nOptions:\n"
    for o in self.options:
      if o.shortid: res += " -" + o.shortid
      else: res += "  "
      if o.longid: res += " --" + o.longid
      res += " : " + o.name + " - " + o.description + "\n"

    # Display commands
    res += "\nCommands:\n"
    for c in self.commands:
      res += " " + c.id + " : " + c.name + " - " + c.description + "\n"

    return res + "\n"

################################# GUI part ######################################


  def println(self, text):
    """Prints some text on standard output or console if present (should not be called
       from thread)"""

    if self.console and not self.thread:
      self.console.insertPlainText(text)
      self.console.moveCursor(QtGui.QTextCursor.End)
      self.console.ensureCursorVisible()
    else:
      print text


  def startCallback(self, callback, command):
    """Starts the given callback in a separated thread in GUI, for given command object"""

    # Stores command for later use
    self.command = command

    # Check options validity
    val = self.checkOptionValuesValidity(self.command)
    if val:
      self.println("\nERROR: " + val + "\n")
      return

#    def quote(s):
#      if " " not in s: return s
#      res = re.sub(r'\\"', r'\\"', s)       # Replaces \" by \\" to escape \
#      res = re.sub(r'[^\\]"', r'\\"', res)  # Replaces remaining " by \" to escape "
#      return '"' + res + '"'
#
#    # Creates list of arguments for subprocess call
#    args = [sys.executable or 'python', sys.argv[0]]
#    for o in self.options:
#      v = self.getValue(o.name)
#      if v:
#        if o.type is 'B':
#          args.append("--" + o.longid if o.longid else o.shortid)
#        elif o.longid:
#          args.append(quote("--" + o.longid + "=" + str(v)))
#        else:
#          args.append("-" + o.shortid)
#          args.append(quote(str(v)))
#    args.append(command.id)
#
#    if self.commonOptions and int(self.getValue("Verbosity")) >= 2:
#      self.println("\nStarting script in different process with the following arguments:\n")
#      self.println(str(args) + "\n")
#
#    p = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
#
#    (stdo, stde) = p.communicate()
#    self.println(stdo)


    # Displays option values in debug mode
    if self.commonOptions and int(self.getValue("Verbosity")) >= 2:
      text = "\nStarting script with following options: "
      for o in self.options:
        text += o.name + " = \"" + str(self.getValue(o.name)) + "\"   "
      self.println(text + "\n\n")

    # No HTML result by default
    self.result = None

    # Prepares thread and catches stdout
    self.thread = self.ScriptThread(callback, self.console)





    # Prepares HMI for execution, i.e. disable all widgets except the ones needed during run
    if self.mainWidget:
      self.changeWindow(isEnabled = False)
      self.killButton.clicked.connect(self.thread.terminate)
      # TODO: re-activate the button when multi-processing is implemented
      self.killButton.setEnabled(False)
    self.thread.finished.connect(self.stopCallback)

    # Starts
    self.thread.start()


  def stopCallback(self):

    self.thread.wrapup()
    self.thread = None

    self.showResult()

    # Re-enable HMI
    if self.mainWidget:
      self.changeWindow(isEnabled = True)
      self.killButton.clicked.disconnect()
      self.killButton.setEnabled(False)

  def setResult(self, content):
    """Sets optional HTML content (given as a string) to be displayed after command execution"""

    self.result = content


  def showResult(self):
    """IF result was provided, displays a dialog showing it after command execution"""

    # Display results if some content was provided
    if self.result:
      if not self.mainWidget:       # Execution in command line, not GUI
        app = QtGui.QApplication(sys.argv)
      d = QtGui.QDialog()
      l = QtGui.QVBoxLayout()
      w = QtWebKit.QWebView()
      w.setHtml(self.result)
      w.setZoomFactor(0.7) # TODO add control widget
      l.addWidget(w)
      w = QtGui.QPushButton("Close")
      w.clicked.connect(d.close)
      l.addWidget(w)
      d.setLayout(l)
      d.setModal(True)
      d.setWindowFlags(d.windowFlags() | QtCore.Qt.WindowMinMaxButtonsHint)
      d.show()
      if not self.mainWidget:       # Execution in command line, not GUI
        app.exec_()
      else:
        d.exec_()


  def changeWindow(self, isVisible = None, isEnabled = None):
    """Change the visual properties of the non-runnable widgets of the main window"""
    if self.mainWidget:

      # Re-build list of run widgets and their children, as new children appear after clicks
      runWidgets = list(self.runWidgets)
      for w in self.runWidgets:
        runWidgets.extend(w.findChildren(QtCore.QObject))

      # Search for widget objects in main window
      for w in self.mainWidget.findChildren(QtGui.QWidget):
        if w not in runWidgets:
          if isVisible is not None and hasattr(w, "setVisible"): # and type(w) is not QtGui.QFrame:
            w.setVisible(isVisible)
          if isEnabled is not None and hasattr(w, "setEnabled"):
            w.setEnabled(isEnabled)

      # Search for spacers in main window
      #for s in self.mainWidget.findChildren(QtCore.QObject):
      #  print ">spacer>", type(s)


  def displayWindow(self):

    # Prints hint when HMI is started (normally because no option is given)
    print "\nTry \"" + self.file + " help\" for script usage on the command line\n"

    # Initializes Qt and setup window
    app = QtGui.QApplication(sys.argv)
    self.mainWidget = QtGui.QWidget()
    ml = QtGui.QVBoxLayout()
    ml.setSpacing(2)
    self.mainWidget.setLayout(ml)
    self.mainWidget.setWindowTitle(self.title)
    self.runWidgets = list()   # Widgets to be kept enabled

    # Displays title and description
    title = "<center><font size=+2><strong>"+self.title+"</strong></font>"
    title += "<br/>Version "+self.version+"</center>"
    w = QtGui.QLabel(title)
    w.setToolTip(self.description)
    ml.addWidget(w, alignment = QtCore.Qt.AlignCenter)

    # Adds widgets for the options and prepares boolean/drop-down options and commands
    ml.addSpacing(3)
    lcom = QtGui.QHBoxLayout()      # All common options on one line
    lcom.setMargin(0)
    lcur = None                     # Used for several widgets on one line

    # Set an alternative callback to be called from pushbutton
    for c in self.commands:
      func = (lambda param, cmd: lambda: self.startCallback(param, cmd))(c.callback, c)
      c.setGUICallback(func)

    # Adds the different options
    containerstack = list()   # Stack of main containerstacks including group boxes
    for item in self.items:

      # N: new line before widget, S: stretched space right of widget, L: line on top of widget
      # G<name>: Group box started before widget
      # E: End of group box after widget

      # Creates new line of widgets if necessary ('N' or first line)
      if 'N' in item.format or 'L' in item.format or 'G' in item.format or 'E' in item.format or \
           lcur is None:
        if lcur is not None: ml.addLayout(lcur)
        lcur = QtGui.QHBoxLayout()
        lcur.setMargin(0)
        lcur.setSpacing(2)

      # Adds horizontal line if necessary
      if 'L' in item.format:
        w = QtGui.QFrame()
        w.setFrameShape(QtGui.QFrame.HLine)
        w.setFrameShadow(QtGui.QFrame.Sunken)
        w.setFixedHeight(3)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.gray)
        w.setPalette(palette)
        ml.addWidget(w)

      # Ends groupbox
      if 'E' in item.format and len(containerstack) > 0:
        ml = containerstack.pop()

      # Starts Group Box
      if 'G' in item.format:
        w = QtGui.QGroupBox(item.format['G'])
        newlayout = QtGui.QVBoxLayout()
        newlayout.setSpacing(2)
        newlayout.setMargin(4)
        w.setLayout(newlayout)
        ml.addWidget(w)
        containerstack.append(ml)
        ml = newlayout


      # Adds GUI item to currenty layout line
      destlayout = lcom if item.name in self.commonOptions else lcur
      if len(destlayout) > 0 and item.name not in self.commonOptions:
        destlayout.addSpacing(3)
      if 'S' in item.format:
        destlayout.addStretch()
      item.addGUI(destlayout)


    # Adds last defined list of widgets (otherwise only added with newline)
    if lcur is not None: ml.addLayout(lcur)

    # Pops remaining group boxes if any
    while len(containerstack) != 0:
      ml = containerstack.pop()

    # Adds line of additional controls after common options if any
    ml.addSpacing(3)
    lcom.addSpacing(20)
    lcom.addStretch()
    self.expand = QtGui.QCheckBox("Expand")
    lcom.addWidget(self.expand)
    self.runWidgets.append(self.expand)
    self.lineWrap = QtGui.QCheckBox("Wrap")
    lcom.addWidget(self.lineWrap)
    self.runWidgets.append(self.lineWrap)
    self.fontSizeCombo = QtGui.QComboBox()
    self.fontSizeCombo.setFixedHeight(17)
    lcom.addWidget(self.fontSizeCombo)

    self.clearButton = QtGui.QToolButton()
    self.clearButton.setText("Clear")
    lcom.addWidget(self.clearButton)
    self.runWidgets.append(self.clearButton)

    self.searchText = QtGui.QLineEdit()
    self.searchText.setFixedWidth(150)
    lcom.addWidget(self.searchText)
    self.runWidgets.append(self.searchText)

    self.searchBackwardButton = QtGui.QToolButton()
    self.searchBackwardButton.setText("<")
    lcom.addWidget(self.searchBackwardButton)
    self.runWidgets.append(self.searchBackwardButton)

    self.searchForwardButton = QtGui.QToolButton()
    self.searchForwardButton.setText(">")
    lcom.addWidget(self.searchForwardButton)
    self.runWidgets.append(self.searchForwardButton)

    self.killButton = QtGui.QPushButton("Kill")
    lcom.addWidget(self.killButton)
    self.runWidgets.append(self.killButton)
    self.killButton.setEnabled(False)    # Kill button disabled at the beginning
    ml.addLayout(lcom)

    # Create console i.e. large text edit area for script output
    ml.addSpacing(3)
    css = """QPlainTextEdit{font-family: monospace, "Courier", "System"; color:white;
          background-color: black; selection-color: black; selection-background-color:#437DCD;}"""
    self.console = QtGui.QPlainTextEdit()
    self.console.setStyleSheet(css)
    self.console.setReadOnly(True)
    self.console.setWordWrapMode(QtGui.QTextOption.WrapAnywhere)
    self.console.setLineWrapMode(QtGui.QPlainTextEdit.NoWrap)

    ml.addWidget(self.console)
    self.runWidgets.append(self.console)

    # Local function to set the font
    def updateFont():
      f = self.console.document().defaultFont()
      f.setPointSize(int(self.fontSizeCombo.currentText()))
      self.console.setFont(f)

    # Local function to search for text, and wrap around if not found
    def search(forward=True):
      text = self.searchText.text()
      options = QtGui.QTextDocument.FindFlag(0) if forward else QtGui.QTextDocument.FindBackward
      if not self.console.find(QtCore.QString(text), options):
        prevcursor = self.console.textCursor()
        prevscroll = self.console.verticalScrollBar().value()
        cursor = prevcursor
        cursor.movePosition(QtGui.QTextCursor.Start if forward else QtGui.QTextCursor.End)
        self.console.setTextCursor(cursor)
        if not self.console.find(QtCore.QString(text), options):
          self.console.setTextCursor(prevcursor)
          self.console.verticalScrollBar().setValue(prevscroll)

    # Connects console controls
    self.expand.stateChanged.connect(lambda: self.changeWindow(isVisible=not self.expand.isChecked()))
    self.lineWrap.stateChanged.connect(lambda: self.console.setLineWrapMode(
       QtGui.QPlainTextEdit.WidgetWidth if self.lineWrap.isChecked() else QtGui.QPlainTextEdit.NoWrap))
    self.lineWrap.setCheckState(False)

    self.fontSizeCombo.addItems(["6", "8", "9", "10", "11", "12", "14", "16", "18"])
    self.fontSizeCombo.setCurrentIndex(1)
    self.runWidgets.append(self.fontSizeCombo)
    self.fontSizeCombo.currentIndexChanged.connect(updateFont)
    updateFont()
    self.clearButton.clicked.connect(lambda: self.console.clear())
    self.searchForwardButton.clicked.connect(lambda: search(True))
    self.searchBackwardButton.clicked.connect(lambda: search(False))
    self.searchText.returnPressed.connect(lambda: search(True))
    self.mainWidget.show()
    sys.exit(app.exec_())


  def run(self):
    """Parses the command-line, calls the command callback if a command was provided,
    otherwise displays the GUI. This function does not return.
    """

    # Parses command line
    try:
      cmd = self.parseCommandLine()
    except ValueError as err:
      print err
      print self.usage()
      sys.exit(1)

    # Find command in list
    command = None
    if cmd:
      for c in self.commands:
        if c.id == cmd:
          command = c

    # Check validity of options entered on command line, exits if errors
    val = self.checkOptionValuesValidity(command)
    if val:
      print "ERROR:", val
      print self.usage()
      sys.exit(1)

    # Runs command if provided
    if command:
      command.callback()
      self.showResult()
      sys.exit(0)

    # Starts GUI if no command was given on command line
    self.displayWindow()


def periodicPrint():


  while True:

    print "This command prints a string to stdout every second, use kill button to stop"
    time.sleep(1)


def scanDisk(path="/"):

  if path == "/": print "START SCANNING"
  for (dirpath, dirnames, filenames) in os.walk(path):
    print dirpath, filenames
    for dir in dirnames:
      scanDisk(dir)
  if path == "/": print "STOP SCANNING"


def displayResultExample(si):

  print "Now started in thread, creating HTML"

  # Creates HTML table
  res = """<html><head><style type='text/css'>
             table, td, th {border:1px solid black;border-collapse:collapse;padding:3px;margin:5px;}
           </style></head><body>"""
  res += "<h1>Example HTML result</h1><p><table>"
  for i in range(10):
    res += "<tr>"
    for j in range(10):
      res += "<td>" + str((i+1)*(j+1)) + "</td>"
    res += "</tr>"
  res += "</table></p></body></html>"

  si.setResult(res)

  time.sleep(1)


if __name__ == '__main__':

  print "Arguments", sys.argv

  # Auto test of module
  des =  "Auto-test of ScriptInterface: " + ScriptInterface.__doc__
  si = ScriptInterface("Auto-test ScriptInterface", des, __version__, sys.argv[0])
  si.addCommonOptions()

  si.addOption("String", "Input string", 'S', "s", "string", "bla")
  si.addOption("String2", "Input string", 'S', "2", "string2", "bli", format='W100')
  val = 'Line 1\nLine 2\nprint "BLA"\nprint "\\"bla\\""'
  si.addOption("Text", "Input text", 'T', "T", "text", val, format='')
  si.addOption("Opt", "Description of opt", 'E;first:bla:bla;second:bla2:bla2',
               "Y", "optionY", "second", format='W80')
  si.addOption("Regexp", "Regular expression", 'R', "R", "regexp", "(bla|bli)", format='')

  si.addOption("Input dir", "Input path to look for files", 'ID', "i", "inputdir", ".", format='GInput/Output')
  si.addOption("Output dir", "Output path to store files", 'OD', "o", "outputdir", ".", format='')
  si.addOption("Input file", "Input file description", 'IF', "f", "inputfile")
  si.addOption("Output file", "Output file description", 'OF', "g", "outputfile")
  si.addOption("Multiple input dir", "Multiple input dir description", 'MID', "m", "multindir")
  si.addOption("Multiple input file", "Multiple input file description", 'MIF', "n", "multinfile")
  si.addOption("Multiple input file and dirs", "MIDF description", 'MIDF', "z", "multinfiledir")
  si.addOption("Dummy option A", "Description of option A", 'B', "a", "optiona", format = "E")
  si.addOption("Dummy option B", "Description of option B", 'B', "b", "optionb", format='')
  si.addOption("Dummy option C", "Description of option C", 'E;first:bla:bla;second:bla2:bla2',
               "c", "optionc", "first", format='W80')

  si.addCommand("Print values", "Prints parameter values from dict", "print-values",
                lambda: si.println(str(si.getValues())), ["inputdir"], format='S')
  si.addCommand("HTML", "Show an example of displayResult in HTML", "show-html",
                lambda: displayResultExample(si), ["inputfile"], format='L')
  si.addCommand("Periodic print", "Prints a string periodically, no return, use kill to stop",
                "periodic-print", periodicPrint, ["inputdir", "optiona"])
  si.addCommand("Scan disk", "List all files srting at top directory, i.e. must be stoppable",
                "scan-disk", scanDisk, ["inputdir", "optiona"])

  si.run()
