""" Utility methods used by Views """


from urllib.parse import quote
from string import ascii_letters, digits
import random


def get_random_value(length):
    return ''.join(random.choices(ascii_letters + digits, k=length))


def serialize(object):
    """ convert specified object to string of concatenated query parameters """
    return '&'.join([f'{quote(k)}={quote(v)}' for k, v in object.items()])
