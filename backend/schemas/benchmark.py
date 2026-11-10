from pydantic import Field
from backend.schemas.inference import Configuration, ModelInput, StrictModel

class BenchmarkConfiguration(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    configuration: Configuration

class BenchmarkInput(ModelInput):
    name: str = Field('Benchmark', min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=32000)
    configurations: list[BenchmarkConfiguration] = Field(min_length=1, max_length=8)
    warmups: int = Field(1, ge=0, le=3)
    repeats: int = Field(3, ge=1, le=10)
