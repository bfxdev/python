#!/usr/bin/env python
# -*- coding: utf-8 -*-
#        1         2         3         4         5         6         7         8         9        9
# 3456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789
"""
ReguLog - Unpacks and analyzes log archives with regular expressions

ReguLog can be used via a GUI (start script with no argument) or on the command line to:

 - Search for log files according to regexp patterns into directories and archive files. The zip,
    tar and gzipped-tar archive formats are supported. Data is searched recursively into directories
    and archive files down to the deepest level. At the end of the scan process, an overview of the
    identified log files is shown with their earliest and latest modification times.

 - Extract the identified log files into a destination directory, and apply several schemes for
    file concatenation (log4j style) and directory re-ordering.

 - Search for regexp patterns in log files, in archive or directories, and extract fields (using the
    Python syntax e.g. to extract a 2-digit day field "(?P<day>[0-3][0-9])"). The found occurrences
    can be displayed on match or on change, and may include references to fields (e.g. "{day}").
    Additional pre-defined fields are available such as the timestamp, extracted with a regexp too.
    Python code can as well be entered and executed on search start, event match and search end.

 - Export the data of the found events in XML/CSV files for post-processing.

 - Store a working pattern into a new or existing patterns XML file, then re-use patterns for
    other searches.

Known issues:
 - A tar file packed in a zip file cannot be read ("seek" error)
 - QT: during search, too many displayed events can lead to HMI freeze or crash. As a
   workaround set the verbosity to "Quiet" or run the tool in command-line mode.
 - QT/bfScriptInterface: "Kill" button does not work
 - QT/bfScriptInterface: console view is scrolled to bottom when new text is generated, so
   it is not possible to keep the view during command execution
 - QT: it is not possible to select multiple directories
"""

#Revisions:
# 0.1     : First version with tar file support
# 0.2     : Use of ScriptInterface for GUI
# 0.3-d1  : Changed name to regulog
# 0.3-d2  : Associated options to commands
# 0.3-d3  : Implement unpack, make dist with new ScriptInterface
# 0.3-d4  : Added support for MIDF for input files and dirs, renaming of options and commands
# 0.3-d5  : Re-factored patterns, add support for input XML file with log event definition
# 0.3-d6  : Re-factored log archive opening
# 0.3-d7  : Added LogSource class, implemented simple version of unpack
# 0.3-d8  : Consolidated unpack for all kinds of sources and HMI re-ordering
# 0.3-d9  : Renamed "unpack" to "extract", completed "keep source dirs", changed default values
# 0.3-d10 : Update with new bfScriptInterface supporting multiple files/dirs selection
# 0.3-d11 : Re-factored extract procedure to support file re-ordering and concatenation
# 0.3-d12 : Completed extract procedure with options - Issue PR1: very long extraction time
# 0.3-d13 : Split extract procedure, rewrote procedures to process files in archive order
# 0.3     : Removed default test values for release, added list of known issues
# 0.4.1   : Set last modification time to value found on original file
# 0.4.2   : Corrected hanging with reducedirs if all files in source have different names
# 0.4.3   : Some re-factoring for pathfilter, change path regex to filename regex in event
# 0.4.4   : Fixed today's timestamp on joined files
# 0.5.1   : First version of log analysis with patterns
# 0.5.2   : Implementation of event save, display on match, display on change, timestamp
# 0.5.3   : Consolidation of ElementTree patch, fix of CDATA removal while saving, re-factoring
# 0.5.4   : Re-factoring of many elements, chronological order, newline in HMI
# 0.5.5   : Support of multiline patterns, improvement of timestamp pattern and logic
# 0.5.6   : Case sensitive option, hide timestamp option
# 0.5.7   : Fixed timestamp in ipsec.log, implemented global source
# 0.5.8   : Lookup functions, re-factoring search function, change of syntax to {field}-style
# 0.5.9   : XML/CSV export
# 0.6.0   : Python execution
# 0.6.1   : HMI changes following new ScriptInterface, widgets location, re-wording
# 0.6.2   : Python execution consolidation, displayIfChanged introduced
# 0.6.3   : Introduced checkPathFilter, named groups in path filter now create dirs
# 0.6.4   : Reducedir separately in each output dir, avoid duplicate files in tar
# 0.6.5   : Moved code to new EventSet class with lookup, corrections in scanPath
# 0.6.6   : Added Python functions, fully pseudo-path in _source_path, fixed multiline issue
# 0.6.7   : Further Python functions (e.g. get_fields), __str__ for Event, _user_fields
# 0.6.8   : Kill button grayed, user fields from timestamp rex, _core, _flat_core, fixed Event str
# 0.6.9   : Changed finalization sequence (all Python, then display strings), added Event.execute()


__version__ = "0.6.9"

# TODO add compilation of Pytho code at event type read time (to verify syntax)
# TODO check name of fields given in python in set_field and add_field
# TODO support cascaded event types (Parent, ParentFile), with includes of patterns in other files
# TODO prevent changing XML structure and comments when saving event type
# TODO improve events search performance
# TODO add option remove duplicated events
# TODO add new virtual fields (_reduced_raw, _reduced_flat) to hide timestamp rex span
# TODO continue re-implementation of replaceFields with get_event like functions
# TODO make _flat fully virtual given by get_field
# TODO improve error message after execution error (now execution stack displayed)
# TODO fix kill button
# TODO multithreaded search
# TODO Re-edit event type parameters
# TODO improve globalsource management for extract (single dest dir), LOG dirs reduction
# TODO Improve global source, i.e. each found archive in dir treated as soon as found
# TODO Display previous lines when an event is displayed
# TODO Add option ignore errors
# TODO join syslog-style log rotation

# Imports
import os, sys, traceback, tarfile, zipfile, re, datetime, time, shutil, collections, types, psutil
import bfcommons
import xml.etree.ElementTree as ET
#from types import MethodType


# ------------------------- CDATA support adapted from gist.github.com/zlalanne/5711847
# Defines new function to be added as method, appending a new Element to the current one
def appendCDATA(self, text):
  """Appends a CDATA object containing the given text, returns CDATA Element"""

  # Adds new Element with tag "![CDATA["
  element = ET.SubElement(self, '![CDATA[')
  element.text = text
  return element

# Adds method as "unbound method" to Element
ET.Element.appendCDATA = types.MethodType(appendCDATA, None, ET.Element)

# Saves original serialize method
ET._original_serialize_xml = ET._serialize_xml

# Defines new function to replace standard serialize function
def _serialize_xml(write, elem, encoding, qnames, namespaces):
  if elem.tag == '![CDATA[':
    write("<%s%s]]>%s" % (elem.tag, elem.text, elem.tail if elem.tail else ""))
    return
  return ET._original_serialize_xml(write, elem, encoding, qnames, namespaces)

# Replace global function in ElementTree module
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

ET.Element.indent = types.MethodType(indent, None, ET.Element)

#-------------------------------------------------------------------------

