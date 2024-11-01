import json
import time
import requests
from . import twocaptchaconstants as const
from .base import BaseFunCaptchaResult, BaseHCaptchaResult
from typing import Optional, TypeVar
from proxy import ProxyConfig
from abc import ABC, abstractmethod

TwoCaptchaResultT = TypeVar('TwoCaptchaResultT', bound='TwoCaptchaResult')


class TwoCaptchaException(Exception):
    pass


class TwoCaptchaRequestProcessing(TwoCaptchaException):
    pass


class TwoCaptchaRequestFailed(TwoCaptchaException):
    pass


def generate_request_proxy_dict(proxy_config: ProxyConfig) -> dict:
    new_dict = dict()
    # TODO: Improve this to include other protocols
    new_dict[const.TWO_CAPTCHA_TASK_KEY_PROXY_TYPE] = 'http'

    new_dict[const.TWO_CAPTCHA_TASK_KEY_PROXY_ADDRESS] = proxy_config.hostname
    new_dict[const.TWO_CAPTCHA_TASK_KEY_PROXY_PORT] = proxy_config.port

    if proxy_config.has_username():
        new_dict[const.TWO_CAPTCHA_TASK_KEY_PROXY_USERNAME] = proxy_config.username

    if proxy_config.has_password():
        new_dict[const.TWO_CAPTCHA_TASK_KEY_PROXY_PASSWORD] = proxy_config.password

    return new_dict


class RequestHandler:
    def __init__(self, api_token: str):
        self.api_token: str = api_token

    def _create_base_request_body(self) -> dict:
        request_data = dict()
        request_data[const.TWO_CAPTCHA_REQUEST_KEY_API_TOKEN] = self.api_token

        return request_data

    def create_task(self, task_details: dict) -> int:
        """
        Creates a task on 2Captcha, and returns the task number. Does not wait for task to complete.
        :param task_details: Task configuration data
        :return: 2Captcha task number
        """
        request_data = self._create_base_request_body()
        request_data[const.TWO_CAPTCHA_REQUEST_KEY_TASK] = task_details

        response = requests.post(const.TWO_CAPTCHA_URL_CREATE_TASK, json=request_data)

        if response.status_code < 200 or response.status_code > 299:
            raise (TwoCaptchaRequestFailed(
                f'Create task request did not return 2XX code. Status code: {response.status_code}'))

        response_json = response.json()

        response_code = response_json[const.TWO_CAPTCHA_RESPONSE_KEY_ERROR_ID]

        if response_code != 0:
            print(json.dumps(response_json, sort_keys=True, indent=4))
            raise (TwoCaptchaRequestFailed(f'Error occurred while creating task. Error id: {response_code}'))

        return response_json[const.TWO_CAPTCHA_RESPONSE_KEY_TASK_ID]

    def get_result(self, task_id: int) -> dict:
        """
        Attempt to get result of a 2Captcha task. Raises exception if the task is still being processed or failed.

        :param task_id: 2Captcha task number
        :return: Solution JSON of the result.
        :except TwoCaptchaRequestFailed: Raised if the task failed
        :except TwoCaptchaRequestProcessing: Raised if the task is still being processed
        """
        request_data = self._create_base_request_body()
        request_data[const.TWO_CAPTCHA_REQUEST_KEY_TASK_ID] = task_id

        response = requests.post(const.TWO_CAPTCHA_URL_CHECK_RESULT, json=request_data)

        if response.status_code < 200 or response.status_code > 299:
            raise (TwoCaptchaException(
                f'Create task request did not return 2XX code. Status code: {response.status_code}'))

        response_json = response.json()

        response_code = response_json[const.TWO_CAPTCHA_RESPONSE_KEY_ERROR_ID]

        if response_code != 0:
            print(json.dumps(response_json, sort_keys=True, indent=4))
            raise (TwoCaptchaRequestFailed(f'Error id: {response_code}'))

        status = response_json[const.TWO_CAPTCHA_RESPONSE_KEY_STATUS]

        if status == const.TWO_CAPTCHA_RESPONSE_STATUS_PROCESSING:
            raise (TwoCaptchaRequestProcessing(f'Request still processing. Task id: {task_id}'))

        return response_json.get(const.TWO_CAPTCHA_RESPONSE_KEY_SOLUTION)


class TwoCaptchaResult:
    def __init__(self, raw_solution: dict):
        self.raw_solution: dict = raw_solution


