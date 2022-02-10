# -*- coding: utf-8 -*-

#
# Author: Roland Pihlakas, 2017 - 2021
#
# roland@simplify.ee
#


import string
import json
import re
import unicodedata
# import nltk


from SemanticSearchUtilities import Timer, safeprint




# nltk.download("stopwords")  # update data

eng_min_token_len = 2   # TODO: tune
eng_min_lemma_len = 2   # TODO: tune
  

punctuation = set(string.punctuation)
punctuation.add("§")    # paragraph mark

punctuation.add("±")    # +- mark

punctuation.add("«")    # left quote
punctuation.add("»")    # right quote
punctuation.add("„")    # left quote
punctuation.add("“")    # right quote
#punctuation.add('"')    # double quote
#punctuation.add("'")    # single quote

#punctuation.add(":")    # colon
#punctuation.add(";")    # semicolon
#punctuation.add(",")    # comma
#punctuation.add(".")    # dot
#punctuation.add("!")    # exclamation mark
#punctuation.add("?")    # question mark

#punctuation.add("(")    # left bracket
#punctuation.add(")")    # right bracket
#punctuation.add("[")    # left bracket
#punctuation.add("]")    # right bracket
#punctuation.add("{")    # left bracket
#punctuation.add("}")    # right bracket

def is_punctuation(token):
  global punctuation

  for letter in token:
    if not letter in punctuation:
      return False

  return True

#/ def is_punctuation(token):


def isnumeric(token):

  if token[:1] == "-":    # NB! Python does not consider strings of negative numbers as numerics
    return token[1:].isnumeric()
  else:
    return token.isnumeric()

#/ def isnumeric(token):


nonalpha_re = re.compile(r'[^a-z ]+')

def remove_nonalpha(text):

  result = nonalpha_re.sub(" ", text.replace("'", ""))  # NB replace apostrophe with empty string

  return result

#/ def remove_nonalpha(text):


# https://stackoverflow.com/questions/4324790/removing-control-characters-from-a-string-in-python
# NB! this also removes newlines
def remove_control_characters(s):
  return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


nltk_eng_inited = False
doing_nltk_eng_init = False
eng_stopwords = set()
eng_lemmatizer = None   # will be assigned when nltk is loaded
wordnet_tagDict = {}

def init_nltk_eng(log=True, load_lemmatizer=False):
  global doing_nltk_eng_init, nltk_eng_inited, eng_stopwords, eng_lemmatizer, wordnet_tagDict

  if nltk_eng_inited:
    return

  if doing_nltk_eng_init:
    return


  doing_nltk_eng_init = True

  try:
    if log:
      safeprint("Loading NLTK eng")


    if load_lemmatizer:
      from nltk import WordNetLemmatizer
      from nltk import pos_tag

    from nltk import wordpunct_tokenize
    from nltk.corpus import wordnet
    import nltk.corpus
    # from nltk.corpus import stopwords

    from many_stop_words import get_stop_words

    import stop_words
    import stopwords


    # stopwords common in all languages
    common_forbidden_words = set(['', # NB!
                    'ii', 'iii', 'iv', 'vi', 'vii', 'viii',
                    'ix', 'xi', 'xii', 'xiii',
                    'xiv', 'xv', 'xvi', 'xvii', 'xviii', 'ixx', 'xx'
                  ])  # TODO!! all roman numerals


    eng_stopwords0 = eng_stopwords

    # https://stackoverflow.com/questions/5486337/how-to-remove-stop-words-using-nltk-or-python/5486535
    eng_stopwords1 = set(nltk.corpus.stopwords.words('english'))    #About 150 stopwords
    eng_stopwords2 = set(get_stop_words('en'))         #About 900 stopwords

    eng_stopwords3 = [
      "the", "a", "an", "thanks", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december", "utc", "gmt", "ok", "please", "be", "hi", "hey" 
    ]

    eng_stopwords4 = set(stop_words.get_stop_words("english"))    #About 175 stopwords
    eng_stopwords5 = set(stopwords.get_stopwords("english"))    #About 175 stopwords


    with open('stopwords-en-master/stopwords-en.json', 'r', 1024 * 1024, encoding='utf-8') as data_file:
      eng_stopwords6 = json.load(data_file)

    with open('stopwords-json-master/dist/en.json', 'r', 1024 * 1024, encoding='utf-8') as data_file:
      eng_stopwords7 = json.load(data_file)

    #async with aiofiles.open('stopwords-en-master/stopwords-en.json', 'r', 1024 * 1024, encoding='utf-8') as afh:
    #  data = await afh.read()
    #  with io.BytesIO(data) as fh:
    #    eng_stopwords6 = json.load(fh)

    #async with aiofiles.open('stopwords-json-master/dist/en.json', 'r', 1024 * 1024, encoding='utf-8') as afh:
    #  data = await afh.read()
    #  with io.BytesIO(data) as fh:
    #    eng_stopwords7 = json.load(fh)



    eng_stopwords = set()

    for word in common_forbidden_words:
      eng_stopwords.add(word)  # NB! keep nonalpha

    for word0 in eng_stopwords0:
      eng_stopwords.add(remove_nonalpha(word0)) # TODO perform this replacement in lemmatiser too

    for word1 in eng_stopwords1:
      eng_stopwords.add(remove_nonalpha(word1))

    for word2 in eng_stopwords2:
      eng_stopwords.add(remove_nonalpha(word2))

    for word3 in eng_stopwords3:
      eng_stopwords.add(remove_nonalpha(word3))

    for word4 in eng_stopwords4:
      eng_stopwords.add(remove_nonalpha(word4))

    for word5 in eng_stopwords5:
      eng_stopwords.add(remove_nonalpha(word5))

    for word6 in eng_stopwords6:
      eng_stopwords.add(remove_nonalpha(word6.lower()))

    for word7 in eng_stopwords7:
      eng_stopwords.add(remove_nonalpha(word7.lower()))


    # from nltk.corpus import wordnet; safeprint(wordnet._FILEMAP);

    if load_lemmatizer:
      wordnet_tagDict = {
            'N': wordnet.NOUN,
            'V': wordnet.VERB,
            'R': wordnet.ADV,
            'J': wordnet.ADJ
          }

      eng_lemmatizer = WordNetLemmatizer()


    # run analysis once so that all lazy fields are also associated by the time this function ends
    filter_words_eng("Loading and running NLTK for the first time.")


    nltk_eng_inited = True      # NB! set the flag only when the nltk loading succeeded before timeout occurred

    if log:
      safeprint("Done loading NLTK eng")

  finally:

    doing_nltk_eng_init = False

