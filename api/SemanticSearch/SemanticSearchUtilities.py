# -*- coding: utf-8 -*-

#
# Author: Roland Pihlakas, 2021
#
# roland@simplify.ee
#


import os
import sys
import io
import gzip
import pickle


import time
import textwrap
import shutil

from progressbar import ProgressBar # NB! need to load it before init_logging is called else progress bars do not work properly for some reason

import requests
import asyncio
# import aiodebug.log_slow_callbacks
# import aiodebug.monitor_loop_lag
# from aiofile import aiofiles.open   # does not support flush method
import aiofiles                       # supports flush method
import aiofiles.os

import functools
from functools import reduce
import operator

import numpy as np
# import pandas as pd

from SemanticSearchLogger import get_now_str, init_colors, ansi_INTENSE, ansi_RED, ansi_GREEN, ansi_BLUE, ansi_CYAN, ansi_RESET



loop = asyncio.get_event_loop()



is_dev_machine = (os.name == 'nt')
debugging = (is_dev_machine and sys.gettrace() is not None) and (1 == 1)  # debugging switches

if is_dev_machine or debugging:   # TODO!! refactor to a separate function called by the main module

  np_err_default = np.geterr()
  np.seterr(all='raise')  # https://stackoverflow.com/questions/15933741/how-do-i-catch-a-numpy-warning-like-its-an-exception-not-just-for-testing
  np.seterr(under=np_err_default["under"])
  # np.seterr(divide='raise')


  if True:

    import aiodebug.log_slow_callbacks
    # import aiodebug.monitor_loop_lag

    aiodebug.log_slow_callbacks.enable(30 if is_dev_machine else 10)  # https://stackoverflow.com/questions/65704785/how-to-debug-a-stuck-asyncio-coroutine-in-python
    # aiodebug.monitor_loop_lag.enable(statsd_client) # TODO!

#/ if is_dev_machine or debugging:


if False and debugging:   # enable nested async calls so that async methods can be called from Immediate Window of Visual studio    # disabled: it is not compatible with Stampy wiki async stuff
  import nest_asyncio
  nest_asyncio.apply()


# https://stackoverflow.com/questions/28452429/does-gzip-compression-level-have-any-impact-on-decompression
# there's no extra overhead for the client/browser to decompress more heavily compressed gzip files
compresslevel = 9   # -6 is default level for gzip: https://linux.die.net/man/1/gzip
# https://github.com/ebiggers/libdeflate

data_dir = "data"



def safeprint(text, is_pandas = False):

  if True or (is_dev_machine and debugging):

    screen_width = shutil.get_terminal_size((200, 50)).columns - 1
    np.set_printoptions(linewidth=screen_width, precision=2, floatmode="maxprec_equal") # "maxprec_equal": Print at most precision fractional digits, but if every element in the array can be uniquely represented with an equal number of fewer digits, use that many digits for all elements.

    if is_pandas:
      import pd
      pd.set_option("display.precision", 2)
      pd.set_option("display.width", screen_width)        # pandas might fail to autodetect screen width when running under debugger
      pd.set_option("display.max_columns", screen_width)  # setting display.width is not sufficient for some  reason
      pd.set_option("display.max_rows", 100) 


  text = str(text).encode('utf8', 'ignore').decode('ascii', 'ignore')

  if False:
    init_colors()
    print(ansi_CYAN + ansi_INTENSE + text + ansi_RESET)  # NB! need to concatenate ANSI colours not just use commas since otherwise the terminal.write would be called three times and write handler might override the colour for the text part
  else:
    print(text)

#/ def safeprint(text):


# need separate handling for error messages since they should not be sent to the terminal by the logger
def safeprinterror(text, is_pandas = False):

  if True or (is_dev_machine and debugging):

    screen_width = shutil.get_terminal_size((200, 50)).columns - 1
    np.set_printoptions(linewidth=screen_width, precision=2, floatmode="maxprec_equal") # "maxprec_equal": Print at most precision fractional digits, but if every element in the array can be uniquely represented with an equal number of fewer digits, use that many digits for all elements.

    if is_pandas:
      import pd
      pd.set_option("display.precision", 2)
      pd.set_option("display.width", screen_width)        # pandas might fail to autodetect screen width when running under debugger
      pd.set_option("display.max_columns", screen_width)  # setting display.width is not sufficient for some reason
      pd.set_option("display.max_rows", 100) 


  text = str(text).encode('utf8', 'ignore').decode('ascii', 'ignore')

  if True:
    init_colors()
    print(ansi_RED + ansi_INTENSE + text + ansi_RESET, file=sys.stderr)  # NB! need to concatenate ANSI colours not just use commas since otherwise the terminal.write would be called three times and write handler might override the colour for the text part
  else:
    print(text, file=sys.stderr)

