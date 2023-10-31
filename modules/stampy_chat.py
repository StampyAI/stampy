"""
Queries chat.stampy.ai with the user's question.

"""

import json
import re
from collections import deque, defaultdict
from typing import Iterable, List, Dict, Any
from uuid import uuid4

import requests
from structlog import get_logger

from modules.module import Module, Response
from servicemodules.serviceConstants import italicise
from utilities.serviceutils import ServiceChannel, ServiceMessage
from utilities.utilities import Utilities

log = get_logger()
utils = Utilities.get_instance()


LOG_MAX_MESSAGES = 15  # don't store more than X messages back
DATA_HEADER = 'data: '

STAMPY_CHAT_ENDPOINT = "https://chat.stampy.ai:8443/chat"
NLP_SEARCH_ENDPOINT = "https://stampy-nlp-t6p37v2uia-uw.a.run.app/"

STAMPY_ANSWER_MIN_SCORE = 0.75
STAMPY_CHAT_MIN_SCORE = 0.4


def stream_lines(stream: Iterable):
    line = ''
    for item in stream:
        item = item.decode('utf8')
        line += item
        if '\n' in line:
            lines = line.split('\n')
            line = lines[-1]
            for l in lines[:-1]:
                yield l
    yield line


def parse_data_items(stream: Iterable):
    for item in stream:
        if item.strip().startswith(DATA_HEADER):
            yield json.loads(item.split(DATA_HEADER)[1])


def top_nlp_search(query: str) -> Dict[str, Any]:
    resp = requests.get(NLP_SEARCH_ENDPOINT + '/api/search', params={'query': query, 'status': 'all'})
    if not resp:
        return {}

    items = resp.json()
    if not items:
        return {}
    return items[0]


def chunk_text(text: str, chunk_limit=2000, delimiter='.'):
    chunk = ''
    for sentence in text.split(delimiter):
        if len(chunk + sentence) + 1 >= chunk_limit and chunk and sentence:
            yield chunk
            chunk = sentence + delimiter
        elif sentence:
            chunk += sentence + delimiter
    yield chunk


def filter_citations(text, citations):
    used_citations = re.findall(r'\[([a-z],? ?)*?\]', text)
    return [c for c in citations if c.get('reference') in used_citations]


class StampyChat(Module):

    def __init__(self):
        self.utils = Utilities.get_instance()
        self._messages: dict[ServiceChannel, deque[ServiceMessage]] = defaultdict(lambda: deque(maxlen=LOG_MAX_MESSAGES))
        self.session_id = str(uuid4())
        super().__init__()

    @property
    def class_name(self):
        return 'stampy_chat'

    def format_message(self, message: ServiceMessage):
        return {
            'content': message.content,
            'role': 'assistant' if self.utils.stampy_is_author(message) else 'user',
        }

    def stream_chat_response(self, query: str, history: List[ServiceMessage]):
        return parse_data_items(stream_lines(requests.post(STAMPY_CHAT_ENDPOINT, stream=True, json={
            'query': query,
            'history': [self.format_message(m) for m in history],
            'sessionId': self.session_id,
            'settings': {'mode': 'discord'},
        })))

    def get_chat_response(self, query: str, history: List[ServiceMessage]):
        response = {'citations': [], 'content': '', 'followups': []}
        for item in self.stream_chat_response(query, history):
            if item.get('state') == 'citations':
                response['citations'] += item.get('citations', [])
            elif item.get('state') == 'streaming':
                response['content'] += item.get('content', '')
            elif item.get('state') == 'followups':
                response['followups'] += item.get('followups', [])
        response['citations'] = filter_citations(response['content'], response['citations'])
        return response

    async def query(self, query: str, history: List[ServiceMessage], message: ServiceMessage):
        log.info('calling %s', query)
        chat_response = self.get_chat_response(query, history)
        content_chunks = list(chunk_text(chat_response['content']))
        citations = [f'[{c["reference"]}] - {c["title"]} ({c["url"]})' for c in chat_response['citations'] if c.get('reference')]
        if citations:
            citations = ['Citations: \n' + '\n'.join(citations)]
        followups = []
        if follows := chat_response['followups']:
            followups = [
                'Checkout these articles for more info: \n' + '\n'.join(
                    f'{f["text"]} - https://aisafety.info?state={f["pageid"]}' for f in follows
                )
            ]

        log.info('response: %s', content_chunks + citations + followups)
        return Response(
            confidence=10,
            text=[italicise(text, message) for text in content_chunks + citations + followups],
            why='This is what the chat bot returned'
        )

    def _add_message(self, message: ServiceMessage) -> deque[ServiceMessage]:
        self._messages[message.channel].append(message)
        return self._messages[message.channel]

    def process_message(self, message: ServiceMessage) -> Response:
        history = self._add_message(message)
        history.append(message)

        query = message.content
        nlp = top_nlp_search(query)
        if nlp.get('score', 0) > STAMPY_ANSWER_MIN_SCORE and nlp.get('status') == 'Live on site':
            return Response(confidence=5, text=f'Check out {nlp.get("url")} ({nlp.get("title")})')
        if nlp.get('score', 0) > STAMPY_CHAT_MIN_SCORE:
            return Response(confidence=6, callback=self.query, args=[query, history, message])
        return Response()

    def process_message_from_stampy(self, message: ServiceMessage):
        self._add_message(message)