class Event():
  """Data of found occurrences in logs. To be completely defined, the object methods need to be
     called in the following order:
       - __init__ to initialize standard fields
       - setRaw, setLinenum to set the internal fields once consolidated
       - parseText to extract fields from the text match
       - parseTimestamp to extract time/date fields from text (calls setTimestamp)
       - execute to run execOnMatch code
       - parseDisplay to generate the display_on_match field as defined in event type"""

  def __init__(self, eventType, path):
    """Initializes an event with the standard fields"""

    self.eventType = eventType

    # Defines user and system fields dictionaries
    self.sfields = dict()
    self.ufields = dict()

    # Stores standard values (check as well replaceFields below for additional items)
    self.sfields['_name'] = eventType.name
    self.sfields['_description'] = eventType.description if eventType.description else ""
    self.sfields['_source_path'] = path
    self.sfields['_source_filename'] = os.path.basename(path)

    # Default values if left undefined or failure
    self.sfields['_display_on_match'] = None
    self.ufields['_changed_fields'] = None
    self.setSeqnum(-1)
    self.setTimestamp()
    self.timestampSpan = (0,0)     # Default text span if no timestamp has been found


  def __str__(self):
    return "Event: ts:" + str(self.timestamp) + " seqnum:" + str(self.seqnum) +\
           " ufields:" + str(self.ufields) + " sfields:" + str(self.sfields)


  # Function advertised for Python code
  def set_field(self, name, value):
    if name in self.sfields:
      raise RuntimeError("Overwriting " + name + " system field not allowed")
    else:
      self.ufields[name] = value

  # Function advertised for Python code
  def set_fields(self, dictionary):
    for (name, value) in dictionary.items():
      try:
        self.set_field(name, value)
      except:
        pass

  # Function advertised for Python code
  def add_field(self, name, value):
    if name in self.sfields or name in self.ufields:
      raise RuntimeError("Field " + name + " already exists")
    else:
      self.ufields[name] = value

  # Function advertised for Python code
  def add_fields(self, dictionary):
    for (name, value) in dictionary.items():
      try:
        self.add_field(name, value)
      except:
        pass


  # Function advertised for Python code
  def has_field(self, name):
    """Returns true if the given field name or virtual field name is part of the event"""
    if name in ['_user_fields', '_system_fields', '_flat', '_core', '_flat_core']:
      return True
    return (name in self.ufields) or (name in self.sfields)

  # Function advertised for Python code
  def get_field(self, name):
    if name in self.ufields: return self.ufields[name]
    elif name in self.sfields: return self.sfields[name]
    elif name == "_user_fields": return str(self.ufields)
    elif name == "_system_fields": return str(self.sfields)
    elif name == "_flat":
      return self.sfields['_raw'].replace('\n', '')
    elif name == "_core":
      raw = self.sfields['_raw']
      return raw[0:self.timestampSpan[0]] + raw[self.timestampSpan[1]:]
    elif name == "_flat_core":
      raw = self.sfields['_raw']
      core = raw[0:self.timestampSpan[0]] + raw[self.timestampSpan[1]:]
      return core.replace('\n', '')

    raise RuntimeError("Field " + name + " not found")


  # Function advertised for Python code
  def get_user_fields(self):
    return self.ufields

  # Function advertised for Python code
  def get_system_fields(self):
    return self.sfields



  def setRaw(self, raw):
    self.sfields['_raw'] = raw
    self.sfields['_flat'] = raw.replace("\n", " ")

  def setLinenum(self, linenum):
    self.sfields['_line_number'] = str(linenum)

  def setSeqnum(self, num):
    self.seqnum = num
    self.sfields['_sequence_number'] = str(num)

  def setTimestamp(self, timestamp=None):
    """Sets the timesamp of this event and related fields, minimum time if timestamp not given"""
    self.timestamp = timestamp if timestamp is not None else datetime.datetime.min
    self.sfields['_timestamp'] = self.timestamp.isoformat()
    self.sfields['_date'] = str(self.timestamp.date())
    self.sfields['_time'] = str(self.timestamp.time())


  def replaceFields(self, text, events=None):
    """Replaces fields given as "{field_name}" in a string by their values
       from the object user and system dictionaries"""

    # Replaces special chars
    res = text.replace(r"\t", "\t")
    res = res.replace(r"\n", "\n")

    # Special functions:
    # {fieldname} : field value of current event
    # {rfieldname@evname:} : last field value of other event
    # {rfieldname@evname:rcfieldname=fieldname} : lookup of value of rfield in other event
    parts = re.split("({[^{}]+})", res)
    res = parts[0]
    fields = dict(self.sfields.items() + self.ufields.items())
    for i in range(1, len(parts), 2):
      trans = "N/A"                                # default value if transformation not successful

      # Extracts text between curly brackets
      src = parts[i][1:-1].strip()

      # Case of simple ref to local field (no "@")
      (fieldname, sep, src) = src.partition("@")
      if len(sep) == 0:
        if self.has_field(fieldname):
          trans = self.get_field(fieldname)
        else:
          trans = "FIELD '" + fieldname + "' NOT FOUND"

      # Case of ref to another event type ("@" present), checks event type name
      else:
        (evname, sep, src) = src.partition(":")
        if evname not in events:
          trans = "EVENT '" + evname + "' NOT FOUND"
        elif len(events[evname]) == 0:
          trans = "EMPTY"
        else:
          evlist = events[evname]
          ev = None

          # Latest value of this event (no ":")
          if len(sep) == 0:

            # Determines nearest event in the past
            t = self.timestamp
            for sev in reversed(evlist):
              # If another event with same timestamp is found, prefer event from same source
              if (ev is None and sev.timestamp <= t) or (ev is not None and sev.timestamp == t and\
                         self.sfields["_source_path"] == sev.sfields["_source_path"]):
                ev = sev
                t = ev.timestamp
              elif sev.timestamp < t:
                break
            else:
              trans = "NO MATCHING EVENT"

          # Lookup (":" present), need to extract fields around "="
          else:
            (rfieldname, sep, cfieldname) = src.partition("=")
            if len(sep) == 0:
              trans = "LOOKUP CONDITION '" + src + "' NOT VALID"
            elif cfieldname not in fields:
              trans = "COMPARISON FIELD '" + fieldname + "' NOT FOUND"
            else:
              for sev in evlist:
                if rfieldname in sev.sfields and sev.sfields[rfieldname] == fields[cfieldname] or \
                   rfieldname in sev.ufields and sev.ufields[rfieldname] == fields[cfieldname]:
                  ev = sev
                  break
              else:
                trans = "NO MATCHING EVENT"

          # Extraction of field value from found ev
          if ev:
            if fieldname in ev.sfields:
              trans = ev.sfields[fieldname]
            elif fieldname in ev.ufields:
              trans = ev.ufields[fieldname]
            else:
              trans = "FIELD '" + fieldname + "' NOT IN FOUND EVENT"
          else:
            trans = "EVENT NOT FOUND"

      # Concatenates result with rest of string
      if trans is None: trans = "N/A"
      res += trans + parts[i+1]

    return res

  def parseText(self, textRexResult=None):

    # Parses text if not already provided
    if textRexResult is None:
      textRexResult = self.eventType.searchText(self.sfields['_raw'])

    # At this point, it must be assumed that string matched
    assert textRexResult is not None

    # Adds detected fields to user fields
    self.ufields = textRexResult.groupdict()


  def parseTimestamp(self, alternativeText=None, sourceTime=None):
    """Matches compiled regexp, if yes updates system fields, may raise exceptions. Searches in
       alternativeText if given, otherwise in current _raw system field"""

    ts = self.eventType.searchTimestamp(alternativeText if alternativeText else self.sfields['_raw'])
    assert ts is not None, "Timestamp regex does not match in" + str(self.sfields['_raw'])

    # Gets named groups
    tsfields = ts.groupdict()

    # Searches for keys in tsfields with names compatible with timestamp fields
    names = dict()
    for k in tsfields.keys():
      # Select a field name if name syntax is as _<letter><empty_or_digit>
      if tsfields[k] is not None and len(tsfields[k])>0 and k[0] == '_' and len(k) in [2,3] and \
         k[1] in ['Y', 'M', 'D', 'h', 'm', 's'] and \
         (len(k) == 2 or (len(k)==3 and k[2] >= "0" and k[2] <= "9")):
          names[k[1]] = k
    assert len(names) >= 4, "Not enough timestamp fields"

    # Year field may not be present in timestamp fields
    if 'Y' in names:
      year = int(tsfields[names['Y']])
      if year < 100: year += 2000           # If the year is acquired as 2-digits (e.g. "31/12/16")
    else:
      year = sourceTime.year if sourceTime is not None else datetime.datetime.now().year

    # Month field may be given as text
    m = tsfields[names['M']]
    if len(m) <= 2:
      month = int(m)
    else:
      m = m[0:3].upper()
      months = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
                "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
      month = int(months[m])

    # Second field may not be present
    if 's' in names:
      second = int(tsfields[names['s']])
    else:
      second = 0

    # Convert common time values
    day = int(tsfields[names['D']])
    hour = int(tsfields[names['h']])
    minute = int(tsfields[names['m']])

    # Sets the timestamp fields and retrieves additional fields if everything went well
    self.setTimestamp(datetime.datetime(year, month, day, hour, minute, second))
    self.timestampSpan = ts.span()
    for k in tsfields.keys():
      if tsfields[k] is not None and k[0] != "_":
        self.add_field(k, tsfields[k])


  def parseDisplay(self, previousEvent=None, events=None):
    """Generates _changed_fields and _display_on_match according to EventType"""

    # Determines changed fields
    res = ''
    if previousEvent is not None:
      for k in self.ufields:
        if k not in previousEvent.ufields or previousEvent.ufields[k] != self.ufields[k]:
          res += (',' if len(res) > 0 else '') + k
    self.sfields['_changed_fields'] = res if len(res) > 0 else None

    # Computes display string on match
    if self.eventType.displayOnMatch:
      self.sfields['_display_on_match'] = self.replaceFields(self.eventType.displayOnMatch, events)


  def display(self, hideTimestamp):
    """Prints the event as string if display on match is defined otherwise nothing displayed"""

    if self.sfields['_display_on_match']:
      if (self.eventType.displayIfChanged and self.sfields['_changed_fields'] is not None) or \
      (not self.eventType.displayIfChanged):
        t = self.sfields['_timestamp'] if not hideTimestamp else ""
        print t + " " + self.sfields['_display_on_match']


  def toXML(self, full=True):
    """Returns an XML element, all elements as CDATA if full, otherwise a meaningful subset"""

    # Creates basic element object
    template = "<Event></Event>"
    elem = ET.fromstring(template)

    # Selection of fields if not full
    sel1 = ["_timestamp"]
    sel2 = ["_line_number", "_source_path", "_flat"]

    # Export system fields in alphabetical order or first set of selected fields
    for k in sorted(self.sfields) if full else sel1:
      e = ET.Element(k)
      if full:
        e.appendCDATA(self.sfields[k])
      else:
        e.text = self.sfields[k] if self.sfields[k] is not None else ""
      elem.append(e)

    # Export user fields in alphabetical order
    for k in sorted(self.ufields):
      e = ET.Element(k)
      if full:
        e.appendCDATA(self.ufields[k])
      else:
        e.text = self.ufields[k] if self.ufields[k] is not None else ""
      elem.append(e)

    # Export second set of selected fields
    if not full:
      for k in sel2:
        e = ET.Element(k)
        e.text = self.sfields[k] if self.sfields[k] is not None else ""
        elem.append(e)

    return elem

  def execute(self, executionContext):
    """Executes the python code on match"""

    if self.eventType.execOnMatch:
      executionContext.execute(self.eventType.execOnMatch, self.eventType.name, self)

  def __cmp__(self, other):
    if self.timestamp != other.timestamp:
      return -1 if self.timestamp < other.timestamp else 1
    elif self.seqnum != other.seqnum:
      return -1 if self.seqnum < other.seqnum else 1