#/ def init_nltk_eng():


stop_phrases_re = None
stop_phrases_re_input = None

def filter_words_eng(line, lemmatize = False, stop_phrases = []):
  global stop_phrases_re, stop_phrases_re_input


  init_nltk_eng(load_lemmatizer=False)
  from nltk import wordpunct_tokenize

  if lemmatize:
    from nltk import pos_tag


  line = remove_urls_and_numbers(line)  # NB!


  if len(stop_phrases) > 0:

    line = " " + line + " " # lookbehind and lookahead require some character to detect word boundary

    if stop_phrases_re_input != stop_phrases:
      stop_phrases_re = re.compile(r'(?<=[^\w])(' + "|".join(re.escape(stop_phrase) for stop_phrase in stop_phrases) + r')(?=[^\w])', re.IGNORECASE)
      stop_phrases_re_input = stop_phrases

    line = stop_phrases_re.sub("", line)
    line = line[1:-1]   # remove temporarily added whitespace

  #/ if len(stop_phrases) > 0:


  if not lemmatize:

    for token in wordpunct_tokenize(line): # TODO!: cache tokenizations for speed?

      token = remove_control_characters(token.lower())

      # TODO!: detect and keep dates?
      if (token not in eng_stopwords) \
        and len(token) >= eng_min_token_len \
        and not is_punctuation(token) \
        and not isnumeric(token):

        yield token

    #/ for token in wordpunct_tokenize(line):

  else:   #/ if not lemmatize:

    for token, tag in pos_tag(wordpunct_tokenize(line)): # TODO!: cache tokenizations + lemmatizations for speed?

      token = remove_control_characters(token.lower())

      # TODO!: detect and keep dates?
      if (token not in eng_stopwords) \
        and len(token) >= eng_min_token_len \
        and not is_punctuation(token) \
        and not isnumeric(token):

        for lemma in eng_lemmatize(token, tag):
          if len(lemma) >= eng_min_lemma_len:     # NB! sanitize
            yield lemma

    #/ for token, tag in pos_tag(wordpunct_tokenize(line)):

  #/ if lemmatize:

#/ def filter_words_eng(line):


