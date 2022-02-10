# -*- coding: utf-8 -*-

#
# Author: Roland Pihlakas, 2017 - 2021
#
# roland@simplify.ee
#


import os
import sys
import io
import time

import datetime

import traceback



# https://stackoverflow.com/questions/333995/how-to-detect-that-python-code-is-being-executed-through-the-debugger
is_dev_machine = (os.name == 'nt')
debugging = (is_dev_machine and sys.gettrace() is not None) and (1 == 1)  # debugging switches



# TODO
# from MyPool import current_process_index, parent_exited, exiting
current_process_index = 0
parent_exited = False
exiting = False



current_request_id = None


pid = os.getpid()
pid_str = " :    " + str(pid).rjust(7) + " :    "



# set up console colors
# https://en.wikipedia.org/wiki/ANSI_escape_code#SGR
ansi_PREFIX = '\033['
ansi_RESET = '\033[0m'
ansi_INTENSE = '\033[1m'      # bold or bright colour variation
ansi_SLOWBLINK = '\033[5m'    # inconsistent support in terminals
ansi_REVERSE = '\033[7m'      # inconsistent support in terminals
# foreground colors:
ansi_BLACK = '\033[30m' 
ansi_RED = '\033[31m' 
ansi_GREEN = '\033[32m'
ansi_YELLOW = '\033[33m'
ansi_BLUE = '\033[34m'
ansi_MAGENTA  = "\033[35m"
ansi_CYAN  = "\033[36m"
ansi_WHITE  = "\033[37m"



ansi_colors_inited = None

def init_colors():
  global ansi_colors_inited

  if ansi_colors_inited is not None:
    return;

  if os.name == "nt":
    ansi_colors_inited = False
    try:
      # https://github.com/tartley/colorama
      # 
      # On Windows, calling init() will filter ANSI escape sequences out of any text sent to stdout or stderr, and replace them with equivalent Win32 calls.
      # 
      # On other platforms, calling init() has no effect (unless you request other optional functionality; see “Init Keyword Args”, below). By design, this permits applications to call init() unconditionally on all platforms, after which ANSI output should just work.
      # 
      # To stop using Colorama before your program exits, simply call deinit(). This will restore stdout and stderr to their original values, so that Colorama is disabled. To resume using Colorama again, call reinit(); it is cheaper than calling init() again (but does the same thing).
      import colorama
      colorama.init()
      ansi_colors_inited = True
    except Exception as ex:
      pass
  else:   #/ if os.name == "nt":
    ansi_colors_inited = True
  #/ if os.name == "nt":

#/ def init_colors():


def get_now_str():

  now_str = datetime.datetime.strftime(datetime.datetime.now(), '%m.%d %H:%M:%S')
  return now_str

#/ def get_now_str():