class ExecutionContext:
  """Special object encapsulating the execution of Python code"""

  def __init__(self, events, chronological, outputdir):
    self.events = events
    self.output_directory = outputdir
    self.chronological = chronological

  def execute(self, code, name, event=None):
    """Executes the given code"""

    exec code in locals()


class EventSet(dict):
  """"Structure holding events found during search. Events are arranged in lists per eventType,
      where each list is referenced by the related event type name in a dictionary."""

  def __init__(self, eventTypes):
    """Inits the object using the list of event types, i.e. creates empty lists in dict"""

    # Sequence of all events used for event searches
    self.sequence = list()

    # Main structure holding events
    for k in eventTypes.keys():
      self[k] = list()


  def addEvent(self, event):
    """Adds event after setting the sequence number in event"""

    event.setSeqnum(len(self.sequence))
    self[event.eventType.name].append(event)
    self.sequence.append(event)


  def get_events(self, name=None, fields=None, before=None, limit=1):
    """Returns an iterator on the latest events in multi-criterion search. The
       function may raise exceptions if the parameters are invalid, or may return None if no
       event was found. Events are searched in the full list (self.sequence) starting from the end.
       Parameters:
       - name: name of the event, or search all events if no name given
       - before: given as a timestamp or event
       - fields: dictionary of field names/values, all need to match
       - limit: max number of events to return (default 1)"""

    # Validates inputs
    if name is not None:
      assert name in self, "Given event name " + str(name) + " is not known in event set"

    # Main loop into full list of events, or dedicated list if name is given
    num = 0
    for ev in reversed(self.sequence if name is None else self[name]):
      isMatching = True

      # Checks name
      if name is not None and ev.eventType.name != name: isMatching = False

      # Checks fields
      if isMatching and fields is not None:
        for kf in fields.keys():
          if (kf not in ev.sfields and kf not in ev.ufields) or \
             (kf in ev.ufields and ev.ufields[kf] != fields[kf]) or \
             (kf in ev.sfields and ev.sfields[kf] != fields[kf]):
            isMatching = False

      # Checks before
      if isMatching and before is not None:
        if (hasattr(before, "timestamp") and before.timestamp < ev.timestamp) or \
           (hasattr(before, "seqnum") and before.seqnum <= ev.seqnum) or \
           (hasattr(before, "utcfromtimestamp") and before < ev.timestamp):
         isMatching = False

      # Final test
      if isMatching:
        yield ev
        num += 1
        if num == limit: break


  def get_event(self, name=None, fields=None, before=None):
    """Returns a single event or None, same search criteria as get_events, except limit parameter"""
    for e in self.get_events(name, fields, before, limit=1):
      return e

    return None


  def sortEvents(self):
    """Sorts all events according to their timestamps and sequence number, then sets sequence
       numbers according to new ordering"""

    # Reset list for all events
    self.sequence = list()

    # Sorts each list of stored events, and adds it to the main list
    for l in self.values():
      l.sort()
      self.sequence.extend(l)

    # Finally sorts all events in main list
    self.sequence.sort()

    # Re-compute sequence numbers
    for i in range(len(self.sequence)):
      self.sequence[i].setSeqnum(i)

    return self.sequence


  def finalizeEvents(self, executionContext):
    """Deferred execution of Python code and parsing of display strings for chronological search"""

    # Executes the python code of all the events in the sequence
    for e in self.sequence:
      e.execute(executionContext)

    # Calls the finalization methods of each event in each list
    for l in self.values():
      prev = None
      for ev in l:
        ev.parseDisplay(prev, self)
        prev = ev


  def save(self, outputdir):
    """Saves the content of the events into XML/CSV files in outputdir"""

    # Creates 1 CSV and 2 XML files per event name, one simplified and one full
    for k in self.keys():
      if len(self[k]) > 0:
        for ext in [".xml", ".full.xml", ".csv"]:

          # Creates XML file (own file creation to avoid keeping whole file in memory)
          filename = os.path.join(outputdir, k + ext)
          with open(filename, "w") as f:

            #if self.verbosity >= 2:
            #  print "--", len(self[k]), "events in", f.name

            # CSV export
            if ext is ".csv":
              sfsel = ["_timestamp", "_name", "_display_on_match", "_changed_fields", "_flat"]
              ufsel = sorted(self[k][0].ufields.keys())

              # CSV Header
              for s in sfsel + ufsel: f.write(s + ";")
              f.write("\n")

              # Export events
              def trans(s): return "" if s is None else s.replace("\n", " ").replace(";", " ")
              for ev in self[k]:
                for kf in sfsel: f.write(trans(ev.sfields[kf] if kf in ev.sfields else None) + ";")
                for kf in ufsel: f.write(trans(ev.ufields[kf] if kf in ev.ufields else None) + ";")
                f.write("\n")

            # XML export
            else:
              # XML Header
              f.write("<?xml version='1.0' encoding='utf-8'?>\n<RegulogEvents>\n")

              # Adds events to XML data
              for ev in self[k]:
                xev = ev.toXML("full" in ext)
                f.write("  " + ET.tostring(xev) + "\n")

              # XML End of file
              f.write("</RegulogEvents>\n")


class EventSearchContext(dict):

  def __init__(self, verbosity, eventTypes, chronological, outputdir):

    # Internal variables
    self.verbosity = verbosity
    self.eventTypes = eventTypes
    self.chronological = chronological

    # Used to display advancement
    self.numProcessedLines = 0
    self.numFoundEvents = 0
    self.lastPrintedAdvancement = datetime.datetime.now()
    self.lastNumProcessedLines = 0

    # Creates main structure holding events, i.e. dict of lists of events, key is event name
    self.events = EventSet(self.eventTypes)

    # Creates execution context
    self.executionContext = ExecutionContext(self.events, chronological, outputdir)

    # Execute start Python code of events
    for evt in self.eventTypes.values():
      if evt.execOnInit:
        self.executionContext.execute(evt.execOnInit, evt.name)


  def printAdvancement(self, currentLogPath):
    """Prints statistics information every 30 seconds"""

    # Checks only every 10000 lines
    if self.numProcessedLines % 10000 == 0:

      # Prints if the time delta exceeds 30 seconds
      dt = (datetime.datetime.now() - self.lastPrintedAdvancement).seconds
      if dt > 30 :
        self.lastPrintedAdvancement = datetime.datetime.now()
        dl = self.numProcessedLines - self.lastNumProcessedLines
        self.lastNumProcessedLines = self.numProcessedLines
        mem = psutil.Process(os.getpid()).get_memory_info()[0]
        print "\n", self.numProcessedLines, "lines -", int(dl/dt), "lines/sec -", \
            self.numFoundEvents, "events -", int(mem / (1024*1024)), "MBytes -", \
            "Now at", currentLogPath

  def checkSource(self, filePath, fileTime):
    """Checks if file path is matching at least one event, then prepares internal structures.
       Timestamp on file is given in order to get Year value if missing in the timestamp
       definition."""

    self.searchFilePath = filePath
    self.searchFileTime = fileTime

    # Gets events matching filename into new list
    self.searchEventTypes = list()
    for evt in self.eventTypes.values():
      if evt.searchFilename(filePath):
        self.searchEventTypes.append(evt)

    # Prepares structures and returns true if at least one event matched
    if len(self.searchEventTypes) > 0:

      # Prepares buffer of log text strings for multiline log entries support
      self.lines = collections.deque(maxlen=100) # Previous lines to scan for timestamp
      self.unfinishedEvents = dict()             # Events while looking for following timestamp
      self.linenum = 0                           # Current line number in source file

      return True

    return False


  def getMultiline(self, num):
    """Returns a string built of the most recent num lines starting backwards"""
    # Packs all lines from event into one
    res = ''
    for i in range(min(num, len(self.lines))):
      res = self.lines[i] + ('\n' if i > 0 else '') + res

    return res


  def storeNewEvent(self, ev, eventLinesCount):
    """Completes event definition if not chronological and stores it into list of event"""

    # Packs all lines related to this event into one (at this stage the current line is not
    #  in the previous lines, eventLinesCount was updated previously).
    # Then updates event content, no new parseText as the user fields were already extracted.
    ev.setRaw(self.getMultiline(eventLinesCount))

    # Updates linenum using the event lines count, taking num of lines into account
    ev.setLinenum(self.linenum - (eventLinesCount+1))

    # Adds created event to current lists
    self.events.addEvent(ev)
    self.numFoundEvents += 1

    # Exec Python and creates display strings immediately using previous event if not chronological
    if not self.chronological:
      ev.execute(self.executionContext)
      pev = self.events[ev.eventType.name][-2] if len(self.events[ev.eventType.name]) > 1 else None
      ev.parseDisplay(pev, self.events)




  def checkLine(self, line, finishEvents=True):
    """Detects and stores events found in the given line of text (without CR). Function must be
       called with 'line' set to None to finish current multiline treatment. If finishEvents is
       false, then acquires events without waiting for next line with timestamp."""

    # Handles unfinished events that were created during previous calls, i.e. check if the
    #   current line contains a timestamp applicable for this event type found in previous lines
    if len(self.unfinishedEvents) > 0:
      #print ">>>>>>>>", len(self.unfinishedEvents), self.unfinishedEvents
      for ev in self.unfinishedEvents.values():

        # Checks if the current line contains a timestamp or it is the last line (line=None),
        #  i.e. completes the fields and stores the event
        if line is None or ev.eventType.searchTimestamp(line):

          # Completes fields and stores new event
          self.storeNewEvent(ev, self.eventLinesCount)

          # Removes this event from the list and returns it
          del self.unfinishedEvents[ev.eventType.name]
          yield ev

      # In any case increases the number of lines belonging to these events, created before
      self.eventLinesCount += 1


    # Handles new events starting at the current line
    if line is not None:

      # Stores line in multiline buffer
      self.lines.appendleft(line)

      # Updates current line number in source (pre-incrementation)
      self.linenum += 1

      # Search for known event types in given line, only if there is no unfinished event on-going
      for evt in self.searchEventTypes:
        if evt.name not in self.unfinishedEvents:

          # Creates string with the current and previous lines for multiline patterns
          multiline = line if evt.multilineCount == 1 else self.getMultiline(evt.multilineCount)

          # Checks if text on current multiline matches the text pattern
          rexResult = evt.searchText(multiline)

          # If one event type matched, and match is on the last line of the multiline string
          if rexResult and (len(multiline)-rexResult.span()[1]) < len(line):

            if self.verbosity >= 2: print "---", multiline.replace("\n", " ")

            # Creates Event object
            ev = Event(evt, self.searchFilePath)
            ev.parseText(rexResult)

            # Looks in the current and previous lines to find a matching timestamp, and sets the
            #  eventLinesCount accordingly (reset to 1 if not found)
            timestampFound = False
            self.eventLinesCount = 1
            for l in self.lines:
              try:
                ev.parseTimestamp(l, sourceTime=self.searchFileTime)
                timestampFound = True
                break
              except:
                self.eventLinesCount += 1
            else:
              self.eventLinesCount = 1


            # If no timestamp could be found, at least prints a detailed description of the issue
            #   during the timestamp parsing process
            if not timestampFound and self.verbosity >= 2:
              print "WARNING: no timestamp found for this event\n" + multiline
              try:
                ev.parseTimestamp(multiline, sourceTime=self.searchFileTime)
              except Exception as e:
                print e
                stack = traceback.format_exc().splitlines()
                print stack[-3] + "\n" + stack[-2] + "\n" + stack[-1]

            # Force output of new unfinished event if set, or no timestamp was found (little
            #  chance that a timestamp will be found in the next lines if no one was found in the
            #  previous lines)
            if not finishEvents or not timestampFound:
              self.storeNewEvent(ev, self.eventLinesCount)
              yield ev

            # Inserts event into list of unfinished events for later processing
            else:
              self.unfinishedEvents[evt.name] = ev
              #print "\n\nAdding event", evt.name
              #print multiline, "\n"

      # Increments counter for statistics
      self.numProcessedLines += 1


  def wrapup(self, outputdir):
    """Sorts the events to display in chronological order, and save events in files if
       the given outputdir is not None. Returns the full list of events if chronological
       otherwise an empty list."""

    sl = list()

    # Sorts and finalizes events if necessary
    if self.chronological:
      sl = self.events.sortEvents()
      self.events.finalizeEvents(self.executionContext)

    # Executes wrapup Python code of event types
    for evt in self.eventTypes.values():
      if evt.execOnWrapup:
        self.executionContext.execute(evt.execOnWrapup, evt.name)

    # Export sorted events
    if outputdir:
      print "\nSaving events as XML/CSV"
      self.events.save(outputdir)

    return sl


