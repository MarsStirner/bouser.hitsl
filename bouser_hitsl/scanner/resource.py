# -*- coding: utf-8 -*-
from twisted.internet import defer
from twisted.internet.defer import CancelledError
from twisted.python.components import registerAdapter
from twisted.web.resource import Resource, IResource
from twisted.web.server import NOT_DONE_YET

from bouser.helpers.plugin_helpers import BouserPlugin, Dependency
from .interfaces import IScanService
from bouser.utils import api_method, get_args, as_json

__author__ = 'viruzzz-kun'


class ScanResource(Resource, BouserPlugin):
    signal_name = 'bouser.scanner.resource'
    isLeaf = 1

    web = Dependency('bouser.web')
    service = Dependency('bouser.scanner')

    def render(self, request):
        """
        :type request: bouser.web.request.BouserRequest
        :param request:
        :return:
        """
        if self.web.crossdomain(request):
            return ''

        request.postpath = filter(None, request.postpath)
        ppl = len(request.postpath)
        if ppl == 0:
            return 'I am Scanner'

        elif ppl == 1:
            leaf = request.postpath[0]
            if leaf == 'list':
                request.setHeader('Content-Type', 'application/json; charset=utf-8')
                return self.scanners(request)
            elif leaf == 'scan':
                request.setHeader('Content-Type', 'image/png')
                return self.scan(request)
        request.setResponseCode(404)
        return ''

    @api_method
    @defer.inlineCallbacks
    def scanners(self, request):
        force = bool(request.args.get('force', [0])[0])
        result = yield self.service.getScanners(force)
        defer.returnValue(result)

    def scan(self, request):
        j = get_args(request)
        name = j.get('name')
        options = {
            'format': j.get('format', 'png') or 'png',
            'resolution': str(j.get('resolution') or 300),
            'mode': j.get('mode') or 'Color'
        }
        if not name:
            request.setHeader('Content-Type', 'text/plain;charset=utf-8')
            request.setResponseCode(400)
            return 'Name should be set'
        deferred = self.service.getImage(name, request, options)
        finished = request.notifyFinish()

        def _finished(_):
            print('Request cancelled')
            deferred.cancel()

        def _cb(name):
            print('Process Finished: %s' % name)
            if not request._disconnected:
                request.finish()

        def _eb(failure):
            if not isinstance(failure.value, CancelledError):
                request.setResponseCode(500, 'Scanning error')
                request.setHeader('Content-Type', 'text/json;charset=utf-8')
                request.write(as_json(failure.value))
                if not request._disconnected:
                    request.finish()

        deferred.addCallbacks(_cb, _eb)
        finished.addErrback(_finished)
        return NOT_DONE_YET

    @web.on
    def web_boot(self, sender):
        sender.root_resource.putChild('scan', self)


registerAdapter(ScanResource, IScanService, IResource)


def make(config):
    return ScanResource()