# TODO!!! cache the lemmatisations
def eng_lemmatize(token, treebank_tag):
  global eng_min_token_len, eng_stopwords, punctuation

  from nltk.corpus import wordnet


  # https://stackoverflow.com/questions/15586721/wordnet-lemmatization-and-pos-tagging-in-python
  tag = wordnet_tagDict.get(treebank_tag[0], wordnet.NOUN)

  
  lemmas = set()

  lemmatized = eng_lemmatizer.lemmatize(token, tag)

  token = lemmatized.lower()

  if (token not in eng_stopwords \
    and len(token) >= eng_min_token_len and not is_punctuation(token) and not isnumeric(token)):

    yield token
    
  return lemmas

#/ def eng_lemmatize(token, tag):


left_brac_or_punc = r'[.,:;!?({<\[\/\-]'  # NB! / or - IS included here
right_brac_or_punc = r'[.,:;!?)}>\]]'     # NB! / or - IS NOT included here

# https://stackoverflow.com/questions/17327765/exclude-characters-from-a-character-class
alpha_except_left_brac_or_punc = r'((?!' + left_brac_or_punc + ')\S)'
alpha_except_right_brac_or_punc = r'((?!' + right_brac_or_punc + ')\S)'

alphas_except_left_brac_or_punc_at_start = alpha_except_left_brac_or_punc + r'\S*'
alphas_except_right_brac_or_puncs_at_end = r'\S*' + alpha_except_right_brac_or_punc

space_or_left_brac_or_punc = r'(' + left_brac_or_punc + r'|[^\w])'
space_or_right_brac_or_punc = r'(' + right_brac_or_punc + r'|[^\w])'

lookbehind_space_or_left_brac_or_punc = r'(?<=' + space_or_left_brac_or_punc + r')'
lookahead_space_or_right_brac_or_punc = r'(?=' + space_or_right_brac_or_punc + r')'

http_re     = re.compile(
  lookbehind_space_or_left_brac_or_punc 
  + r'(http|https|ftp)://' + alphas_except_right_brac_or_puncs_at_end                       # https://whatever
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)
url_like_re = re.compile(
  lookbehind_space_or_left_brac_or_punc    
  + alphas_except_left_brac_or_punc_at_start + r'[.]\S+/' + alphas_except_right_brac_or_puncs_at_end   # domain.xyz/folder 
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)
email_re    = re.compile(
  lookbehind_space_or_left_brac_or_punc    
  + alphas_except_left_brac_or_punc_at_start + r'@\S+[.]' + alphas_except_right_brac_or_puncs_at_end   # email@domain.xyz  
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)
domain_re   = re.compile(
  lookbehind_space_or_left_brac_or_punc 
  + alphas_except_left_brac_or_punc_at_start + r'[.](com|org|net|edu|gov|int|mil|me|io|ai)' # domain.com
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)
www_re      = re.compile(
  lookbehind_space_or_left_brac_or_punc 
  + r'www[.]' + alphas_except_right_brac_or_puncs_at_end                                    # www.domain.xyz   
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)
at_gmail_re = re.compile(
  lookbehind_space_or_left_brac_or_punc 
  + r'at\s+(gmail|hotmail)(\s+dot\s+com)?'                                                # at gmail, at hotmail
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)

percent_dollar_eur_pound_re  = re.compile(
  lookbehind_space_or_left_brac_or_punc 
  + r'[0-9,.\']*[0-9]\s*(%|\$|usd|€|eur|£)'                                               # 12 %, 12 $, 12 eur 
  + lookahead_space_or_right_brac_or_punc,
  re.IGNORECASE
)

def remove_urls_and_numbers(line):

  line = " " + line + " " # lookbehind and lookahead require some character to detect word boundary


  line = http_re.sub("", line)
  line = url_like_re.sub("", line)
  line = email_re.sub("", line)
  line = domain_re.sub("", line)
  line = www_re.sub("", line)
  line = at_gmail_re.sub("", line)

  line = percent_dollar_eur_pound_re.sub("", line)


  line = line[1:-1]   # remove temporarily added space

  return line

#/ def remove_urls_and_numbers(line):


url_re = re.compile("(" 
                      + http_re.pattern 
                      + "|" + www_re.pattern 
                      + "|" + url_like_re.pattern 
                      + "|" + domain_re.pattern 
                      + ")",
                      re.IGNORECASE)

def escape_urls_for_discord(line):

  line = " " + line + " " # lookbehind and lookahead require some character to detect word boundary

  line = url_re.sub(r'<\1>', line)

  line = line[1:-1]   # remove temporarily added space

  return line

#/ def escape_urls_for_discord(line):
