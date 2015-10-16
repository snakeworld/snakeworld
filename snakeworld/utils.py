import json
import functools


json_dumps = functools.partial(json.dumps, separators=(',', ':'))
