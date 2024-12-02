import requests
from proxy import ProxyConfig
from typing import Protocol, Optional
from dataclasses import dataclass


class BaseFunCaptchaResult:
    @property
    def token(self):
        return self._token

    def __init__(self, token: str):
        self._token: str = token


class BaseFunCaptchaGenerator(Protocol):
    def generate(self, captcha_proxy: ProxyConfig = None) -> BaseFunCaptchaResult:
        pass


class BaseHCaptchaResult:
    @property
    def response_key(self):
        return self._response_key

    @property
    def request_key(self):
        return self._request_key

    @property
    def user_agent(self):
        return self._user_agent

    def __init__(self, response_key: str, request_key: str, user_agent: str):
        self._response_key: str = response_key
        self._request_key: str = request_key
        self._user_agent: str = user_agent

    def generate_user_agent_header(self) -> requests.sessions.CaseInsensitiveDict:
        session_headers = requests.sessions.CaseInsensitiveDict()
        session_headers['User-Agent'] = self.user_agent

        return session_headers


class BaseHCaptchaGenerator(Protocol):
    def generate(self, site_key: str, captcha_proxy: ProxyConfig = None, invisible: bool = False) -> BaseHCaptchaResult:
        pass


@dataclass(frozen=True)
class BaseImageCaptchaResult:
    text: str
    """Resolved text of the captcha"""

    task_id: Optional[str] = None
    """(Optional) Task ID related to the submitted job/task."""

    confidence: Optional[str] = None
    """(Optional) Confidence of the result."""


class BaseImageCaptchaGenerator(Protocol):

    def generate_from_binary(self, image_binary: bytes) -> BaseImageCaptchaResult:
        """
        The implementation must accept a captcha image as a binary, solves the captcha and return the captcha result as
        :class:`BaseImageCaptchaResult` object.

        :param image_binary: Binary of the image.
        :return: Result of the captcha.
        """
        pass