#/ def safeprinterror(text):


def print_exception(msg):

  msg = "Exception during processing " + type(msg).__name__ + " : " + str(msg)  + "\n"

  safeprinterror(msg)

#/ def print_exception(msg):


# https://stackoverflow.com/questions/5849800/tic-toc-functions-analog-in-python
class Timer(object):

  def __init__(self, name=None, quiet=False):
    self.name = name
    self.quiet = quiet

  def __enter__(self):

    if not self.quiet and self.name:
      safeprint(get_now_str() + " : " + self.name + " ...")

    self.tstart = time.time()

  def __exit__(self, type, value, traceback):

    elapsed = time.time() - self.tstart

    if not self.quiet:
      if self.name:
        safeprint(get_now_str() + " : " + self.name + " totaltime: {}".format(elapsed))
      else:
        safeprint(get_now_str() + " : " + "totaltime: {}".format(elapsed))
    #/ if not quiet:

#/ class Timer(object):


async def rename_temp_file(filename, make_backup = False):  # NB! make_backup is false by default since this operation would not be atomic

  max_tries = 20
  try_index = 1
  while True:

    try:

      if make_backup and os.path.exists(filename):

        if os.name == 'nt':   # rename is not atomic on windows and is unable to overwrite existing file. On UNIX there is no such problem
          if os.path.exists(filename + ".old"):
            if not os.path.isfile(filename + ".old"):
              raise ValueError("" + filename + ".old" + " is not a file")
            await aiofiles.os.remove(filename + ".old")

        await aiofiles.os.rename(filename, filename + ".old")

      #/ if make_backup and os.path.exists(filename):


      if os.name == 'nt':   # rename is not atomic on windows and is unable to overwrite existing file. On UNIX there is no such problem
        if os.path.exists(filename):
          if not os.path.isfile(filename):
            raise ValueError("" + filename + " is not a file")
          await aiofiles.os.remove(filename)

      await aiofiles.os.rename(filename + ".tmp", filename)

      return

    except Exception as ex:

      if try_index >= max_tries:
        raise

      try_index += 1
      safeprint("retrying temp file rename: " + filename)
      asyncio.sleep(5)
      continue

    #/ try:

  #/ while True:

#/ def rename_temp_file(filename):


async def delete_file(filename):

  filename = os.path.join(data_dir, filename)

  max_tries = 20
  try_index = 1
  while True:

    try:
      if os.path.exists(filename):
        if not os.path.isfile(filename):
          raise ValueError("" + filename + " is not a file")
        await aiofiles.os.remove(filename)

      return

    except Exception as ex:

      if try_index >= max_tries:
        raise

      try_index += 1
      safeprint("retrying file delete: " + filename)
      asyncio.sleep(5)
      continue

    #/ try:

  #/ while True:

#/ def delete_file(filename):


def format_long_text(text, padding_len, newline_sufix):

  screen_width = shutil.get_terminal_size((80, 20)).columns - 1

  text = "\n".join(textwrap.wrap(text, width = screen_width - len(newline_sufix.expandtabs()) - padding_len))
  # text = textwrap.indent(text, " " * padding_len)
  text = text.replace('\n', '\n' + newline_sufix + ' ' * padding_len)
  return text

#/ def format_long_text(text, padding_len, newline_sufix):


def init_logging(caller_filename = "", caller_name = "", log_dir = "logs", max_old_log_rename_tries = 10):

  from Logger import Logger, rename_log_file_if_needed


  logfile_name_prefix = caller_filename + ("_" if caller_filename else "")


  full_log_dir = os.path.join(data_dir, log_dir)
  if not os.path.exists(full_log_dir):
    os.makedirs(full_log_dir)


  rename_log_file_if_needed(os.path.join(full_log_dir, logfile_name_prefix + "standard_log.txt"), max_tries = max_old_log_rename_tries)
  rename_log_file_if_needed(os.path.join(full_log_dir, logfile_name_prefix + "error_log.txt"), max_tries = max_old_log_rename_tries)
  rename_log_file_if_needed(os.path.join(full_log_dir, logfile_name_prefix + "request_log.txt"), max_tries = max_old_log_rename_tries)


  if not isinstance(sys.stdout, Logger):
    sys.stdout = Logger(sys.stdout, os.path.join(full_log_dir, logfile_name_prefix + "standard_log.txt"), False)
    if caller_name == "__main__":
      sys.stdout.write("--- Main process " + caller_filename + " ---\n")
    else:
      sys.stdout.write("--- Subprocess process " + caller_filename + " ---\n")

  if not isinstance(sys.stderr, Logger):
    sys.stderr = Logger(sys.stdout, os.path.join(full_log_dir, logfile_name_prefix + "error_log.txt"), True) # NB! redirect stderr to stdout so that error messages are saved both in standard_log as well as in error_log


  if caller_name == '__main__':
    request_logger = Logger(terminal=None, logfile=os.path.join(full_log_dir, logfile_name_prefix + "request_log.txt"), is_error_log=False)
  else:
    request_logger = None

  return request_logger

