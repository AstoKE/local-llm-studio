from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Options(StrictModel):
    temperature: float = Field(0.8, ge=0, le=2)
    top_k: int = Field(40, ge=0, le=1000)
    top_p: float = Field(0.9, ge=0, le=1)
    min_p: float = Field(0, ge=0, le=1)
    repeat_penalty: float = Field(1.1, ge=0, le=3)
    num_ctx: int = Field(4096, ge=128, le=1048576)
    num_predict: int = Field(512, ge=1, le=32768)
    seed: int = Field(-1, ge=-1, le=2147483647)
    stop: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(default_factory=list, max_length=16)

class Configuration(StrictModel):
    options: Options = Field(default_factory=Options)
    system_prompt: str = Field('', max_length=32000)
    keep_alive: int = Field(300, ge=0, le=86400)

class ConversationInput(StrictModel):
    title: str = Field('New conversation', min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')
    configuration: Configuration = Field(default_factory=Configuration)

class ChatInput(StrictModel):
    model: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')
    content: str = Field('', max_length=100000)
    conversation_id: int | None = Field(None, gt=0)
    edit_message_id: int | None = Field(None, gt=0)
    regenerate: bool = False
    configuration: Configuration = Field(default_factory=Configuration)
    history: list['HistoryMessage'] = Field(default_factory=list, max_length=200)

class HistoryMessage(StrictModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=100000)

class ModelInput(StrictModel):
    model: str = Field(min_length=1, max_length=200, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$')

class PresetInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    configuration: Configuration

class ConversationSnapshot(ConversationInput):
    messages: list[HistoryMessage] = Field(min_length=1, max_length=200)
