# -*- coding: utf-8 -*-
from zope.interface import Interface, Attribute, classImplements


class IExternalCasService(Interface):
    db = Attribute('db', 'Database service')
    expiry_time = Attribute('expiry_time', 'Token time to live')
    clean_period = Attribute('clean_period', 'How often service should check for expired tokens')
    check_duplicate_tokens = Attribute(
        'check_duplicate_tokens',
        'Should the service raise exception if user already took a token?')

    def acquire_token(self, login, password):
        """
        Acquire auth token for user login
        :param login:
        :param password:
        :return:
        """

    def release_token(self, token, ext_cookie):
        """
        Release previously acquired token
        :param token:
        :return:
        """

    def check_token(self, token,  prolong, ext_cookie):
        """
        Check whether auth token is valid
        :param token:
        :param prolong:
        :param ext_cookie:
        :return:
        """

    def prolong_token(self, token, ext_cookie):
        """
        Make token live longer
        :param token:
        :return:
        """
