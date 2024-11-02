from distutils.core import setup

setup(
    name='captcha-provider',
    version='0.0.0',
    packages=[
        'captcha'
    ],
    url='https://github.com/OnlyCookie/captcha-provider',
    license='',
    author='Chung Seng',
    author_email='comtactme@chungseng.dev',
    description='Simple captcha solver with that support multiple sources.',
    install_requires=[
        'requests >= 2.29.0,<3',
        'proxy-provider @ git+ssh://git@github.com/OnlyCookie/proxy-provider.git@feature-2captcha-improvement'
    ]
)
