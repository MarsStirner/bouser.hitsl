# -*- coding: utf-8 -*-
import time
import datetime
import os
import msgpack

from UserDict import UserDict
from xml.dom import minidom

from twisted.python.components import registerAdapter
from twisted.application.service import Service
from twisted.internet import defer
from twisted.internet.task import LoopingCall
from twisted.web.static import Data
from twisted.logger import Logger
from twisted.internet import reactor
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.python import log
from twisted.web.iweb import IBodyProducer

from zope.interface import implementer
from bouser.castiel.auxiliary import AuxiliaryResource
from bouser.castiel.mixin import RequestAuthMixin
from bouser.helpers.plugin_helpers import Dependency, BouserPlugin
from bouser.helpers import msgpack_helpers
from bouser.web.resource import AutoRedirectResource
from bouser.castiel.objects import AuthTokenObject
from bouser.castiel.exceptions import EExpiredToken
from bouser.castiel.interfaces import IAuthenticator
from bouser.bouser_simplelogs import SimplelogsLogObserver
from bouser_hitsl.external_castiel.interfaces import IExternalCasService
from bouser_hitsl.external_castiel.user_login import ExternalCastielLoginResource
from bouser_hitsl.external_castiel.rpc import ExternalCastielApiResource
from bouser_hitsl.external_castiel.exceptions import EUnsuccesfulCheckTGT


logger = Logger(
    observer=SimplelogsLogObserver(system_name='Coldstar.Castiel'),
    namespace="coldstar.castiel")


class CastielUserRegistry(UserDict, msgpack_helpers.Serializable):
    def __getstate__(self):
        return [
            (ato.token, ato.deadline, ato.object)
            for ato in self.data.itervalues()
        ]

    def __setstate__(self, state):
        self.data = dict(
            (token, AuthTokenObject(obj, deadline, token))
            for (token, deadline, obj) in state
        )


