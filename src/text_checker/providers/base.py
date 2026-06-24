from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerationRequest:
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float = 0.2
    max_tokens: int = 1024


@dataclass
class GenerationResponse:
    text: str
    tokens_in: int
    tokens_out: int
    model: str


class Provider(ABC):
    @abstractmethod
    async def generate(self, req: GenerationRequest) -> GenerationResponse: ...

    @abstractmethod
    async def health(self) -> bool: ...