class TwoCaptchaGenerator(ABC):
    def __init__(self, request_handler: RequestHandler, website_url: str, max_auto_retry: int = 0):
        self.request_handler: RequestHandler = request_handler
        self.website_url: str = website_url
        self.auto_retry: int = max_auto_retry

        # TODO: Type should be provided by subclass. No need to be stored on superclass.
        self.type: Optional[str] = None

    @abstractmethod
    def _process_solution(self, solution: dict) -> TwoCaptchaResultT:
        pass

    def _generate_task_dict(self, additional_params: dict = None) -> dict:
        new_dict = dict()
        new_dict[const.TWO_CAPTCHA_TASK_KEY_CAPTCHA_TYPE] = self.type
        new_dict[const.TWO_CAPTCHA_TASK_KEY_WEBSITE_URL] = self.website_url

        if additional_params is not None:
            new_dict.update(additional_params)

        return new_dict

    def _get_solution(self, additional_params: dict = None) -> TwoCaptchaResultT:
        # TODO: Better retry handling
        solution = None

        while solution is None:
            task_id = self.request_handler.create_task(self._generate_task_dict(additional_params))
            print(f'Task created. Id: {task_id}')

            while True:
                try:
                    solution = self.request_handler.get_result(task_id)
                    break

                except TwoCaptchaRequestProcessing:
                    print(f'Request "{task_id}" is still being processed. Will retry in 3 seconds.')
                    time.sleep(3)
                    continue

                except TwoCaptchaRequestFailed as e:
                    print(f'{e}')
                    break

            # TODO: Implement auto retry

        return self._process_solution(solution)


class TwoCapchaFunCaptchaResult(BaseFunCaptchaResult, TwoCaptchaResult):
    def __init__(self, raw_solution: dict):
        token: str = raw_solution[const.TWO_CAPTCHA_RESPONSE_FUN_CAPTCHA_TOKEN]

        BaseFunCaptchaResult.__init__(self, token)
        TwoCaptchaResult.__init__(self, raw_solution)


class TwoCapchaFunCaptchaGenerator(TwoCaptchaGenerator):
    def __init__(self, request_handler: RequestHandler, website_url: str, captcha_public_key: str,
                 user_agent: str = None, captcha_subdomain: str = None):
        super().__init__(request_handler, website_url)
        self.captcha_public_key: str = captcha_public_key
        self.user_agent: Optional[str] = user_agent
        self.captcha_subdomain: Optional[str] = captcha_subdomain

    def _process_solution(self, solution: dict) -> TwoCapchaFunCaptchaResult:
        return TwoCapchaFunCaptchaResult(solution)

    def generate(self, captcha_proxy: ProxyConfig = None) -> BaseFunCaptchaResult:
        if captcha_proxy is None:
            self.type = const.TWO_CAPTCHA_TASK_TYPE_FUN_CAPTCHA
        else:
            self.type = const.TWO_CAPTCHA_TASK_TYPE_FUN_CAPTCHA_PROXY

        additional_params = dict()

        additional_params[const.TWO_CAPTCHA_TASK_FUN_CAPTCHA_PUBLIC_KEY] = self.captcha_public_key

        if self.captcha_subdomain is not None:
            additional_params[const.TWO_CAPTCHA_TASK_FUN_CAPTCHA_SUBDOMAIN] = self.captcha_subdomain

        if self.user_agent is not None:
            additional_params[const.TWO_CAPTCHA_TASK_FUN_CAPTCHA_USER_AGENT] = self.user_agent

        if captcha_proxy is not None:
            additional_params.update(generate_request_proxy_dict(captcha_proxy))

        return self._get_solution(additional_params)


class TwoCapchaHCaptchaResult(BaseHCaptchaResult, TwoCaptchaResult):
    def __init__(self, raw_solution):
        response_key: str = raw_solution[const.TWO_CAPTCHA_RESPONSE_H_CAPTCHA_RESPONSE_KEY]
        request_key: str = raw_solution[const.TWO_CAPTCHA_RESPONSE_H_CAPTCHA_REQUEST_KEY]
        user_agent: str = raw_solution[const.TWO_CAPTCHA_RESPONSE_H_CAPTCHA_USER_AGENT]

        BaseHCaptchaResult.__init__(self, response_key, request_key, user_agent)
        TwoCaptchaResult.__init__(self, raw_solution)


class TwoCapchaHCaptchaGenerator(TwoCaptchaGenerator):
    def __init__(self, request_handler: RequestHandler, website_url: str, site_key: str):
        super().__init__(request_handler, website_url)
        self.site_key = site_key

    def _process_solution(self, solution: dict) -> TwoCapchaHCaptchaResult:
        return TwoCapchaHCaptchaResult(solution)

    def generate(self, captcha_proxy: ProxyConfig = None, invisible: bool = False) -> BaseHCaptchaResult:
        if captcha_proxy is None:
            self.type = const.TWO_CAPTCHA_TASK_TYPE_H_CAPTCHA
        else:
            self.type = const.TWO_CAPTCHA_TASK_TYPE_H_CAPTCHA_PROXY

        additional_params = dict()

        additional_params[const.TWO_CAPTCHA_TASK_H_CAPTCHA_SITE_KEY] = self.site_key

        if invisible is True:
            additional_params[const.TWO_CAPTCHA_TASK_H_CAPTCHA_INVISIBLE] = True

        if captcha_proxy is not None:
            additional_params.update(generate_request_proxy_dict(captcha_proxy))

        return self._get_solution(additional_params)
