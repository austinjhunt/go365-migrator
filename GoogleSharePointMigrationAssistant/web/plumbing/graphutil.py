from ratelimit import sleep_and_retry, limits
from urllib3.exceptions import ProtocolError
from .constants import (
    MAX_GRAPH_REQUESTS_PER_MINUTE, ONE_MINUTE,
    GRAPH_SLEEP_RETRY_SECONDS
)
from .m365_util import get_token_from_cache
import requests
import time

class GraphUtil():
    """ Abstract class offering basic graph API http methods GET, POST, PUT 
    which parameterize the URLs and the data """
    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def graph_get(self, url: str = '', headers: dict = {}):
        response = None
        token = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        use_headers = headers if headers else {
                    'Authorization': f'Bearer {token["access_token"]}',
                    'Content-Type': 'application/json'
                }
        try:
            response = requests.get(
                url=url,
                headers=use_headers
            )
            response_data = response.json()
            msg = {
                'graph_get': {
                    'status_code': response.status_code,
                    'response_data': response_data,
                    'url': url
                }
            }
            if response.status_code not in [200, 201, 202]:
                self.error(msg)
                return None
            else:
                self.debug(msg)
        except requests.exceptions.ConnectTimeout as etimeout:
            self.error({'graph_get': {'TimeoutError': str(
                econnerror), 'url': url, 'sleeping_for': f'{GRAPH_SLEEP_RETRY_SECONDS}s'}})
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response_data = self.graph_get(url=url, headers=headers)
        except (
            requests.exceptions.ConnectionError,
            # handle Connection aborted, RemoteDisconnected
            # ref: https://github.com/urllib3/urllib3/issues/1327
            ProtocolError
        ) as econnerror:
            self.error({'graph_get': {'ConnectionErrorOrProtocolError': str(
                econnerror), 'url': url, 'sleeping_for': f'{GRAPH_SLEEP_RETRY_SECONDS}s'}})
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response_data = self.graph_get(url=url, headers=headers)
        return response_data

    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def graph_put(self, url: str = '', headers: dict = {}, data=None):
        response = None
        token = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        use_headers = headers if headers else {
                    'Authorization': f'Bearer {token["access_token"]}',
                    'Content-Type': 'application/json'
                }
        try:
            response = requests.put(
                url=url,
                headers=use_headers,
                data=data
            )
            response_data = response.json()
            msg = {
                'graph_put': {
                    'status_code': response.status_code,
                    'response_data': response_data,
                    'url': url,
                    'payload': data
                }
            }
            if response.status_code not in [200, 201, 202]:
                self.error(msg)
                return None
            else:
                self.debug(msg)
        except requests.exceptions.ConnectTimeout as etimeout:
            self.error({'graph_put': {'TimeoutError': str(
                etimeout), 'url': url, 'sleeping_for': f'{GRAPH_SLEEP_RETRY_SECONDS}s'}})
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response_data = self.graph_put(url=url, headers=headers, data=data)
        except (
            requests.exceptions.ConnectionError,
            # handle Connection aborted, RemoteDisconnected
            # ref: https://github.com/urllib3/urllib3/issues/1327
            ProtocolError
        ) as econnerror:
            self.error({'graph_put': {'ConnectionErrorOrProtocolError': str(
                econnerror), 'url': url, 'sleeping_for': f'{GRAPH_SLEEP_RETRY_SECONDS}s'}})
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response_data= self.graph_put(url=url, headers=headers, data=data)
        return response_data

    @sleep_and_retry
    @limits(calls=MAX_GRAPH_REQUESTS_PER_MINUTE, period=ONE_MINUTE)
    def graph_post(self, url: str = '', headers: dict = {}, data = None):
        response = None
        token = get_token_from_cache(m365_token_cache=self.m365_token_cache)
        use_headers = headers if headers else {
                    'Authorization': f'Bearer {token["access_token"]}',
                    'Content-Type': 'application/json'
                }
        try:
            response = requests.post(
                url=url,
                headers=use_headers,
                data=data
            )
            response_data = response.json()
            msg = {
                'graph_post': {
                    'status_code': response.status_code,
                    'response_data': response_data,
                    'url': url,
                    'payload': data
                }
            }
            if response.status_code not in [200, 201, 202]:
                self.error(msg)
                return None
            else:
                self.debug(msg)
        except requests.exceptions.ConnectTimeout as etimeout:
            self.error({'graph_post': {'TimeoutError': str(
                etimeout), 'url': url, 'sleeping_for': f'{GRAPH_SLEEP_RETRY_SECONDS}s'}})
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response_data = self.graph_post(url=url, headers=headers, data=data)
        except (
            requests.exceptions.ConnectionError,
            # handle Connection aborted, RemoteDisconnected
            # ref: https://github.com/urllib3/urllib3/issues/1327
            ProtocolError
        ) as econnerror:
            self.error({'graph_post': {'ConnectionErrorOrProtocolError': str(
                econnerror), 'url': url, 'sleeping_for': f'{GRAPH_SLEEP_RETRY_SECONDS}s'}})
            time.sleep(GRAPH_SLEEP_RETRY_SECONDS)
            response_data = self.graph_post(url=url, headers=headers, data=data)
        return response_data