#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import datetime
import urllib2

from twisted.internet import defer
from twisted.web.resource import IResource, Resource
from twisted.web.util import redirectTo
from twisted.logger import Logger
from twisted.python import log
from zope.interface import implementer

from bouser.helpers.plugin_helpers import BouserPlugin, Dependency
from bouser.castiel.exceptions import EExpiredToken, ETokenAlreadyAcquired, EInvalidCredentials, ENoToken
from bouser.web.interfaces import IWebSession
from bouser.bouser_simplelogs import SimplelogsLogObserver
from bouser_hitsl.external_castiel.exceptions import EUnsuccesfulCheckTGT


logger = Logger(
    observer=SimplelogsLogObserver(system_name='Coldstar.Castiel'),
    namespace="coldstar.castiel")


re_referrer_origin = re.compile(u'\Ahttps?://(?P<origin>[\.\w\d]+)(:\d+)?/.*', (re.U | re.I))


@implementer(IResource)
class ExternalCastielLoginResource(Resource, BouserPlugin):
    isLeaf = True

    service = Dependency('bouser.castiel')

    @defer.inlineCallbacks
    def render_GET(self, request):
        """
        :type request: bouser.web.request.BouserRequest
        :param request:
        :return:
        """
        def redirect_to_ext_cas():
            url = '{0}/login?service={1}'.format(self.service.ext_url, self_uri)
            rt = redirectTo(url, request)
            defer.returnValue(rt)

        token = request.getCookie(self.service.cookie_name)
        session = request.getSession()
        fm = IWebSession(session)
        if 'back' in request.args:
            fm.back = request.args['back'][0]
        elif not fm.back:
            fm.back = '/'

        self_uri = urllib2.quote(self.service.self_url + '/cas/login?back=' + fm.back)

        # 1) redirect from external cas which processed our login and issued service ticket
        # that need to be validated
        if 'ticket' in request.args:
            st = request.args['ticket'][0]
            ok, data = yield self.service.validate_service_ticket(st, self_uri)
            if not ok:
                redirect_to_ext_cas()
            else:
                # завершить аутентификацию, установив нашу куку
                try:
                    ato = yield self.service.acquire_token(data['user'], None)
                    logger.info(u'Пользователь {user_descr} аутентифицировался {dt:%d.%m.%Y %H:%M:%S}',
                                user_descr=ato.object.get_description(), dt=datetime.datetime.now(),
                                tags=['AUTH', 'EXT_CAS'])
                except EInvalidCredentials:
                    log.msg('Error login: cannot find user {0}'.format(data['user'].encode('utf-8')))
                    logger.warn(u'Неудачная попытка аутентификации по логину {login} {dt:%d.%m.%Y %H:%M:%S} '
                                u'(Не найден пользователь по логину)',
                                login=data['user'], dt=datetime.datetime.now(), tags=['AUTH', 'EXT_CAS'])
                    redirect_to_ext_cas()
                except ETokenAlreadyAcquired:
                    fm.back = None
                    redirect_to_ext_cas()
                else:
                    back = request.args.get('back', [fm.back])[0] or '/'
                    token_txt = ato.token.encode('hex')

                    domain = request.getHeader('Host').split(':', 1)[0]
                    uri = request.getHeader('Referer')
                    if uri:
                        match = re_referrer_origin.match(uri)
                        if match:
                            domain = match.groupdict()['origin']
                    cookie_domain = self.service.get_cookie_domain(domain)

                    request.addCookie(
                        str(self.service.cookie_name), token_txt, domain=str(cookie_domain),
                        path='/', comment='Castiel Auth Cookie'
                    )
                    request.addCookie(
                        str(self.service.ext_cookie_name), data['tgt'], domain=str(cookie_domain),
                        path='/', comment='External CAS TGT Cookie'
                    )

                    fm.back = None
                    defer.returnValue(redirectTo(back, request))

        # 2) user was redirected here from one of our systems;
        # need to check if _our_ current token is valid and if not - start login in external cas
        else:
            try:
                if token:
                    token = token.decode('hex')
                    tgt = request.getCookie(self.service.ext_cookie_name) or ''
                    yield self.service.check_token(token, False, tgt)
                else:
                    raise ENoToken()
            except (EExpiredToken, ENoToken, EUnsuccesfulCheckTGT):
                redirect_to_ext_cas()
            else:
                # _Our_ token is valid - just redirect back to our system
                back, fm.back = fm.back, None
                defer.returnValue(redirectTo(back, request))