#/ def init_logging():


# protects against decompression bombs
def decompress_with_limit(data, limit=None):  

  if limit is None:

    return gzip.decompress(data)

  else:

    with io.BytesIO(data) as fh:
      with gzip.GzipFile(fileobj=fh, mode="rb") as gzip_file:

        chunksize = 1024 * 1024    # NB! read in 1MB chunks else gzip will allocate all limit bytes even if they actually will not be needed
        chunks = []
        length = 0
        for i in range(0, limit + 1, chunksize):  # NB! + 1 to detect over-limit data 
          chunk = gzip_file.read(chunksize)
          chunks.append(chunk)
          length += len(chunk)

        if length > limit:
          raise ValueError("Decompressed data is too large")

        return b''.join(chunks)

      #/ with gzip.GzipFile(fileobj=bytes_reader, mode="r") as fh:
    #/ with BytesIO(data) as bytes_reader:

#/ def decompress_with_limit(data, limit=None):


async def async_request(method, *args, **kwargs):

  if len(kwargs) > 0:
    return await loop.run_in_executor(None, functools.partial(method, *args, **kwargs))
  else:
    return await loop.run_in_executor(None, method, *args)

#/ def async_request(method, *args, **kwargs):


# https://github.com/psf/requests/issues/1751
# https://stackoverflow.com/questions/23514256/http-request-with-timeout-maximum-size-and-connection-pooling
# https://stackoverflow.com/questions/22346158/python-requests-how-to-limit-received-size-transfer-rate-and-or-total-time
async def request_with_content_limit(url, is_post = False, data = None, timeout_sec = None, content_limit = None):

  start_time = time.time()

  # TODO!! use aiohttp 

  if not is_post:
    # As of requests release 2.3.0 the timeout applies to streaming requests too - https://stackoverflow.com/questions/22346158/python-requests-how-to-limit-received-size-transfer-rate-and-or-total-time
    # disable compression by NGINX since we will compress and decompress manually using gzip in order to protect against decompression bombs
    # NB! use empty string not None for Accept-Encoding: "*" Matches any content encoding not already listed in the header. This is the default value if the header is not present. It doesn't mean that any algorithm is supported; merely that no preference is expressed. - https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Encoding
    request = await async_request(requests.get, url, stream=True, timeout=timeout_sec, headers={'Accept-Encoding': ''})
  else:
    assert(data is not None)
    # As of requests release 2.3.0 the timeout applies to streaming requests too - https://stackoverflow.com/questions/22346158/python-requests-how-to-limit-received-size-transfer-rate-and-or-total-time
    # disable compression by NGINX since we will compress and decompress manually using gzip in order to protect against decompression bombs
    # NB! use empty string not None for Accept-Encoding: "*" Matches any content encoding not already listed in the header. This is the default value if the header is not present. It doesn't mean that any algorithm is supported; merely that no preference is expressed. - https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Encoding
    request = await async_request(requests.post, url, data=data, stream=True, timeout=timeout_sec, headers={'Accept-Encoding': ''})


  with request:

    assert(request.request.headers.get('Accept-Encoding') == "")

    request.raise_for_status()

    if int(request.headers.get('Content-Length')) > content_limit:
      raise ValueError('Response is too large')

    # All decompression is handled in urllib3 in either case, no protection against a decompression bomb is included in that. - https://stackoverflow.com/questions/23514256/http-request-with-timeout-maximum-size-and-connection-pooling
    # content = next(request.iter_content(content_limit + 1))
    content = await loop.run_in_executor(None, functools.partial(request.raw.read, content_limit + 1, decode_content=False)) # NB! decode_content=False since automatic compression was disabled

    if len(content) > content_limit:
      raise ValueError('Response is too large')

    # request.close()

    return content

  #/ with request:


  #chunksize = 1024 * 1024
  #size = 0
  #data = []
  #for chunk in request.iter_content(chunksize):

  #  if time.time() - start_time > timeout:
  #    raise ValueError('Timeout reached')

  #  size += len(chunk)
  #  data.append(chunk)

  #  if size > your_maximum:
  #    raise ValueError('Response is too large')

  ##/ for chunk in r.iter_content(1024 * 1024):

  #return b''.join(data)

#/ def request_with_content_limit(url, is_post = False, data = None, timeout = None, content_limit = None):