class EventType:
  """Data to search text in logs for a particular set of files"""

  def __init__(self):
    """Pre-initialization with given mandatory values set to None"""
    self.name = None

  def init(self, rexFilename, rexText, rexTimestamp, multilineCount=1, caseSensitive=False,
           name=None, description=None, displayOnMatch=None, displayIfChanged=False,
           execOnInit=None, execOnMatch=None, execOnWrapup=None):
    """Initializes fully an event definition from the given parameters"""
    self.rexFilename = rexFilename
    self.compiledRexFilename = re.compile(self.rexFilename)
    self.multilineCount = int(multilineCount)
    self.caseSensitive = caseSensitive
    self.rexText = rexText
    rexTextFlags = re.MULTILINE | re.DOTALL | (re.IGNORECASE if not self.caseSensitive else 0)
    self.compiledRexText = re.compile(self.rexText, rexTextFlags)
    self.rexTimestamp = rexTimestamp
    self.compiledRexTimestamp = re.compile(self.rexTimestamp)
    self.name = name if name else "DEFAULT_EVENT_TYPE"
    self.description = description if description else "N/A"
    self.displayOnMatch = displayOnMatch
    self.displayIfChanged = displayIfChanged
    self.execOnInit = execOnInit
    self.execOnMatch = execOnMatch
    self.execOnWrapup = execOnWrapup

  def __str__(self):
    res =  "EventType '" + str(self.name) + "'\n"
    for s,v in [["Description", self.description], ["Filename regexp", self.rexFilename],
                ["Text regexp", self.rexText], ["Timestamp regexp", self.rexTimestamp],
                ["Multiline pattern count", self.multilineCount],
                ["Case sensitive pattern search", self.caseSensitive],
                ["Displayed on match", self.displayOnMatch],
                ["Display if changed", self.displayIfChanged],
                ["Python code on init", "\n" + str(self.execOnInit)],
                ["Python code on match", "\n" + str(self.execOnMatch)],
                ["Python code on wrap-up", "\n" + str(self.execOnWrapup)]]:
      res += "  " + s + ": " + str(v) + "\n"

    return res


  def searchFilename(self, path):
    """Returns result of regexp search on filename"""
    return self.compiledRexFilename.search(os.path.basename(path))


  def searchText(self, text):
    """Returns result of regexp search on text"""
    return self.compiledRexText.search(text)


  def searchTimestamp(self, text):
    """Returns result of regexp search on timestamp"""
    return self.compiledRexTimestamp.search(text)


  def initXML(self, xev):
    """Initializes event definition from an XML element, see regulog.xsd"""

    # Mandatory fields for an event (exception if not found in XML file)
    assert xev.tag == "EventType", "Attempt to parse tag " + xev.tag + " as log event definition"
    name = xev.find("Name").text
    rexFilename = xev.find("RexFilename").text
    rexText = xev.find("RexText").text
    rexTimestamp = xev.find("RexTimestamp").text

    # Optional fields, set to None if not found or empty
    e = xev.find("Description")
    description = None if e is None else None if len(e.text) == 0 else e.text
    e = xev.find("DisplayOnMatch")
    displayOnMatch = None if e is None else None if len(e.text) == 0 else e.text
    e = xev.find("DisplayIfChanged")
    displayIfChanged = e is not None and e.text == "true"
    e = xev.find("ExecOnInit")
    execOnInit = None if e is None else None if len(e.text) == 0 else e.text
    e = xev.find("ExecOnMatch")
    execOnMatch = None if e is None else None if len(e.text) == 0 else e.text
    e = xev.find("ExecOnWrapup")
    execOnWrapup = None if e is None else None if len(e.text) == 0 else e.text
    e = xev.find("MultilineCount")
    multilineCount = 1 if e is None else int(e.text)
    e = xev.find("CaseSensitive")
    caseSensitive = e is not None and e.text == "true"

    self.init(rexFilename, rexText, rexTimestamp, multilineCount, caseSensitive, name, description,
           displayOnMatch, displayIfChanged, execOnInit, execOnMatch, execOnWrapup)

  def toXML(self):
    """Returns an XML element"""

    # Creates basic element object
    template = "<EventType><Name/><Description/><RexFilename/>" + \
               "<RexText/><MultilineCount/><CaseSensitive/><RexTimestamp/></EventType>"
    elem = ET.fromstring(template)
    elem.find('Name').text = self.name
    elem.find('Description').text = self.description
    elem.find('RexFilename').appendCDATA(self.rexFilename)
    elem.find('RexText').appendCDATA(self.rexText)
    elem.find('MultilineCount').text = str(self.multilineCount)
    elem.find('CaseSensitive').text = "true" if self.caseSensitive else "false"
    elem.find('RexTimestamp').appendCDATA(self.rexTimestamp)

    if self.displayOnMatch:
      e = ET.Element('DisplayOnMatch')
      e.appendCDATA(self.displayOnMatch)
      elem.append(e)
      e = ET.Element('DisplayIfChanged')
      e.text = "true" if self.displayIfChanged else "false"
      elem.append(e)

    if self.execOnInit:
      e = ET.Element('ExecOnInit')
      e.appendCDATA(self.execOnInit)
      elem.append(e)
    if self.execOnMatch:
      e = ET.Element('ExecOnMatch')
      e.appendCDATA(self.execOnMatch)
      elem.append(e)
    if self.execOnWrapup:
      e = ET.Element('ExecOnWrapup')
      e.appendCDATA(self.execOnWrapup)
      elem.append(e)

    return elem


