import requests
import time
from . import capsolverconstants as const
from .base import BaseHCaptchaResult
from proxy import ProxyConfig
from abc import ABC, abstractmethod
from typing import Optional, TypeVar

CapSolverResultT = TypeVar('CapSolverResultT', bound='CapSolverResul')


class CapSolverException(Exception):
    pass


class CapSolverRequestProcessing(CapSolverException):
    pass


class CapSolverRequestFailed(CapSolverException):
    pass


def generate_request_proxy_dict(proxy_config: ProxyConfig) -> dict:
    new_dict = dict()
    # TODO: Improve this to include other protocols
    new_dict[const.CAP_SOLVER_TASK_KEY_PROXY_TYPE] = 'http'

    new_dict[const.CAP_SOLVER_TASK_KEY_PROXY_ADDRESS] = proxy_config.hostname
    new_dict[const.CAP_SOLVER_TASK_KEY_PROXY_PORT] = proxy_config.port

    if proxy_config.has_username():
        new_dict[const.CAP_SOLVER_TASK_KEY_PROXY_USERNAME] = proxy_config.username

    if proxy_config.has_password():
        new_dict[const.CAP_SOLVER_TASK_KEY_PROXY_PASSWORD] = proxy_config.password

    return new_dict


class CapSolverResult:
    def __init__(self, raw_solution: dict):
        self.raw_solution = raw_solution


class CapSolverGenerator(ABC):
    def __init__(self, api_key: str, website_url: str, max_auto_retry: int = 0):
        self.api_key: str = api_key
        self.website_url: str = website_url
        self.max_auto_retry: int = max_auto_retry

    def _create_task(self, task_body: dict) -> str:
        if const.CAP_SOLVER_TASK_KEY_WEBSITE_URL not in task_body:
            task_body[const.CAP_SOLVER_TASK_KEY_WEBSITE_URL] = self.website_url

        request_data = dict()
        request_data[const.CAP_SOLVER_REQUEST_KEY_API_TOKEN] = self.api_key
        request_data[const.CAP_SOLVER_REQUEST_KEY_TASK] = task_body

        response = requests.post(const.CAP_SOLVER_URL_CREATE_TASK, json=request_data)

        if (response.status_code < 200 or response.status_code > 299) and response.status_code != 400:
            raise (CapSolverRequestFailed(
                f'Create task request did not return 2XX code. Status code: {response.status_code}'))

        response_json: dict = response.json()
        # print(json.dumps(response.json(), sort_keys=True, indent=4))
        response_id = response_json[const.CAP_SOLVER_RESPONSE_KEY_ERROR_ID]

        if response_id != 0:
            error_code = response_json[const.CAP_SOLVER_RESPONSE_KEY_ERROR_CODE]
            raise (CapSolverRequestFailed(f'Task create did not return error id of 0. Error code: {error_code}'))

        return response_json[const.CAP_SOLVER_REQUEST_KEY_TASK_ID]

    def _get_result(self, task_id: str) -> dict:
        request_data = dict()
        request_data[const.CAP_SOLVER_REQUEST_KEY_API_TOKEN] = self.api_key
        request_data[const.CAP_SOLVER_REQUEST_KEY_TASK_ID] = task_id

        response = requests.post(const.CAP_SOLVER_URL_CHECK_RESULT, json=request_data)

        if (response.status_code < 200 or response.status_code > 299) and response.status_code != 400:
            raise (CapSolverRequestFailed(
                f'Create task request did not return 2XX code. Status code: {response.status_code}'))

        response_json: dict = response.json()
        # print(json.dumps(response.json(), sort_keys=True, indent=4))
        response_id = response_json[const.CAP_SOLVER_RESPONSE_KEY_ERROR_ID]

        if response_id != 0:
            error_code = response_json[const.CAP_SOLVER_RESPONSE_KEY_ERROR_CODE]
            raise (CapSolverRequestFailed(f'Task did not return error id of 0. Error code: {error_code}'))

        if response_json.get(const.CAP_SOLVER_RESPONSE_KEY_STATUS) != const.CAP_SOLVER_RESPONSE_STATUS_READY:
            raise (CapSolverRequestProcessing(f'Request still processing. Task id: {task_id}'))

        return response_json.get(const.CAP_SOLVER_RESPONSE_KEY_SOLUTION)

    @abstractmethod
    def _process_solution(self, raw_solution: dict) -> CapSolverResult:
        pass

    def _get_solution(self, task_body: dict) -> CapSolverResultT:
        # TODO: Better retry handling
        solution: Optional[dict] = None

        while solution is None:
            task_id = self._create_task(task_body)
            print(f'Task created. Id: {task_id}')

            while True:
                try:
                    solution = self._get_result(task_id)
                    break

                except CapSolverRequestProcessing:
                    print(f'Request "{task_id}" is still being processed. Will retry in 3 seconds.')
                    time.sleep(2)
                    continue

                except CapSolverRequestFailed as e:
                    print(f'Request for task "{task_id} failed. Reason: {e}')
                    break

            # TODO: Implement auto retry

        return self._process_solution(solution)


class CapSolverHCaptchaResult(BaseHCaptchaResult, CapSolverResult):
    def __init__(self, raw_solution: dict):
        response_key: str = raw_solution[const.CAP_SOLVER_RESPONSE_H_CAPTCHA_RESPONSE_KEY]
        request_key: str = raw_solution[const.CAP_SOLVER_RESPONSE_H_CAPTCHA_REQUEST_KEY]
        user_agent: str = raw_solution[const.CAP_SOLVER_RESPONSE_H_CAPTCHA_USER_AGENT]

        BaseHCaptchaResult.__init__(self, response_key, request_key, user_agent)
        CapSolverResult.__init__(self, raw_solution)


class CapSolverHCaptchaGenerator(CapSolverGenerator):
    def __init__(self, api_key: str, website_url: str, max_auto_retry: int = 0):
        super().__init__(api_key, website_url, max_auto_retry=max_auto_retry)
    
    def _process_solution(self, raw_solution: dict) -> CapSolverResult:
        return CapSolverHCaptchaResult(raw_solution)

    def generate(self, site_key: str, captcha_proxy: ProxyConfig = None, invisible: bool = False) -> BaseHCaptchaResult:
        captcha_type = const.CAP_SOLVER_TASK_TYPE_H_CAPTCHA
        task_body = dict()

        task_body[const.CAP_SOLVER_TASK_H_CAPTCHA_SITE_KEY] = site_key
        
        if captcha_proxy is not None:
            captcha_type = const.CAP_SOLVER_TASK_TYPE_H_CAPTCHA_PROXY
            task_body.update(generate_request_proxy_dict(captcha_proxy))

        if invisible is True:
            task_body[const.CAP_SOLVER_TASK_H_CAPTCHA_INVISIBLE] = True

        task_body[const.CAP_SOLVER_TASK_KEY_CAPTCHA_TYPE] = captcha_type

        return self._get_solution(task_body)
