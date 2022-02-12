# -*- coding: utf-8 -*-

#
# Author: Roland Pihlakas, 2021 - 2022
#
# roland@simplify.ee
#


print("Loading modules ...")
import os
print(os.path.basename(__file__))
import sys
import traceback

from syncer import sync

from typing import Union, List, Tuple, Dict

import json
import pickle
import json_tricks
import gzip

import requests
from urllib.parse import urlparse

from configparser import ConfigParser


from SemanticSearchUtilities import debugging, is_dev_machine, safeprint, decompress_with_limit, request_with_content_limit, print_exception, match_beginning, compresslevel
from SemanticSearchClientUtilities import is_remote_server, do_request, get_job_result




if (is_dev_machine or True) and False:
  semanticsearch_api_server_url = 'http://127.0.0.1:' + str(9102 if is_dev_machine else 9102) + '/'
else:
  semanticsearch_api_server_url = 'https://semanticsearch.groupassembler.org/'



def configure(url):
  global semanticsearch_api_server_url

  semanticsearch_api_server_url = url

#/ def configure(url):


def get_use_json_response(use_json_response, semanticsearch_api_server_url):

  if use_json_response is None:
    use_json_response = is_remote_server(semanticsearch_api_server_url)

  return use_json_response

#/ def get_use_json_response(use_json_response, semanticsearch_api_server_url):


def get_token(token, model_name):

  if not token:
    config = ConfigParser()
    config.read('semanticsearch_client.ini')
    token = config.get("tokens", "token_" + str(model_name))

  return token

#/ def get_token(token, model_name):


# TODO!!! example parameters for all requests


async def get_index_data(model_name: str, enable_log = False, token = "", use_json_response: bool = None):

  try:

    use_json_response = get_use_json_response(use_json_response, semanticsearch_api_server_url)
    token = get_token(token, model_name)


    request = {
      "index":                      str(model_name),
      "token":                      str(token),
      "use_json_response":          bool(use_json_response),
    }


    result = await do_request(semanticsearch_api_server_url, request, request_path = "get_index_data", timeout_sec = 60, result_field_name = "index_data", enable_log = enable_log, use_json_response = use_json_response)
    return result

  except Exception as ex:

    print_exception(ex)
    safeprint(traceback.format_exc())

    return None

#/ def get_index_data(model_name):


async def index(model_name: str, data: List[str], language = "en", normalize_vectors = True, calculate_nonempty_texts = False, stop_phrases = [], concepts_and_abbreviations = {}, allow_long_text_chunking = True, clear_index = False, enable_log = False, token = "", use_json_response: bool = None, wait_for_job_completion = False):

  try:

    use_json_response = get_use_json_response(use_json_response, semanticsearch_api_server_url)
    token = get_token(token, model_name)
    

    request = {
      "index":                      str(model_name),
      "token":                      str(token),
      "use_json_response":          bool(use_json_response),

      "language":                   str(language),
      "texts":                      [str(x) for x in data],
      "clear_index":                bool(clear_index),
      # "ids":                      [int(x) for x in list(ids)] if ids else None,
      "normalize_vectors":          bool(normalize_vectors),
      "calculate_nonempty_texts":   bool(calculate_nonempty_texts),
      "stop_phrases":               [str(x) for x in list(stop_phrases)] if stop_phrases else [],
      "concepts_and_abbreviations": ({
                                      str(abbreviation): str(expansion) 
                                      for (abbreviation, expansion) 
                                      in dict(concepts_and_abbreviations).items()
                                    }
                                    if concepts_and_abbreviations else {}),
      "allow_long_text_chunking":   bool(allow_long_text_chunking),
    }


    job_id = await do_request(semanticsearch_api_server_url, request, request_path = "index", timeout_sec = 60, result_field_name = "job_id", enable_log = enable_log, use_json_response = use_json_response)

    result = await get_job_result(semanticsearch_api_server_url, model_name, job_id, wait_for_job_completion, enable_log = enable_log, token = token, use_json_response = use_json_response)

    return result

  except Exception as ex:

    print_exception(ex)
    safeprint(traceback.format_exc())

    return None