class EventTypeList(dict):
  """List of Event Types with import/export XML file"""

  def __init__(self, verbosity):
    self.verbosity = verbosity

  def addEventType(self, eventType):
    self[eventType.name] = eventType

  def readEventTypes(self, filename):
    """Reads event types file"""

    xml = ET.parse(filename)

    for xev in xml.findall("EventType"):
      le = EventType()
      le.initXML(xev)
      self.addEventType(le)

  def writeEventTypes(self, filename):
    """Write event types to file, overwrites file if existing"""

    # Creates XML structure
    template = """<Regulog xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'
                      xsi:noNamespaceSchemaLocation='regulog.xsd'></Regulog>"""
    elem = ET.fromstring(template)

    # Adds events to XML data
    for ev in self.values():
      xev = ev.toXML()
      elem.append(xev)

    # Pretty print result
    elem.indent()

    # Prints results
    if self.verbosity >= 2:
      print ET.tostring(elem)

    # Writes results
    ET.ElementTree(elem).write(filename, 'utf-8', True)


  def printEventTypes(self):

    for el in self.values():
      print str(el)


class LogSource:
  """Source of log files from a directory (DIR), a tar archive (TAR), as zip archive (ZIP) or
     files directly given (LOG). An open tarfile/zipfile object is kept for archives."""

  class LogSourceFile:
    """Helper class to store variables of source log file"""

    def __init__(self, path, pseudoPath, time, size, info=None, fields=dict()):
      """Constructor with path (absolute path for LOG, relative for DIR/ZIP/TAR), time (timestamp
         of last modification), info (info object for ZIP/TAR), groupdict fields"""
      self.path = path                       # full or relative path
      self.pseudoPath = pseudoPath           # Full path normalized, including archive names
      self.time = time
      self.size = size
      self.info = info
      self.fields = fields
      self.offset = 0                        # Modified during file re-ordering (log4j)
      self.destinationBasePath = None        # Used for path reduction (non-modifiable part)
      self.destinationRelativePath = None    # Used for path reduction (modifiable part)


  def __init__(self, verbosity, type, path=None, archive=None):
    """Inits the internal variables with the type of the source (DIR/TAR/ZIP/LOG), the base path
       equal to the archive file path (TAR/ZIP) or the directory of log files searched
       by directory (DIR). A TarFile/ZipFile object must be provided for archives (TAR/ZIP)."""

    self.verbosity = verbosity
    self.type = type                         # 'DIR', 'TAR"', 'ZIP', 'LOG'
    self.path = path                         # Pseudo path of archive/dir (empty for LOG)
    self.archive = archive                   # Archive object TarFile/ZipFile
    self.logs = list()                       # List of LogSourceFile objects, in original order
    self.earliest = datetime.datetime.max
    self.latest   = datetime.datetime.min

  def getPseudoPath(self, logpath):
    """Returns the pseudo-path of the given logpath (taken from path in self.logs)"""

    return os.path.join(self.path, logpath).replace("\\", "/")

  def add(self, logpath, fields):
    """Adds a logpath to the list, given as a relative (TAR/ZIP) or absolute (LOG/DIR) path
       to a log file, and a list of fields extracted from the path as a re.groupdict dictionary."""

    # Retrieves last modification time from file or archive member
    if self.type in ['LOG', 'DIR']:
      info = None
      tm = datetime.datetime.fromtimestamp(os.stat(logpath).st_mtime)
    elif self.type is 'TAR':
      info = self.archive.getmember(logpath)
      tm = datetime.datetime.fromtimestamp(info.mtime)
    elif self.type is 'ZIP':
      info = self.archive.getinfo(logpath)
      i = info.date_time
      tm = datetime.datetime(i[0], i[1], i[2], i[3], i[4], i[5])

    # Updates time
    tm = tm.replace(microsecond=0)
    if tm < self.earliest : self.earliest = tm
    if tm > self.latest   : self.latest = tm

    # Gets size
    if self.type is 'ZIP': size = info.file_size
    elif self.type is 'TAR': size = info.size
    else: size = os.path.getsize(logpath)

    # Relative path to base path needs to be stored for DIR
    spath = os.path.relpath(logpath, self.path) if self.type is 'DIR' else logpath
    pseudoPath = self.getPseudoPath(spath)

    # Stores path
    self.logs.append(self.LogSourceFile(spath, pseudoPath, tm, size, info, fields))
    if self.verbosity >= 2:
      print "--", self.type, str(tm), pseudoPath, fields

  def count(self):
    return len(self.logs)

  def __str__(self):
    return self.type + " -- " + str(self.earliest) + " to " + str(self.latest) + " -- " + \
           str(self.count()) + " file(s) -- " + self.path


  def setDestinationPaths(self, outputdir, keepsourcedirs, globalsource):
    """Sets the destinationBasePath and destinationRelativePath members in log source objects"""

    # Option keepsourcedirs: appends extra directory to outputdir
    # If destination path already exists, then increases suffix "-000", "-001", etc
    if keepsourcedirs:
      if self.type is 'LOG':   #  or globalsource:
        mdir = ""
      else:
        (dir, mdir) = os.path.split(self.path)
        mdir += "-"
      i = 0
      done = False
      while not done:
        dir = os.path.join(outputdir, mdir + "%03d" % i)
        if not os.path.lexists(dir): done = True
        else: i += 1
      outputdir = dir

    # Set destination paths, keeps original order
    for l in self.logs:

      # Computes the prefix dir based on fields acquired from path filter, in alphabetical order
      pref = ""
      for kf in sorted(l.fields.keys()):
        p = l.fields[kf]
        if p is not None and len(p) > 0:
          for c in "\"\\/:*?<>|": p = p.replace(c, "_")
          pref = os.path.join(pref, p)

      # Sets path parts by default
      l.destinationBasePath = os.path.normpath(os.path.join(outputdir, pref))
      if self.type is 'LOG':
        # For type LOG: start relative path is only the filename
        l.destinationRelativePath = os.path.basename(l.path)
      else:
        # For other types: start relative path is the relative path inside archive or directory
        l.destinationRelativePath = os.path.normpath(l.path)


  def reduceDestinationPaths(self, joinlog4j, reducedirs):

    if joinlog4j or reducedirs:

      # Creates dictionary of dictionaries, with destination dirs as keys, and then paths as keys
      # and list of LogSourceFile objects
      # At the beginning each list contains only one element
      destinationPaths = dict()
      for l in self.logs:

        # Sets new entry in first dictionary if not already present, then stores log file object
        if l.destinationBasePath not in destinationPaths:
          destinationPaths[l.destinationBasePath] = dict()
        destinationPaths[l.destinationBasePath][l.destinationRelativePath] = [l]

      # Option joinlog4j: re-order and gather related log files
      if joinlog4j:

        for kbase in destinationPaths.keys():
          for dest in destinationPaths[kbase].keys():

            # Check if key still in dict as some keys will be removed
            if dest in destinationPaths[kbase]:

              # Put the related log files under the same destination file, removes found entries
              i = 1
              while (dest + "." + "%d"%i) in destinationPaths[kbase]:
                odest = dest + "." + "%d"%i
                destinationPaths[kbase][dest].extend(destinationPaths[kbase][odest])
                del destinationPaths[kbase][odest]
                i += 1
              destinationPaths[kbase][dest].reverse()

              # Updates offsets
              offset = 0
              for l in destinationPaths[kbase][dest]:
                l.offset = offset
                offset += l.size

      # Option reducedirs: find common path and removes it
      if reducedirs:

        for kbase in destinationPaths.keys():

          # Prepares new dictionary with paths for processing (keys same as content at beginning)
          newdests = dict()
          for dest in destinationPaths[kbase].keys():
            newdests[dest] = dest

          # Tries to remove top level directories until destinations overlap for at least one file
          done = False
          while not done:

            # For each dest path, removes top dir in path (if any), then puts it in a Python set
            s = set()
            for ndest in newdests.values():
              cropped = ndest.split(os.sep, 1)[-1]
              s.add(cropped)

            # If number of elements in set is the same as the original dict, then no path overlap
            if len(s) == len(newdests):
              # Updates newdests with cropped paths for next iterration
              noupdate = True # Will be set to False if one value is different than from last iter
              for ndest in newdests.keys():
                cropped = newdests[ndest].split(os.sep, 1)[-1]
                #print ">>cropped", cropped
                #print ">>newdests[ndest]", newdests[ndest]
                if cropped != newdests[ndest]: noupdate = False
                newdests[ndest] = cropped
              if noupdate: done = True  # Stops if no dir remains in dest paths
            else:
              done = True # Stops if next removed dir level would make path overlap, i.e. reduction OK

          # Updates main dictionary back with new destination paths
          for (old, new) in newdests.items():
            if new not in destinationPaths[kbase]:
              destinationPaths[kbase][new] = destinationPaths[kbase][old]
              del destinationPaths[kbase][old]


      # Finally updates self.logs list with destination path
      for kbase in destinationPaths.keys():
        for dest in destinationPaths[kbase].keys():
          for source in destinationPaths[kbase][dest]:
            source.destinationRelativePath = dest

      # Prints results of re-ordering using internal list
      if self.verbosity >= 2:
        print "\nNew destination paths and offsets in source log files:"
        for l in self.logs:
          print "--", l.size, l.offset, l.destinationBasePath, l.destinationRelativePath, l.path


  def extract(self, outputdir, keepsourcedirs=False, joinlog4j=False, reducedirs=False,
              globalsource=False):
    """Extract log files from this source to the outputdir"""

    print "\nStarting extraction of", self.type, self.path
    filenames = None  # Only for debug info
    prevdest = None   # Only for debug info

    # Adapts destination paths in self.logs list of LogSourceFile objects
    self.setDestinationPaths(outputdir, keepsourcedirs, globalsource)
    self.reduceDestinationPaths(joinlog4j, reducedirs)

    # Extract source files to destination files
    for l in self.logs:
      destFullPath = os.path.normpath(os.path.join(l.destinationBasePath, l.destinationRelativePath))

      # Checks if the destination directory exists, if not creates it
      dirpath = os.path.dirname(destFullPath)
      parts = list()
      while not (os.path.exists(dirpath) and os.path.isdir(dirpath)):
        (dirpath, part) = os.path.split(dirpath)
        parts.append(part)
      parts.reverse()
      for part in parts:
        dirpath = os.path.join(dirpath, part)
        if self.verbosity >= 2: print "-- Make directory", dirpath
        os.mkdir(dirpath)

      # Sets time values for re-setting once file has been closed
      destexists = os.path.exists(destFullPath)
      if destexists:
        curtime = datetime.datetime.fromtimestamp(os.stat(destFullPath).st_mtime)
      else:
        curtime = datetime.datetime.min

      # Opens source and destination files
      destfile = open(destFullPath, 'r+b' if destexists else 'wb')
      if self.type is 'LOG':   sourcefile = open(l.path, 'rb')
      elif self.type is 'DIR': sourcefile = open(os.path.join(self.path, l.path), 'rb')
      elif self.type is 'TAR': sourcefile = self.archive.extractfile(l.info)
      else:                    sourcefile = self.archive.open(l.info)

      # Copy/extract
      if self.verbosity >= 2:
        if not prevdest or prevdest != destFullPath:
          if filenames: print "---", filenames
          filenames = os.path.basename(l.path)
          prevdest = destFullPath
          print "--", "Depack" if self.type in ['TAR','ZIP'] else "Copy", "to", destFullPath
        else:
          filenames += " " + os.path.basename(l.path)
      destfile.seek(l.offset)
      shutil.copyfileobj(sourcefile, destfile, 1024*1024*10)

      # Closes source and destination files
      sourcefile.close()
      destfile.close()

      # Sets time on destination file to value in source log retrieved during scan,
      #   sets it only if later than set at creation (log4j join if files are in reverse order)
      timestamp = time.mktime((l.time if curtime < l.time else curtime).timetuple())
      os.utime(destFullPath, (timestamp, timestamp))

    # Last line not taken into account in loop
    if self.verbosity >= 2:
      print "---", filenames


  def search(self, searchContext, hideTimestamp):
    """Goes through all log files of the source and searches events if filename matches"""

    for logfile in self.logs:

      # Gets events matching filename
      if self.verbosity >= 2: print "\nSearching events in", logfile.path

      # Checks if path matches
      if searchContext.checkSource(logfile.pseudoPath, logfile.time):

        # Open file
        if self.type is 'ZIP':   sourcefile = self.archive.open(logfile.info)
        elif self.type is 'TAR': sourcefile = self.archive.extractfile(logfile.info)
        elif self.type is 'DIR': sourcefile = open(os.path.join(self.path, logfile.path), 'rb')
        else:                    sourcefile = open(logfile.path, 'rb')

        # Reads text lines from log file and searches for events
        done = False
        while not done:
          line = sourcefile.readline()
          if line == '':
            done = True
            line = None
          else:
            line = line.rstrip("\n\r")

          # Prints events if any found
          for ev in searchContext.checkLine(line):
            if self.verbosity >= 1 and not searchContext.chronological:
              ev.display(hideTimestamp)

          if self.verbosity >= 2 or searchContext.chronological:
            searchContext.printAdvancement(logfile.pseudoPath)

        # Closes file
        sourcefile.close()


