class FluxorBotException(Exception):
    """Base exception for Fluxor Bot"""

    pass


class SkipBotRun(FluxorBotException):
    """Exception to skip the current bot run"""

    pass
