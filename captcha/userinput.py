from .base import BaseFunCaptchaResult
from proxy import ProxyConfig


class UserInputFunCaptchaGenrator:
    def generate(self, captcha_proxy: ProxyConfig = None) -> BaseFunCaptchaResult:
        token = input('Token: ')

        return BaseFunCaptchaResult(token)
