from api.utilities import tokenizers
from enum import Enum
from transformers import PreTrainedTokenizerFast


class OpenAIEngines(Enum):
    def __new__(cls, value: str, name: str, description: str, tokenizer: PreTrainedTokenizerFast):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.name = name
        obj.description = description
        obj.tokenizer = tokenizer
        return obj

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value

    @property
    def tokenizer(self) -> PreTrainedTokenizerFast:
        return self._tokenizer

    @tokenizer.setter
    def tokenizer(self, value: PreTrainedTokenizerFast) -> None:
        self._tokenizer = value

    def __str__(self) -> str:
        return str(self._value_)

    DAVINCI = (
        "text-davinci-001",
        "Davinci 001",
        "Should only be used for Rob.",
        tokenizers.gpt2,
    )
    CURIE = (
        "text-curie-001",
        "Curie 001",
        "Should only be used for bot devs.",
        tokenizers.gpt2,
    )
    BABBAGE = (
        "text-babbage-001",
        "Babbage 001",
        "Should be used by everyone else.",
        tokenizers.gpt2,
    )
