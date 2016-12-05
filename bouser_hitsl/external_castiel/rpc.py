# -*- coding: utf-8 -*-

import time

from twisted.internet import defer
from twisted.web.resource import IResource, Resource
from zope.interface import implementer

from bouser.helpers.plugin_helpers import BouserPlugin, Dependency
from bouser.utils import api_method


@implementer(IResource)
class ExternalCastielApiResource(Resource, BouserPlugin):
    isLeaf = True

    service = Dependency('bouser.castiel')
    web = Dependency('bouser.web')

    @api_method
    def render(self, request):
        """
        :type request: bouser.web.request.BouserRequest
        :param request:
        :return:
        """
        self.web.crossdomain(request, allow_credentials=True)

        request.postpath = filter(None, request.postpath)
        ppl = len(request.postpath)
        if ppl == 0:
            return 'I am External Castiel, angel of God'

        elif ppl == 1:
            leaf = request.postpath[0]
            if leaf == 'acquire':
                return self.acquire_token(request)

            elif leaf == 'release':
                return self.release_token(request)

            elif leaf == 'check':
                return self.check_token(request)

            elif leaf == 'prolong':
                return self.prolong_token(request)

            elif leaf == 'valid':
                return self.is_valid_credentials(request)

            elif leaf == 'get_user_id':
                return self.get_user_id(request)

            elif leaf == 'active_users_count':
                return self.get_active_users_count(request)

        request.setResponseCode(404)
        return '404 Not Found'

    @defer.inlineCallbacks
    def acquire_token(self, request):
        """
        Acquire auth token for login / password pair
        :param request:
        :return:
        """
        login = request.all_args['login']
        password = request.all_args['password']
        ato = yield self.service.acquire_token(login, password)
        defer.returnValue({
            'success': True,
            'token': ato.token.encode('hex'),
            'deadline': ato.deadline,
            'ttl': ato.deadline - time.time(),
            'user_id': ato.user_id,
        })

    @defer.inlineCallbacks
    def release_token(self, request):
        """
        Release previously acquired token
        :param request:
        :return:
        """
        hex_token = self.__get_hex_token(request)
        tgt_cookie = self.__get_tgt_cookie(request)
        result = yield self.service.release_token(hex_token.decode('hex'), tgt_cookie)
        defer.returnValue({
            'success': result,
            'token': hex_token,
        })

    @defer.inlineCallbacks
    def check_token(self, request):
        """
        Check whether auth token is valid
        :param request:
        :return:
        """
        prolong = request.all_args.get('prolong', False)
        hex_token = self.__get_hex_token(request)
        tgt_cookie = self.__get_tgt_cookie(request)
        user_id, deadline = yield self.service.check_token(hex_token.decode('hex'), prolong, tgt_cookie)
        defer.returnValue({
            'success': True,
            'user_id': user_id,
            'deadline': deadline,
            'ttl': deadline - time.time(),
            'token': hex_token,
        })

    @defer.inlineCallbacks
    def prolong_token(self, request):
        """
        Make token live longer
        :param request:
        :return:
        """
        hex_token = self.__get_hex_token(request)
        tgt_cookie = self.__get_tgt_cookie(request)
        success, deadline = yield self.service.prolong_token(hex_token.decode('hex'), tgt_cookie)
        defer.returnValue({
            'success': success,
            'deadline': deadline,
            'ttl': deadline - time.time(),
            'token': hex_token,
        })

    @defer.inlineCallbacks
    def get_active_users_count(self, request):
        """
        Get approximate number of active users
        :param request:
        :return:
        """
        count = yield self.service.get_active_users_count()
        defer.returnValue({
            'success': True,
            'count': count
        })

    @defer.inlineCallbacks
    def is_valid_credentials(self, request):
        """
        Check whether credentials are valid
        :param request:
        :return:
        """
        user = yield self.service.is_valid_credentials(request.all_args['login'], request.all_args['password'])
        defer.returnValue({
            'success': True,
            'user_id': user.user_id,
        })

    @defer.inlineCallbacks
    def get_user_id(self, request):
        hex_token = self.__get_hex_token(request)
        user_id = yield self.service.get_user_id(hex_token.decode('hex'))
        defer.returnValue({
            'success': True,
            'user_d': user_id,
        })

    def __get_hex_token(self, request):
        """
        :type request: bouser.web.request.BouserRequest
        :param request:
        :return:
        """
        hex_token = request.all_args.get('token', request.getCookie(self.service.cookie_name))
        if len(hex_token) != 32:
            raise Exception(u'Bad auth token')
        return hex_token

    def __get_tgt_cookie(self, request):
        tgt = request.all_args.get('ext_cookie', request.getCookie(self.service.ext_cookie_name)) or ''
        dont_check_tgt = request.all_args.get('dont_check_tgt', False)
        if dont_check_tgt:
            tgt = None
        return tgt
