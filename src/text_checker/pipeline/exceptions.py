class PipelineError(Exception):
    pass


class NonEnglishInputError(PipelineError):
    pass


class InputTooLongError(PipelineError):
    def __init__(self, length: int, limit: int) -> None:
        super().__init__(f"input length {length} exceeds limit {limit}")
        self.length = length
        self.limit = limit


class ProviderUnavailableError(PipelineError):
    pass
