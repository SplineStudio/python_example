from services.response import JsonResponse

import json


def validate_body(body=()):
    def decorate(func):
        def wrapper(*arg, **kwarg):
            try:
                try:
                    keys = arg[0].body.keys()
                except AttributeError:
                    keys = json.loads(arg[0].body.keys())
                for i in body:
                    if i not in keys:
                        return JsonResponse(error='{} - request.body.field.NotFound'.format(i))
                return func(*arg, **kwarg)
            except AssertionError as e:
                return JsonResponse(error=e.__str__())
        return wrapper
    return decorate