class LogSet:

  def __init__(self, verbosity, eventTypes, pathFilter = ".*\\.log*"):
    """Inits object with verbosity (value 0 to 2), a LogEventList object, a pathfilter given
       as a regexp to search"""

    # Sets common variables
    self.verbosity = verbosity
    self.eventTypes = eventTypes
    self.rexPathFilter = re.compile(pathFilter, re.IGNORECASE)

    # List of log sources found during scan
    self.sources = list()

  def checkPathFilter(self, path):
    """Checks if the path matches the path filter after normalizing it to "/" separator,
       returns None if not otherwise returns the acquired named groups"""

    res = self.rexPathFilter.match(path.replace("\\", "/"))
    return res.groupdict() if bool(res) else None


  def scanPath(self, path, archivePathRex, file=None):
    """Opens recursively a file or directory for processing, using given path or file handle.
       During the scan, first each file name will be matched to the path filter,
       then otherwise matched to the archive path regexp"""

    # Number of items found in this run
    res = 0

    # Get fields for path given as argument
    fields = self.checkPathFilter(path)

    # Case 1 DIR: directory given as path, walk into sub-directories to find files or archives
    if not file and os.path.isdir(path):

      # Creates new LogSource to be filled, then iterates into directories
      source = LogSource(self.verbosity, 'DIR', path)
      for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:

          # Prepares path and fields
          fullpath = os.path.join(dirpath, filename)
          fields = self.checkPathFilter(fullpath)

          # Stores path to log file if path filter matches
          if fields is not None:  # fields can be empty while not None
            source.add(fullpath, fields)
            res += 1

          # Recurses in archive if archive found in directory
          elif archivePathRex.search(filename):
            res += self.scanPath(fullpath, archivePathRex)

      # Keeps LogSource only if logs were found
      if source.count() > 0:
        self.sources.append(source)
      return res

    # Case 2 LOG: single log file directly given as path (no check if it is an archive)
    # Stores as log only if path filter matches
    elif not file and os.path.isfile(path) and fields is not None:
      self.singleLogFiles.add(path, fields)
      return 1

    # Case 3 TAR/ZIP: given path points on archive file, or given handler on archive file in archive
    elif file or (not file and os.path.isfile(path) and archivePathRex.search(path)):
      tar = None
      zip = None

      # First tries to open the given file as tar
      if self.verbosity>=2:
        print "\nTrying to open as archive", path if not file else file.name
      try:
        if file:
          tar = tarfile.open(fileobj=file, mode='r:*')
        else:
          tar = tarfile.open(path, mode='r:*')
        if self.verbosity>=2: print "TAR: successfully open"
      except Exception as et:
        if self.verbosity>=2: print "TAR: tarfile.open error:", et

        # Then tries as zip
        try:
          zip = zipfile.ZipFile(file if file else path)
          if self.verbosity>=2: print "ZIP: successfully open"
        except Exception as ez:
          # Could not open file at all as archive
          if self.verbosity>=2: print "ZIP: zipfile.ZipFile.open error:", ez
          return 0

      # Either tar or zip was open, get archive file names to check them
      source = LogSource(self.verbosity, "TAR" if tar else "ZIP", path, tar if tar else zip)

      addedNames = set()
      for f in tar if tar else zip.namelist():
        name = f if zip else f.name
        fullpath = os.path.join(path, name)
        fields = self.checkPathFilter(fullpath)

        # Stores path if matching path filter
        if fields is not None and name not in addedNames:
          addedNames.add(name)
          source.add(name, fields)
          res += 1

        # Recurses into archive if extension matches
        elif fields is None and archivePathRex.search(fullpath):
          newFile = tar.extractfile(f) if tar else zip.open(f)
          res += self.scanPath(os.path.join(path, name), archivePathRex, newFile)

      if source.count() > 0:
        self.sources.append(source)
      return res


  def scanPaths(self, paths, extarchive):
    """Calls scanPath for a semi-colon separated list of filenames/dirnames, with semi-colon
       separated list of archive extensions"""

    # List of log files given directly to scan, to be filled by scanPath
    self.singleLogFiles = LogSource(self.verbosity, 'LOG', "")

    # Calls scanPath for all items in list
    print "\n--------------- BEGIN PATH SCAN -", time.strftime("%H:%M:%S"), "---------------"
    for p in paths.split(";"):
      print "\nScanning", p

      # Builds regexp for archive extensions and calls sub-function
      self.scanPath(p, re.compile("(?i)(" + extarchive.replace(";", "|") + ")$"))

    print "\n---------------- END PATH SCAN -", time.strftime("%H:%M:%S"), "----------------"

    # Adds log files given directly to list of sources
    if self.singleLogFiles.count() > 0:
      self.sources.append(self.singleLogFiles)


    # Displays found files
    print "\nRecognized sources:"
    for s in self.sources:
      print s


  def extract(self, outputdir, keepsourcedirs=False, joinlog4j=False, reducedirs=False,
              globalsource=False):
    """Extract log files from archives to the outputdir"""

    print "\n--------------- BEGIN EXTRACTION -", time.strftime("%H:%M:%S"), "---------------"

    for s in self.sources:
      s.extract(outputdir, keepsourcedirs, joinlog4j, reducedirs, globalsource)

    print "\n---------------- END EXTRACTION -", time.strftime("%H:%M:%S"), "----------------"


  def search(self, chronological, hideTimestamp, globalsource, outputdir):
    """Search events in log files"""

    print "\n--------------- BEGIN SEARCH -", time.strftime("%H:%M:%S"), "---------------"

    context = EventSearchContext(self.verbosity, self.eventTypes, chronological, outputdir)

    for s in self.sources:
      s.search(context, hideTimestamp)

    for ev in context.wrapup(outputdir):
      if chronological and self.verbosity >= 1:
        ev.display(hideTimestamp)

    print "\n---------------- END SEARCH -", time.strftime("%H:%M:%S"), "----------------"


