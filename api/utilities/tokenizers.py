from enum import Enum
from transformers import GPT2TokenizerFast, GPTNeoXTokenizerFast

gpt2 = GPT2TokenizerFast.from_pretrained("gpt2")
gpt_neo_x = GPTNeoXTokenizerFast.from_pretrained("EleutherAI/gpt-neox-20b")