#/ def index():


async def encode_text(index_data: Union[str, Tuple], texts: List[str], enable_log = False, token = "", use_json_response: bool = None) -> Tuple[List, List]:   # returns list of vectors and list of text indexes each vector belongs to (some text might have been split up into multiple vectors)

  try:

    use_json_response = get_use_json_response(use_json_response, semanticsearch_api_server_url)
    
    if isinstance(index_data, str):
      model_name = index_data
    else:
      (model_name, _index, _normalization, _data, _language, _allow_long_text_chunking, _ids, _combined_encodings, _nonempty_profiles, _vector_cache, _empty_text_vector_chunks, _td_idf_dict) = index_data

    token = get_token(token, model_name)


    request = {
      "index":                      str(model_name),
      "token":                      str(token),
      "use_json_response":          bool(use_json_response),

      "texts":                      [str(x) for x in texts],
    }


    result = await do_request(semanticsearch_api_server_url, request, request_path = "encode_text", timeout_sec = 60, result_field_name = "encoding", enable_log = enable_log, use_json_response = use_json_response)
    return result

  except Exception as ex:

    print_exception(ex)
    safeprint(traceback.format_exc())

    return None

#/ def encode_text():


async def search(index_data: Union[str, Tuple], query: str, negative_query: str = None, num_results = 10, randomise_equal_results = True, fix_top_n_before_diversify: int = 1, diversify_top_n: int = None, do_full_search: bool = None, exclude_ids = [], distance_aggregator = "inv_sum_distance_aggregator", use_chunk_movers_aggregation = True, include_td_idf_results: Union[bool, int] = True, enable_log = False, token = "", use_json_response: bool = None) -> Tuple[List[str], List[float], List[float]]:

  try:

    use_json_response = get_use_json_response(use_json_response, semanticsearch_api_server_url)
    
    if isinstance(index_data, str):
      model_name = index_data
    else:
      (model_name, _index, _normalization, _data, _language, _allow_long_text_chunking, _ids, _combined_encodings, _nonempty_profiles, _vector_cache, _empty_text_vector_chunks, _td_idf_dict) = index_data
    
    token = get_token(token, model_name)


    request = {
      "index":                          str(model_name),
      "token":                          str(token),
      "use_json_response":              bool(use_json_response),

      "text":                           str(query),
      "negative_text":                  str(negative_query) if negative_query is not None else None,
      "num_results":                    int(num_results),
      "fix_top_n_before_diversify":     int(fix_top_n_before_diversify) if fix_top_n_before_diversify is not None else None,  # default behaviour is to diversify half of the top results
      "diversify_top_n":                int(diversify_top_n) if diversify_top_n is not None else None,
      "randomise_equal_results":        bool(randomise_equal_results),
      "do_full_search":                 bool(do_full_search) if do_full_search is not None else None,
      "exclude_ids":                    [int(x) for x in list(exclude_ids)] if exclude_ids else None,
      "distance_aggregator":            distance_aggregator 
                                          if isinstance(distance_aggregator, str) 
                                          else str(distance_aggregator.__name__),  # function name
      "use_chunk_movers_aggregation":   bool(use_chunk_movers_aggregation),                                      
      "include_td_idf_results":         bool(include_td_idf_results)   # when True then half of the results are obtained using td-idf
                                          if isinstance(include_td_idf_results, bool) 
                                          else int(include_td_idf_results),
    }


    result = await do_request(semanticsearch_api_server_url, request, request_path = "search", timeout_sec = 10, result_field_name = "results", enable_log = enable_log, use_json_response = use_json_response)
    return result

  except Exception as ex:

    print_exception(ex)
    safeprint(traceback.format_exc())

    return None

#/ def search():