def match_beginning(str, pattern):

  if len(str) < len(pattern):
    return False

  if str[0:len(pattern)] == pattern:
    return True
  else:
    return False

#/ def match_beginning(str, pattern):


def match_end(str, pattern):

  if len(str) < len(pattern):
    return False

  if str[-len(pattern):] == pattern:
    return True
  else:
    return False

#/ def match_end(text, pattern):


async def read_file(filename, default_data = {}, quiet = False):

  fullfilename = os.path.join(data_dir, filename)

  if not os.path.exists(fullfilename + ".gz"):
    return default_data

  with Timer("file reading : " + filename, quiet):

    try:
      async with aiofiles.open(fullfilename + ".gz", 'rb', 1024 * 1024) as afh:
        compressed_data = await afh.read()    # TODO: decompress directly during reading and without using intermediate buffer for async data
        with io.BytesIO(compressed_data) as fh:   
          with gzip.open(fh, 'rb') as gzip_file:
            data = pickle.load(gzip_file)
    except FileNotFoundError:
      data = default_data

  #/ with Timer("file reading : " + filename):

  return data

#/ def read_file(filename):


async def save_file(filename, data, quiet = False, make_backup = False):

  haslen = hasattr(data, '__len__')
  message_template = "file saving {}" + (" num of all entries: {}" if haslen else "")
  message = message_template.format(filename, len(data) if haslen else 0)

  with Timer(message, quiet):

    fullfilename = os.path.join(data_dir, filename)

    if (1 == 1):

      async with aiofiles.open(fullfilename + ".gz.tmp", 'wb', 1024 * 1024) as afh:
        with io.BytesIO() as fh:    # TODO: compress directly during reading and without using intermediate buffer for async data
          with gzip.GzipFile(fileobj=fh, filename=filename, mode='wb', compresslevel=compresslevel) as gzip_file:
            pickle.dump(data, gzip_file)
            gzip_file.flush() # NB! necessary to prevent broken gz archives on random occasions (does not depend on input data)
          fh.flush()  # just in case
          buffer = bytes(fh.getbuffer())  # NB! conversion to bytes is necessary to avoid "BufferError: Existing exports of data: object cannot be re-sized"
          await afh.write(buffer)
        await afh.flush()

    else:   #/ if (1 == 0):

      with open(fullfilename + ".gz.tmp", 'wb', 1024 * 1024) as fh:
        with gzip.GzipFile(fileobj=fh, filename=filename, mode='wb', compresslevel=compresslevel) as gzip_file:
          pickle.dump(data, gzip_file)
          gzip_file.flush() # NB! necessary to prevent broken gz archives on random occasions (does not depend on input data)
        fh.flush()  # just in case

    #/ if (1 == 0):

    await rename_temp_file(fullfilename + ".gz", make_backup)

  #/ with Timer("file saving {}, num of all entries: {}".format(filename, len(cache))):

#/ def save_file(filename, data):


def prod(factors):

    return reduce(operator.mul, factors, 1)

#/ def prod(factors):


def transpose_lists(list_of_lists):

  return list(map(list, zip(*list_of_lists)))

#/ def transpose_lists(list_of_lists):


# https://stackoverflow.com/questions/10461531/merge-and-sum-of-two-dictionaries/
def sum_dicts_values_by_key(dicts):

    #result = Counter()
    #for curr_dict in dicts:
    #    result.update(curr_dict)
    #return dict(result)

    #result = defaultdict(np.float32)
    #for curr_dict in dicts:
    #    for key, value in curr_dict.items():
    #        result[key] += value
    #return dict(result)

    result = {}
    for curr_dict in dicts:
      for key, value in curr_dict.items():
        result[key] = result.get(key, 0) + value
    return result

#/ def sum_dicts_values_by_key(dicts):


# used for disabling multprocessing pool or progressbar
class BlackHoleObject(object):

  def __init__(self, *args, **kwargs):
    pass

  # context manager functionality requires this method to be explicitly implemented
  def __enter__(self):
    return self

  # context manager functionality requires this method to be explicitly implemented
  def __exit__(self, type, value, traceback):
    return

  def _blackHoleMethod(*args, **kwargs):
    return

  def __getattr__(self, attr):
    return self._blackHoleMethod

#/ class BlackHoleObject(object):


# https://stackoverflow.com/questions/64100160/numpy-split-array-into-chunks-of-equal-size-with-remainder
def split_arr_to_chunks_of_size(arr, size, axis=0):
  
  return np.split(arr, np.arange(size, len(arr), size), axis=axis)

#/ def split_arr_to_chunks_of_size(arr, size):


def split_list_to_chunks_of_size(lst, size):

  return [lst[offset : offset + size] for offset in range(0, len(lst), size)]

#/ def split_list_to_chunks_of_size(lst, size):