def getDefaultEventType(params):

  # Gets values entered by user if at least the text pattern is given
  if params["rextext"]:
    le = EventType()
    le.init(params["rexfilename"], params["rextext"], params["rextimestamp"],
            int(params["multilinecount"]), params["casesensitive"], params["name"],
            params["description"], params["displayonmatch"], params["displayifchanged"],
            params["execoninit"], params["execonmatch"], params["execonwrapup"], )

    return le

  return None


def readEventsDefinition(params):
  """Common function to read XML events file and define default event from GUI/command-line"""

  # Inits vars
  loge = EventTypeList(int(params["verbosity"]))

  # Reads file(s) if given
  path = params["ineventtypes"]
  if path:
    paths = path.split(';')
    for p in paths:
      loge.readEventTypes(p)

  # Adds default event if defined
  le = getDefaultEventType(params)
  if le:
    loge[le.name] = le

  return loge


def splitLogPaths(params):

  # Handles global source option, i.e. returned list contains either a list of one string or
  # a list of parts of the path
  if params['globalsource']:
    return [params["inlogpaths"]]
  else:
    return params["inlogpaths"].split(';')


def overview(si):

  params = si.getValues()

  # Opens logs
  for paths in splitLogPaths(params):
    logs = LogSet(int(params["verbosity"]), readEventsDefinition(params), params["pathfilter"])
    logs.scanPaths(paths, params["extarchive"])


def extract(si):

  params = si.getValues()

  # Opens logs
  for paths in splitLogPaths(params):
    logs = LogSet(int(params["verbosity"]), readEventsDefinition(params), params["pathfilter"])
    logs.scanPaths(paths, params["extarchive"])

    logs.extract(params["outputdir"], params["keepsourcedirs"], params["joinlog4j"],
                 params["reducedirs"], params["globalsource"])

def search(si):

  params = si.getValues()

  # Gets event types including possibly the default event
  eventTypes = readEventsDefinition(params)

  # Opens logs
  if len(eventTypes) > 0:
    for paths in splitLogPaths(params):
      logs = LogSet(int(params["verbosity"]), eventTypes, params["pathfilter"])
      logs.scanPaths(paths, params["extarchive"])
      logs.search(params["chronological"], params["hidetimestamp"], params["globalsource"],
                  params["outputdir"])
  else:
    print "ERROR: no event type definition"


def saveDefaultEventType(si):

  params = si.getValues()

  # Inits vars
  outputEventTypes = EventTypeList(int(params["verbosity"]))

  # Parses destination file
  filename = params["outeventtypes"]

  # Parses existing output file if it exists
  if os.path.exists(filename):
    outputEventTypes.readEventTypes(filename)

  # Creates single default event from the values entered manually
  le = getDefaultEventType(params)
  if le:
    outputEventTypes.addEventType(le)
    if int(params["verbosity"]) >= 1:
      print "\nEvent to save:\n", le

  # Saves events
  if len(outputEventTypes) > 0:
    outputEventTypes.writeEventTypes(filename)
    print "\nEvent", le.name, "saved successfully in", filename
  else:
    print "ERROR: No event type definition"


def showEventTypes(si):
  eventTypes = readEventsDefinition(si.getValues())
  if len(eventTypes) > 0:
    eventTypes.printEventTypes()
  else:
    print "ERROR: no event type definition"


def main(argv):
  """Main procedure for command line processing and/or HMI"""

  si = bfcommons.ScriptInterface("ReguLog", __doc__, __version__, sys.argv[0])
  si.addCommonOptions()

  # Input file options

  desc = "Files/directories to be analyzed (semi-colon separated list)"
  si.addOption("Input paths", desc, 'MIDF', "i", "inlogpaths")

  desc = "If set for any command, log sources are treated together like one source during search"
  si.addOption("Global source", desc, 'B', "g", "globalsource", format='')

  desc = "In scan/extract/search operations, main path filter defined as a regex on pseudo-path "+\
         "of log files, used to select files recursively in directories and archives\n"          +\
         "The path matching is case-insensitive and needs to match the full pseudo-path (not "   +\
         "only a subpart of it, hence the regexp will likely start with '.*').\n"                +\
         "In the pseudo-path to be matched, the path separator is always set to '/' (instead of "+\
         "'\\' under Windows), in order to keep a common way to write patters whatever the OS. " +\
         "For files in archive, the pseudo-path has the form <achive-file-path>/"                +\
         "<log-file-path-in-archive>, where the archive-file-path part can, recursively, "       +\
         "contain archive file names in the same form.\n"                                        +\
         "If 'named groups' are acquired for a matching log file (Python syntax like "           +\
         "'(?P<name>pattern)'), the values are used to create additional levels of "             +\
         "directories during extract, appended to the 'outputdir' parameter in the alphabetical "+\
         "order of the group names.\n"                                                           +\
         "WARNING: because the search is performed on the full pseudo-path, the expression "     +\
         "may match non-wanted files due to text at the beginning of the source path. For "      +\
         "example '.*ipsec.*\.log.*' can match any file ending with '.log' in an archive called "+\
         "'ipsec-18122016.zip'. You can use '[^/]*' for parts where directories must be excluded."
  if 'aib' in __version__:
    # aib specific:
    val = "(.*_Logs\\.\\d{14}\\.(?P<arn>[^.]{,6})\\.pmf.*|.*)" +\
      "(/inbox/(?P<lsap>LSAP)/(?P<pn>[^/]+)/.*|" +\
      "(ics|bite|messaging|export|WLM|TLM|Diameter|Satcom|IMACS|PKI|abdc|GCM|ground|ipsec|agsm)"+\
      "[^/]*\\.log[^/]*|messages[\d\-/]*)"
  else:
    val = ".*\\.log.*"
  si.addOption("Path Filter Regex", desc, "R", "f", "pathfilter", val)

  desc = "Semicolon-separated list of valid archive extensions"
  val = ".zip;.tar;.tar.gz;.tgz"
  if 'aib' in __version__: val += ";.pmf"
  si.addOption("Archive extensions", desc, "S", "e", "extarchive", val, format='W160')

  desc = "Displays overview of input log files, based on filenamess/dirs structure (not content)"
  si.addCommand("Logs overview", desc, "overview", lambda: overview(si), ["inlogpaths"],
                ["pathfilter"])


  # Output directory

  desc = "Directory to store extracted files or files generated from search"
  si.addOption("Output directory", desc, 'OD', "o", "outputdir", format='L')

  desc = "If set for the extract command, an extra directory is created to store the extracted " +\
         "or copied files from each source of logs"
  si.addOption("Keep source directories", desc, 'B', "k", "keepsourcedirs", format='')

  # Extract options
  desc = "If set for the extract command, recognizes logs stored in log4j style (.log, .log.1, " +\
         "etc in same directory) and concatenates the files into one single .log file in the "   +\
         "directory"
  si.addOption("Join log4j", desc, 'B', "j", "joinlog4j", format='')

  desc = "If set for the extract command, the number of levels of directories is reduced to the "+\
         "common tree of the extracted/copied files"
  si.addOption("Reduce directories", desc, 'B', "r", "reducedirs", format='')

  si.addCommand("Extract", "Extract/copy all files from given archives/dirs into output directory",
                "extract", lambda: extract(si), ["inlogpaths", "outputdir"], ["pathfilter"])


  # Events input file
  desc = "Input XML files with event types definition to be searched (semi-colon separated "     +\
         "list)\nThis list of event types (i.e. log patterns) can be combined with the 'default "+\
         "event type' defined below through the GUI or using the command-line."
  si.addOption("Patterns XML files", desc, 'MIF', "x", "ineventtypes", format='L')

  si.addCommand("Show Event Types", "Prints definition of the applicable event types",
                "show-event-types", lambda: showEventTypes(si), format='')

  # Search events

  desc = "If set for search, displayed text output is not prefixed with a timestamp"
  si.addOption("Hide timestamps", desc, 'B', "t", "hidetimestamp", format='')

  desc = "If set for the search command, found events are stored and then displayed time-"       +\
         "ordered at the end of the search"
  si.addOption("Chronological", desc, 'B', "c", "chronological", format='')

  si.addCommand("Search Events", "Search for events in the input files",
                "search", lambda: search(si), ["inlogpaths"],
                ["pathfilter", "outputdir", "ineventtypes"])

