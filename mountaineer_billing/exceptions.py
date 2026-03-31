class ResourceExhausted(Exception):
    """
    ResourceExhausted is a plain exception that is raised when a resource is exhausted. It isn't
    decorated as an APIException, since APIException's can't be serialized as part of the
    workflow payload.

    """

    pass
