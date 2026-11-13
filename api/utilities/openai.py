from enum import Enum


class OpenAIEngines(Enum):
    def __new__(cls, value: str, name: str, description: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.name = name
        obj.description = description
        return obj

    @property
    def __str__(self) -> str:
        return self._value_

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

    def __str__(self) -> str:
        return str(self._value_)

    GPT_5_6_LUNA = (
        "gpt-5.6-luna",
        "GPT 5.6 Luna",
        "Small, low-cost model",
    )