# FIXME: modify bfScriptInterface to take all parameters into account whater the position of
#        the command on the HMI
#                "name", "description", "rexfilename",
#                 "rextext", "rextimestamp", "displayonmatch",
#                 "execoninit", "execonmatch", "execonwrapup"])


  # Default event type definition


  desc = "For the Default Event Type, regular expression on file name of log files, used for "   +\
         "search operations\nUse '.*' or '.*\\.log.*' to match all log files ('.*' means any "   +\
         "number of any character), or use a part of the name of a file to target specific log " +\
         "files (e.g. 'messaging' to match 'bsmessaging' and 'messagingservice'). The search is "+\
         "case-sensitive."
  si.addOption("Filename Regex", desc, "R", "F", "rexfilename", "(\.log|messages)[.\d\-]*",
               format="N;W130;GDefault Event Type")

  desc = "For the Default Event Type, regular expression to match the timestamp part, on the "   +\
         "first line of event once matched\nThe default value should match most kinds of "       +\
         "timestamps, such that the value can be used in most cases. The timestamp regular "     +\
         "expression needs to contain the following 'named groups', caught using the regular "   +\
         "expression special syntax '(?P<fieldname>pattern)':\n"                                 +\
         "  _Y: year (4 or 2 digits supported, default to file timestamp if not present)\n"      +\
         "  _M: month (2 digits or at least 3 first letters of the month name in English)\n"     +\
         "  _D: day, _h: hour, _m: minute, _s: second (default to 00 if not present)"
  if 'aib' in __version__:
    # aib specific:
    val = r"^#\d\d#(?P<_Y>\d{4})(?P<_M>\d\d)(?P<_D>\d\d)-(?P<_h>\d\d)(?P<_m>\d\d)(?P<_s>\d\d);"  +\
     r"([\d\-;]+#){3}(?P<FPFWS>\d\d)#([\-\w]+#){2}(?P<FLT>[^# ]+) *#"                                +\
     r"\.*(?P<ACID>[^#\.]+)#([^#]+##?){9}|"                                                      +\
     r"^\[(?P<_D1>\d\d)/(?P<_M1>\d\d)/(?P<_Y1>\d?\d?\d\d) (?P<_h1>\d\d):(?P<_m1>\d\d):"          +\
     r"(?P<_s1>\d\d)\] \w+ *- |"                                                                 +\
     r"^(?P<_Y2>\d{4})-(?P<_D2>\d\d)-(?P<_M2>\d\d) (?P<_h2>\d\d):(?P<_m2>\d\d):"                 +\
     r"(?P<_s2>\d\d)([^\-]+- ){2}|"                                                              +\
     r"^(?P<_M3>[JFMASOND][a-z]{2}) (?P<_D3>[0123 ]\d) (?P<_h3>\d\d):(?P<_m3>\d\d):"             +\
     r"(?P<_s3>\d\d) (?P<HOST>[^ ]+) |"                                                                          +\
     r"^#(?P<_Y4>\d{4}) (?P<_M4>\d\d) (?P<_D4>\d\d) (?P<_h4>\d\d):(?P<_m4>\d\d):(?P<_s4>\d\d)#"
  else:
    val = r"^(?P<_Y>\d{4})-(?P<_D>\d\d)-(?P<_M>\d\d) (?P<_h>\d\d):(?P<_m>\d\d):(?P<_s>\d\d)"
  si.addOption("Timestamp Regex", desc, 'R', "S", "rextimestamp", val, format='')

  desc = "For the Default Event Type, regular expression text pattern used for matching text "   +\
         "in log files\nThis regexp is used also for fields extraction with Python-style 'named "+\
         "groups' using the specific syntax '(?P<fieldname>pattern)'.\n"                         +\
         "WARNING: as it is a regular expression, it may be necessary to escape some characters "+\
         "if text is search directly, i.e. the characters '()[]\\.^$' need to be "               +\
         "prefixed with a backslash character e.g. '\\['."
  si.addOption("Text Regex", desc, 'R', "T", "rextext")

  desc = "For the Default Event Type, number of lines to gather for multiline event search for " +\
         "the default event type"
  si.addOption("Multiline", desc, 'S', "M", "multilinecount", "1", format='W30')

  desc = "If set for search with default event type, the text regexp is searched in "            +\
         "case-sensitive mode"
  si.addOption("Case", desc, 'B', "A", "casesensitive", format='')

  desc = "For the Default Event Type, string displayed if the text regex matches the log text\n" +\
         "Extracted and pre-defined fields can be displayed within the text message as such:\n"  +\
         " - {fieldname} for the value of the field in the current event\n"                      +\
         " - {fieldname@evname} for the latest value of a field in another event\n"              +\
         " - {fieldname@evname:rfieldname=cfieldname} for lookup of the value of a field in "    +\
         "another event such that the value of the field rfieldname equals the value of the "    +\
         "field cfieldname in this event.\n"                                                     +\
         "The following pre-defined fields are available:\n"                                     +\
         " _raw: line of text for the event\n"                                                   +\
         " _core: same as _raw without the part matching the timestamp if recognized\n"          +\
         " _flat: same as _raw without end of lines\n"                                           +\
         " _flat_core: same as _core without end of lines\n"                                     +\
         " _name: name of event type\n"                                                          +\
         " _description: description of event type\n"                                            +\
         " _timestamp: timestamp string (date/time ISO format), _time: time, _date: date\n"      +\
         " _line_number: line number in file\n"                                                  +\
         " _source_path: source pseudopath of the log file\n"                                    +\
         " _source_filename: basename of the source path"
  val = "{_raw} at {_source_path}:{_line_number}"
  si.addOption("Display on Match", desc, 'S', "M", "displayonmatch", val)

  desc = "For the Default Event Type, if set to true, the displayonmatch string is displayed if "+\
         "text regex matches and extracted fields are different than the previous match (except "+\
         "system fields like _timestamp)"
  si.addOption("Display if Changed", desc, 'B', "C", "displayifchanged", format='')

  # Python Execution code

  desc = "For the Default Event Type, Python code executed on search start\nThe code is "        +\
         "executed from an encapsulating object common for all event types. It is possible to "  +\
         "define variables for use in other Python code parts by using the prefix 'self.', "     +\
         "e.g. 'self.my_counter'. The following pre-defined variables are available:\n"          +\
         " - name: the name of the event type\n"                                                 +\
         " - self.events: Dictionary with lists of events, referenced by event type name (the "  +\
         "lists are empty at initialization)\n"                                                  +\
         " - self.chronological: Set to True if the search is sorted chronologically\n"          +\
         " - self.output_directory: Contains the path given as outputdir otherwise None"
  si.addOption("Exec On Init", desc, 'T', "I", "execoninit")

  desc = "For the Default Event Type, Python code executed when the text regexp matches\nIn "    +\
         "addition to the definition given for the execoninit option, the following variables "  +\
         "and functions are available:\n"                                                        +\
         " - event: the current event with fields set from the text regexp and system fields\n"  +\
         " - event.set_field(name, value): sets an existing or new field (exception raised if "  +\
         "trying to set an existing system field)\n"                                             +\
         " - event.set_fields(dict): sets existing or new fields from a dictionary (no "         +\
         "exception raised)\n"                                                                   +\
         " - event.add_field(name, value): adds a new field (exception raised if the field "     +\
         "already exists)\n"                                                                     +\
         " - event.add_fields(dict): adds new fields from a dictionary (no exception raised)\n"  +\
         " - event.has_field(name): returns true if the field already exists in event\n"         +\
         " - event.get_field(name): returns the value of the given field\n"                      +\
         " - event.get_user_fields(): returns the user fields as a dictionary\n"                 +\
         " - event.get_system_fields(): returns the system fields as a dictionary\n"             +\
         " - self.events.get_events(name, fields, before, limit): returns an iterator on "       +\
         "events in the list according to several optional criteria, e.g. "                      +\
         "get_event(fields={'_name':'val'}, before=event):\n"                                    +\
         "    - name: matches events with the given name (i.e. name of the related event type "  +\
         "or '_name' field), provided as a character string\n"                                   +\
         "    - fields: matches events with the given fields set to the given values (all "      +\
         "fields need to match), given as a dictionary of name/value pairs\n"                    +\
         "    - before: matches events with a timestamp earlier than or equal to the given "     +\
         "time reference, provided as a timestamp (datetime.datetime object) or as an event "    +\
         "(in this case it is ensured that the sequence number of the matched event is lower "   +\
         "than the sequence number of the event given as reference, in order to ensure "         +\
         "fine-grained event ordering in case timestamp values are equal)\n"                     +\
         "    - limit: maximum number of events to be returned (default 1)"                      +\
         " - self.events.get_event(name, fields, before): returns a single event with the same " +\
         "parameters as get_events (execpt the limit parameter)"
  si.addOption("Exec On Match", desc, 'T', "X", "execonmatch", format='')

  desc = "Python code executed on wrapup (end of the search), same pre-defined variables and "   +\
         "functions can be used as in execonstart and execonmatch (except current 'event' local "+\
         "variable)"
  si.addOption("Exec On Wrapup", desc, 'T', "W", "execonwrapup", format='')

  desc = "Name of of the Default Event Type given directly through the GUI or the command-line\n"+\
         "The name is used to store the event once fully defined and for data exports."
  si.addOption("Name", desc, "S", "N", "name", format='N;W180')

  desc = "Description of the extra event, used for storing event type once fully defined"
  si.addOption("Description", desc, "S", "D", "description", format='')


  # Events output fields

  desc = "XML file to store Default Event Type definition"
  si.addOption("Output patterns file", desc, 'OF', "p", "outeventtypes", format='')

  desc = "Saves the given default event type into new or existing XML file\nThe output "         +\
         "file is re-parsed and re-written completely using the last available definition."
  si.addCommand("Save Default Event Type", desc,  "save-event-type", lambda: saveDefaultEventType(si),
                ["outeventtypes", "name", "description", "rexfilename", "rextext"],
                ["rextimestamp", "displayonmatch", "displayifchanged", "execoninit", "execonmatch",
                 "execonwrapup"])

  si.run()


# Real start of the script
if __name__ == "__main__":
  main(sys.argv[1:])
  sys.exit(0)


