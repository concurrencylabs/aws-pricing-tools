import json
import os



class ValidationError(Exception):
    """Exception raised for errors in the input.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


class NoDataFoundError(Exception):
    """Exception raised when no data could be found for a particular set of inputs

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message