# https://stackoverflow.com/questions/14906764/how-to-redirect-stdout-to-both-file-and-console-with-scripting
class Logger(object):

  def __init__(self, terminal, logfile, is_error_log):

    self.is_error_log = is_error_log


    if (terminal 
      and os.name == "nt" 
      and not isinstance(terminal, Logger)):    # NB! loggers can be chained for log file replication purposes, but colorama.AnsiToWin32 must not be chained else colour info gets lost

      try:
        import colorama
        init_colors()
        # NB! use .stream in order to be able to call flush()
        self.terminal = colorama.AnsiToWin32(terminal).stream # https://github.com/tartley/colorama
      except Exception as ex:
        self.terminal = terminal

    else:

      self.terminal = terminal


    self.log = None

    try:
      if logfile is not None:
        self.log = io.open(logfile, "a", 1024 * 1024, encoding="utf8", errors='ignore')    # https://stackoverflow.com/questions/12468179/unicodedecodeerror-utf8-codec-cant-decode-byte-0x9c
    except Exception as ex:
      msg = "Exception during Logger.__init__ io.open: " + str(ex) + "\n" + traceback.format_exc()
  
      try:
        self.terminal.write(ansi_RED + ansi_INTENSE + msg + ansi_RESET)
      except Exception as ex:
        pass

    try:
      if self.log is not None and not self.log.closed:
        self.log.flush()

    except Exception as ex:   # time_limit.TimeoutException

      if (is_dev_machine or not self.is_error_log) and self.terminal:

        msg = str(ex) + "\n" + traceback.format_exc()
  
        try:
          self.terminal.write(ansi_RED + ansi_INTENSE + msg + ansi_RESET)
        except Exception as ex:
          pass

      #/ if (is_dev_machine or not self.is_error_log) and self.terminal:

  #/ def __init__(self, terminal, logfile, is_error_log):  


  def write(self, message_in):
    

    if parent_exited or exiting:  # NB!
      return


    # if message_in.strip() == "":
    #   return

    if isinstance(message_in, bytes):
      message = message_in.decode("utf-8", 'ignore')
    else:
      message = message_in


    now = get_now_str()

    newline_prefix = now + pid_str + str(current_process_index).rjust(6) + " :    "
    message_with_timestamp = newline_prefix + message.replace('\n', '\n' + newline_prefix)

    if message == "" or (message[-1] != "\n" and message[-1] != "\r"):
      # message += "\n"
      message_with_timestamp += "\n"


    message_with_timestamp = message_with_timestamp.encode('utf8', 'ignore').decode("utf8", 'ignore') #.decode('latin1', 'ignore'))


    if (is_dev_machine or not self.is_error_log) and self.terminal:   # error_log output is hidden from live console

      try:

        use_ansi_colour = True and ((False or self.is_error_log) 
                          and (ansi_PREFIX not in message)  # NB! ensure that we do not override any colours present in the message
                          and message.strip() != "")        # optimisation for newlines
        if use_ansi_colour:
          self.terminal.write(ansi_RED + ansi_INTENSE)

        self.terminal.write(message_in) # NB! need to call write for message body in a separate line since message_in might be byte array not a string

        if use_ansi_colour:
          self.terminal.write(ansi_RESET)

      except Exception as ex:   # time_limit.TimeoutException
        msg = str(ex) + "\n" + traceback.format_exc()

        try:
          if self.log is not None and not self.log.closed:
            self.log.write(msg)  
            self.log.flush()
        except Exception as ex:
          pass

    #/ if (is_dev_machine or not self.is_error_log) and self.terminal:


    if message.strip() != "":  # NB! still write this message to console since it might contain progress bars or other formatting

      try:
        if self.log is not None and not self.log.closed:
          self.log.write(message_with_timestamp.strip() + "\n")  # NB! strip 
          self.log.flush()

      except Exception as ex:   # time_limit.TimeoutException

        if (is_dev_machine or not self.is_error_log) and self.terminal:

          msg = str(ex) + "\n" + traceback.format_exc()
  
          try:
            self.terminal.write(ansi_RED + ansi_INTENSE + msg + ansi_RESET)
          except Exception as ex:
            pass

        #/ if (is_dev_machine or not self.is_error_log) and self.terminal:

    #/ if message.strip() != "":

  #/ def write(self, message_with_timestamp): 


  def flush(self):

    try:
      if self.terminal:
        self.terminal.flush()

    except Exception as ex:   # time_limit.TimeoutException
      msg = str(ex) + "\n" + traceback.format_exc()

      try:
        if self.log is not None and not self.log.closed:
          self.log.write(msg)  
          self.log.flush()
      except Exception as ex:
        pass


    try:
      if self.log is not None and not self.log.closed:
        self.log.flush()

    except Exception as ex:   # time_limit.TimeoutException

      if (is_dev_machine or not self.is_error_log) and self.terminal:

        msg = str(ex) + "\n" + traceback.format_exc()
  
        try:
          self.terminal.write(ansi_RED + ansi_INTENSE + msg + ansi_RESET)
        except Exception as ex:
          pass

      #/ if (is_dev_machine or not self.is_error_log) and self.terminal:
    
    pass 

  #/ def flush(self): 
  
  
  @property
  def encoding(self):
    
    return self.terminal.encoding
    #return "utf8"


  def fileno(self):

    return self.terminal.fileno()

#/ class Logger(object):


def rename_log_file_if_needed(filename, max_tries = 10):

  if os.path.exists(filename):

    try:

      filedate = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
      filedate_str = datetime.datetime.strftime(filedate, '%Y.%m.%d-%H.%M.%S')

      new_filename = filename + "-" + filedate_str + ".txt"
      if filename != new_filename:

        try_index = 1
        while True:

          try:

            os.rename(filename, new_filename)
            return

          except Exception as ex:

            if try_index >= max_tries:
              raise

            try_index += 1
            print("retrying log file rename: " + filename)
            time.sleep(1)
            continue

          #/ try:

      #/ if filename != new_filename:

    except Exception as ex:
      pass

  #/ if os.path.exists(filename):

#/ def rename_log_file_if_needed(filename):


def logger_set_current_request_id(new_current_request_id):
  global current_request_id

  current_request_id = new_current_request_id

#/ def logger_set_current_request_id(new_current_request_id):

