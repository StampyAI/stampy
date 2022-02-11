# -*- coding: utf-8 -*-

#
# Author: Roland Pihlakas, 2021
#
# roland@simplify.ee
#


print("Loading modules ...")
import os
print(os.path.basename(__file__))
import sys
import traceback

from typing import Union, List, Tuple, Dict

import datetime
import json
import pickle
import json_tricks
import gzip

import requests
from urllib.parse import urlparse
import asyncio
import functools

from configparser import ConfigParser


from SemanticSearchUtilities import loop, debugging, is_dev_machine, safeprint, decompress_with_limit, request_with_content_limit, print_exception, match_beginning, compresslevel, transpose_lists




decompression_limit = 1 * 1024 * 1024 * 1024     # TODO: tune, config file



def is_remote_server(url):

  netloc = urlparse(url).netloc
  if match_beginning(netloc, ["127.0.0.1", "localhost"]):
    return False
  else:
    return True

#/ def is_remote_server(url):


def encode_request(request):

  return gzip.compress(json.dumps(request).encode("utf8", "ignore"), compresslevel) # JSON is a safer input format to parse in server and also easier to enable_log

#/ def encode_request(request):


def decode_result(serialized_result, use_json_response):

  decompressed = decompress_with_limit(serialized_result, decompression_limit)

  if use_json_response:   # many serialisers are unsecure since they allow arbitrary code execution OR do not support numpy. json_tricks supports numpy and does not allow code execution
    result = json_tricks.loads(decompressed.decode("utf8", "ignore"), preserve_order=False) # preserve_order=True is default, but we do not need OrderedDict return type here
  else:   # pickle supports numpy but allows arbitrary code execution
    result = pickle.loads(decompressed) 

  return result

#/ def decode_result(serialized_result, use_json_response):


def log_request(enable_log, request):

  if enable_log:
    safeprint(str(datetime.datetime.now()) + " : " + str(request))

#/ def log_request(enable_log, request):


def log_result(enable_log, result):

  if enable_log:
    safeprint(str(datetime.datetime.now()) + " : " + str(result))

#/ def log_result(enable_log, result):


def get_result_from_field(result, result_field_name):

  if result.get("success"):
    if result_field_name is None:
      return result
    else:
      return result[result_field_name]
  else:
    return None

#/ def get_result_from_field(result, result_field_name):


async def do_request(api_server_url: str, request, request_path, timeout_sec, result_field_name, enable_log, use_json_response):

  log_request(enable_log, request)
  request_json = encode_request(request)

  serialized_result = await request_with_content_limit(api_server_url + request_path, is_post=True, data=request_json, timeout_sec=timeout_sec, content_limit=decompression_limit)

  result = decode_result(serialized_result, use_json_response)      
  log_result(enable_log, result)

  return get_result_from_field(result, result_field_name)
  
#/ def do_request(request, enable_log):


async def ping_server(api_server_url: str) -> bool:

  try:

    # result = requests.get(api_server_url + "uptime", timeout=5).content.decode("utf8", "ignore")
    result = (await request_with_content_limit(api_server_url + "uptime", is_post=False, timeout_sec=5, content_limit=1000)).decode("utf8", "ignore")
  
    return result.strip() == "success"

  except Exception as ex:

    print_exception(ex)
    safeprint(traceback.format_exc())

    return False

#/ def ping_server():


async def poll_job(api_server_url: str, model_name: str, job_id: str, enable_log = False, token = "", use_json_response = None):

  try:

    use_json_response = get_use_json_response(use_json_response, api_server_url)
    token = get_token(token, model_name)


    request = {
      "index":                      str(model_name),
      "token":                      str(token),

      "job_id":                     str(job_id),
    }


    return await do_request(request, request_path = "poll_job", timeout_sec = 60, result_field_name = None, enable_log = enable_log, use_json_response = use_json_response)

  except Exception as ex:

    print_exception(ex)
    safeprint(traceback.format_exc())

    return None

#/ def poll_job(model_name, job_id):


async def get_job_result(api_server_url: str, model_name: str, job_id: str, wait_for_job_completion = True, enable_log = False, token = "", use_json_response = None):

  if wait_for_job_completion:

    use_json_response = get_use_json_response(use_json_response, api_server_url)
    token = get_token(token, model_name)
    

    status = "pending"

    while status == "pending" or status == "processing":

      asyncio.sleep(5)
      result = await poll_job(api_server_url, model_name, job_id, enable_log = enable_log, token = token, use_json_response = use_json_response)

      status = result["status"]

    #/ while status == "pending" or status == "processing":

    # NB! result will contain the whole shebang of status fields from the completed job

    return result

  #/ if wait_for_job_completion:

#/ def get_job_result():


