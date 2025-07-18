class SpiderError(Exception):
    pass


class ResponseCodeError(SpiderError):
    pass


class ResponseTextError(SpiderError):
    pass
