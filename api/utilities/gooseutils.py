from enum import Enum


class GooseAIEngines(Enum):
    def __new__(cls, value: str, name: str, description: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.name = name
        obj.description = description
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

    @name.setter
    def description(self, value: str) -> None:
        self._description = value

    def __str__(self) -> str:
        return str(self.value)

    GPT_20B = (
        "gpt-neo-20b",
        "GPT-NeoX 20B",
        "20B parameter EleutherAI model trained on the Pile, using the NeoX framework.",
    )
    GPT_6B = (
        "gpt-j-6b",
        "GPT-J 6B",
        "6B parameter EleutherAI model trained on the Pile, using the Mesh Transformer JAX framework.",
    )
    GPT_2_7B = (
        "gpt-neo-2-7b",
        "GPT-Neo 2.7B",
        "20B parameter EleutherAI model trained on the Pile, using the NeoX framework.",
    )
    GPT_1_3B = (
        "gpt-neo-1-3b",
        "GPT-Neo 1.3B",
        "1.3B parameter EleutherAI model trained on the Pile, using the Neo framework.",
    )
    GPT_125M = (
        "gpt-neo-125m",
        "GPT-Neo 125M",
        "125M parameter EleutherAI model trained on the Pile, using the Neo framework.",
    )
    FAIRSEQ_13B = (
        "fairseq-13b",
        "Fairseq 13B",
        "13B parameter Facebook Mixture of Experts model trained on RoBERTa and CC100 subset data.",
    )
    FAIRSEQ_6_7B = (
        "fairseq-6-7b",
        "Fairseq 6.7B",
        "6.7B parameter Facebook Mixture of Experts model trained on RoBERTa and CC100 subset data.",
    )
    FAIRSEQ_2_7B = (
        "fairseq-2-7b",
        "Fairseq 2.6B",
        "2.7B parameter Facebook Mixture of Experts model trained on RoBERTa and CC100 subset data.",
    )
    FAIRSEQ_1_3B = (
        "fairseq-1-3b",
        "Fairseq 1.3B",
        "1.3B parameter Facebook Mixture of Experts model trained on RoBERTa and CC100 subset data.",
    )
    FAIRSEQ_125M = (
        "fairseq-125m",
        "Fairseq 125M",
        "125M parameter Facebook Mixture of Experts model trained on RoBERTa and CC100 subset data.",
    )
