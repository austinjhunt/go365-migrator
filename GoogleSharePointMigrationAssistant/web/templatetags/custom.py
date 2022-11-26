from django import template 
import math 
from ..views.google import MIMETYPES
register = template.Library()
def prettify_mimetype(mimetype):
    if mimetype in MIMETYPES:
        return MIMETYPES[mimetype]
    return 'Unknown File Type'

def prettify_filesize(size_bytes):
    """ Convert size in bytes to size in friendly format. """
    if isinstance(size_bytes, str): 
        size_bytes = int(size_bytes)
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

register.filter('prettify_mimetype', prettify_mimetype)
register.filter('prettify_filesize', prettify_filesize)