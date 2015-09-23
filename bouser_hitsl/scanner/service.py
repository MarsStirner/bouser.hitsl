# -*- coding: utf-8 -*-
import json
import time
import os

from twisted.application.service import Service
from twisted.internet import defer
from twisted.internet.error import ConnectionClosed, ProcessExitedAlready
from twisted.internet.protocol import ProcessProtocol
from twisted.protocols.basic import LineReceiver
from twisted.python import failure
from zope.interface import implementer

from bouser.excs import SerializableBaseException
from bouser.helpers.plugin_helpers import BouserPlugin
from bouser.helpers.twisted_helpers import chain_deferreds
from .interfaces import IScanService

__author__ = 'viruzzz-kun'


class ScannerBusy(SerializableBaseException):
    def __init__(self, dev_name):
        self.message = u'Сканер %s занят' % dev_name


class ScannerFailure(SerializableBaseException):
    def __init__(self, dev_name):
        self.message = u'Не удалось получить изображение от сканера %s' % dev_name


class ScanProtocol(ProcessProtocol, LineReceiver):
    delimiter = '\n'

    def __init__(self, dev_name, consumer, options):
        self.process = None
        self.name = dev_name
        self.scan_options = options
        self.deferred = defer.Deferred(lambda w: self.stop())
        self.consumer = consumer

    def outReceived(self, data):
        return self.dataReceived(data)

    def lineReceived(self, line):
        print(line)
        if line.startswith('DATA'):
            self.setRawMode()

    def rawDataReceived(self, data):
        self.consumer.write(data)

    def processEnded(self, reason):
        """
        :type reason: twisted.python.failure.Failure
        :param reason:
        :return:
        """
        if self.deferred.called:
            return
        if self.line_mode:
            self.deferred.errback(failure.Failure(ScannerFailure(self.name)))
        elif isinstance(reason.value, ConnectionClosed):
            self.deferred.callback(self.name)
        else:
            self.deferred.errback(reason)

    def start(self):
        from twisted.internet import reactor
        self.process = reactor.spawnProcess(
            self,
            'python',
            ('python',
             os.path.join(os.path.dirname(__file__), 'worker_scan.py'),
             self.name,
             self.scan_options['format'],
             self.scan_options['resolution'],
             self.scan_options['mode']),
            env=None,
            childFDs={0: 'w', 1: 'r', 2: 2}
        )
        self.process.disconnecting = False

    def stop(self):
        try:
            self.process.signalProcess('INT')
        except (ProcessExitedAlready, OSError):
            pass


class GetDevicesProtocol(ProcessProtocol):
    def __init__(self):
        self.process = None
        self.deferred = defer.Deferred()
        self.buffer = []

    def outReceived(self, data):
        self.buffer.append(data)

    def processEnded(self, reason):
        """
        :type reason: twisted.python.failure.Failure
        :param reason:
        :return:
        """
        if self.deferred.called:
            return
        if isinstance(reason.value, ConnectionClosed):
            result = []
            try:
                buf = b''.join(self.buffer)
                result = json.loads(buf)
            except ValueError:
                pass
            finally:
                self.deferred.callback(result)
        else:
            self.deferred.errback(reason)

    def start(self):
        print('sane_get_devices forced')
        from twisted.internet import reactor
        self.process = reactor.spawnProcess(
            self,
            'python',
            ('python', os.path.join(os.path.dirname(__file__), 'worker_gd.py')),
            env=None,
            childFDs={0: 'w', 1: 'r', 2: 2}
        )
        self.process.disconnecting = False


@implementer(IScanService)
class ScanService(Service, BouserPlugin):
    signal_name = 'bouser.scanner'
    cache_timeout = 300

    def __init__(self):
        self.scan_currents = {}
        self.scan_list_deferred = None
        self.cached_scan_list = ([], 0)

    def getImage(self, dev_name, consumer, options):
        from twisted.internet import reactor

        if self.scan_currents.get(dev_name):
            return defer.fail(ScannerBusy(dev_name))

        protocol = ScanProtocol(dev_name, consumer, options)
        self.scan_currents[dev_name] = protocol

        def _cb(result):
            self.scan_currents.pop(dev_name)
            return result

        protocol.deferred.addBoth(_cb)
        reactor.callLater(0, protocol.start)
        return protocol.deferred

    def getScanners(self, force=False):
        if self.scan_list_deferred:
            d = defer.Deferred()
            chain_deferreds(self.scan_list_deferred, d)
            return d

        if not force:
            l, deadline = self.cached_scan_list
            if deadline > time.time():
                return defer.succeed(l)

        def _cb(result):
            self.scan_list_deferred = None
            self.cached_scan_list = (result, time.time() + self.cache_timeout)
            return result

        def _eb(failure):
            self.scan_list_deferred = None
            self.cached_scan_list = ([], 0)
            return failure

        protocol = GetDevicesProtocol()
        protocol.deferred.addCallbacks(_cb, _eb)
        self.scan_list_deferred = protocol.deferred
        protocol.start()
        d = defer.Deferred()
        chain_deferreds(protocol.deferred, d)
        return d