@implementer(IExternalCasService)
class ExternalCastielService(Service, RequestAuthMixin, BouserPlugin):
    signal_name = 'bouser.castiel'
    root = Dependency('bouser')
    auth = Dependency('bouser.auth')
    web = Dependency('bouser.web')

    def __init__(self, config):
        self.clean_period = config.get('clean_period', 10)
        self.expiry_time = config.get('expiry_time', 3600)
        self.cookie_name = config.get('cookie_name', 'authToken')
        self.cookie_domain = config.get('cookie_domain', '127.0.0.1')
        self.domain_map = config.get('domain_map', {})
        self.ext_cookie_name = config.get('ext_cookie_name', 'TGT-CAS')
        self.ext_url = str(config.get('ext_url', '127.0.0.1')).rstrip('/')
        self.self_url = str(config.get('self_url', '127.0.0.1')).rstrip('/')

        cas_resource = self.cas_resource = AutoRedirectResource()

        cas_resource.putChild('api', ExternalCastielApiResource())
        cas_resource.putChild('login', ExternalCastielLoginResource())
        cas_resource.putChild('aux', AuxiliaryResource())
        cas_resource.putChild('', Data('I am External Castiel, angel of God', 'text/html'))

        self.tokens = CastielUserRegistry()
        self.expired_cleaner = None

    def get_cookie_domain(self, source):
        return self.domain_map.get(source, self.cookie_domain)

    @web.on
    def web_boot(self, sender):
        """
        :type sender: bouser.web.service.WebService
        :param sender:
        :return:
        """
        sender.root_resource.putChild('cas', self.cas_resource)

    def validate_service_ticket(self, st, self_uri):
        """
        Make GET request to external cas /serviceValidate
        """
        url = '{0}/serviceValidate?service={1}&ticket={2}'.format(self.ext_url, self_uri, st)
        agent = Agent(reactor)
        d = agent.request(
            'GET',
            url,
            Headers({'User-Agent': ['Twisted Web Client']}),
        )

        def cbBody(body):
            try:
                user_login = minidom.parseString(body).getElementsByTagName('cas:user')[0].childNodes[0].data
                tgt = minidom.parseString(body).getElementsByTagName('cas:TGT')[0].childNodes[0].data
            except Exception, e:
                log.msg('Error: ticket validation failed: {0}'.format(body))
                logger.error(u'Неудачная попытка аутентификации через внешний CAS: {exc}\n\n{ext_url}\n{resp_body}',
                             exc=unicode(e),
                             ext_url=url,
                             resp_body=body.decode('utf-8'),
                             tags=['AUTH', 'EXT_CAS'])
                return False, None

            return True, {
                'user': user_login,
                'tgt': tgt
            }
        def cbResponse(response):
            if 200 < response.code or response.code > 299:
                log.msg('Error: {0} {1}'.format(
                    response.code, response.phrase).encode('utf-8'))
            resp_d = readBody(response)
            resp_d.addCallback(cbBody)
            return resp_d
        d.addCallback(cbResponse)

        def cbError(failure):
            log.msg('Error: {0}'.format(failure))
            return False, None
        d.addErrback(cbError)
        return d

    def acquire_token(self, login, password):
        def _cb(user):
            user_id = user.user_id
            ctime = time.time()

            token = os.urandom(16)

            deadline = ctime + self.expiry_time
            ato = self.tokens[token] = AuthTokenObject(user, deadline, token)  # (deadline, user_id)
            return ato

        d = self.auth.get_user(login, password)
        d.addCallback(_cb)
        return d

    @defer.inlineCallbacks
    def release_token(self, token, ext_cookie=None):
        if token in self.tokens:
            ato = self.tokens[token]
            del self.tokens[token]
            if ext_cookie is not None:
                yield self.logout_from_ext_cas(ext_cookie)
            defer.returnValue(True)
        else:
            raise EExpiredToken(token)

    def logout_from_ext_cas(self, tgt):
        """
        Make DELETE request to external cas /v1/tickets/<tgt>
        """
        url = '{0}/v1/tickets/{1}'.format(self.ext_url, tgt)
        agent = Agent(reactor)
        d = agent.request(
            'DELETE',
            url,
            Headers({'User-Agent': ['Twisted Web Client']}),
        )

        def cbBody(body):
            return body

        def cbResponse(response):
            if 200 < response.code or response.code > 299:
                log.msg('Error (logout_from_ext_cas): {0} {1}'.format(
                    response.code, response.phrase).encode('utf-8'))
            resp_d = readBody(response)
            resp_d.addCallback(cbBody)
            return resp_d

        d.addCallback(cbResponse)

        def cbError(failure):
            log.msg('Error (logout_from_ext_cas): {0}'.format(failure))
        d.addErrback(cbError)
        return d

    @defer.inlineCallbacks
    def check_token(self, token, prolong=False, ext_cookie=None):
        if token not in self.tokens:
            raise EExpiredToken(token)
        ato = self.tokens[token]
        if ato.deadline < time.time():
            raise EExpiredToken(token)

        if ext_cookie is not None:
            # проверять аутентификацию во внешнем CAS не чаще чем раз в 5 секунд
            self_uri = self.self_url
            if (time.time() - ato.modified) > 5:
                st = yield self.get_st_from_ext_cas(ext_cookie, self_uri)
                if not st.startswith('ST-'):
                    raise EUnsuccesfulCheckTGT('bad service ticket')
                ok, data = yield self.validate_service_ticket(st, self_uri)
                if not ok:
                    raise EUnsuccesfulCheckTGT('ticket validation failed')

        if prolong:
            # prolong without checking ext cas
            self.prolong_token(token, None)
        ato.modified = time.time()
        defer.returnValue((ato.user_id, ato.deadline))

    def get_st_from_ext_cas(self, tgt, self_uri):
        """
        Make POST request to external cas /v1/tickets/<tgt>
        """
        @implementer(IBodyProducer)
        class StringProducer(object):
            def __init__(self, uri):
                self.body = 'service={0}'.format(uri)
                self.length = len(self.body)
            def startProducing(self, consumer):
                consumer.write(self.body)
                return defer.succeed(None)
            def pauseProducing(self):
                pass
            def stopProducing(self):
                pass

        url = '{0}/v1/tickets/{1}'.format(self.ext_url, tgt)
        agent = Agent(reactor)
        d = agent.request(
            'POST',
            url,
            Headers({'User-Agent': ['Twisted Web Client']}),
            StringProducer(self_uri)
        )

        def cbBody(body):
            if not body.startswith('ST-'):
                log.msg('Error (get_st_from_ext_cas): bad service ticket {0}'.format(body))
                logger.error(u'Неудачная попытка проверки TGT через внешний CAS: {resp_body}',
                             resp_body=body.decode('utf-8'),
                             tags=['AUTH', 'EXT_CAS'])
            return body
        def cbResponse(response):
            if 200 < response.code or response.code > 299:
                log.msg('Error (get_st_from_ext_cas): {0} {1}'.format(
                    response.code, response.phrase).encode('utf-8'))
            resp_d = readBody(response)
            resp_d.addCallback(cbBody)
            return resp_d
        d.addCallback(cbResponse)

        def cbError(failure):
            log.msg('Error (get_st_from_ext_cas): {0}'.format(failure))
        d.addErrback(cbError)
        return d

    @defer.inlineCallbacks
    def prolong_token(self, token, ext_cookie=None):
        if token not in self.tokens:
            raise EExpiredToken(token)
        ato = self.tokens[token]

        if ext_cookie is not None:
            # проверять аутентификацию во внешнем CAS не чаще чем раз в 5 секунд
            self_uri = self.self_url
            if (time.time() - ato.modified) > 5:
                st = yield self.get_st_from_ext_cas(ext_cookie, self_uri)
                if not st.startswith('ST-'):
                    raise EUnsuccesfulCheckTGT('bad service ticket')
                ok, data = yield self.validate_service_ticket(st, self_uri)
                if not ok:
                    raise EUnsuccesfulCheckTGT('ticket validation failed')

        # just in case
        if token not in self.tokens:
            raise EExpiredToken(token)

        now = time.time()
        deadline = now + self.expiry_time
        ato = self.tokens[token]
        ato.deadline = deadline
        ato.modified = now
        defer.returnValue((True, deadline))

    def get_active_users_count(self):
        """Return number of tokens that were updated in last 3 minutes"""
        now = time.time()
        inactivity_duration = 180
        count = 0
        for token in self.tokens.itervalues():
            if now - token.modified < inactivity_duration:
                count += 1
        return defer.succeed(count)

    def is_valid_credentials(self, login, password):
        return self.auth.get_user(login, password)

    def _clean_expired(self):
        now = time.time()
        expired_users = []
        for token, ato in self.tokens.items():
            if ato.deadline < now:
                print "token", token.encode('hex'), "expired"
                expired_users.append(ato.object.get_description())
                del self.tokens[token]

        if expired_users:
            logger.info(u'Время жизни сессии истекло {dt:%d.%m.%Y %H:%M:%S} для следующих '
                        u'пользователей: {expired_users}',
                        expired_users=u', '.join(expired_users), dt=datetime.datetime.now(),
                        tags=['AUTH'])

    def get_user_id(self, token):
        """
        Returns users Auth Token Object
        :param token: Auth token
        :rtype: Deferred <AuthTokenObject | None>
        :return:
        """
        if token not in self.tokens:
            return defer.succeed(None)
        ato = self.tokens[token]
        if ato.deadline < time.time():
            return defer.succeed(None)
        return defer.succeed(ato.object.user_id)

    def startService(self):
        try:
            with open('tokens.msgpack', 'rb') as f:
                self.tokens = msgpack_helpers.load(f.read())
        except (IOError, OSError, msgpack.UnpackException, msgpack.UnpackValueError):
            pass
        self.expired_cleaner = LoopingCall(self._clean_expired)
        self.expired_cleaner.start(self.clean_period)
        Service.startService(self)

    def stopService(self):
        self.expired_cleaner.stop()
        with open('tokens.msgpack', 'wb') as f:
            f.write(msgpack_helpers.dump(self.tokens))
        Service.stopService(self)


registerAdapter(ExternalCastielService, IAuthenticator, IExternalCasService)