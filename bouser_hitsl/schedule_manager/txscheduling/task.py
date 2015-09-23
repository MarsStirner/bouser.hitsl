from logging import getLogger

from twisted.python import reflect
from twisted.internet import defer
from twisted.python.failure import Failure

from .interfaces import ISchedule


log = getLogger('twisted.schedule.task')
if not log.handlers:
    from bouser.helpers.twisted_helpers import TwistedLoggerHandler
    handler = TwistedLoggerHandler()
    handler.system = 'TaskHandler'
    log.addHandler(handler)


class ScheduledCall(object):
    """Call a function repeatedly.

    If C{f} returns a deferred, rescheduling will not take place until the
    deferred has fired. The result value is ignored.

    @ivar f: The function to call.
    @ivar a: A tuple of arguments to pass the function.
    @ivar kw: A dictionary of keyword arguments to pass to the function.
    @ivar clock: A provider of
        L{twisted.internet.interfaces.IReactorTime}.  The default is
        L{twisted.internet.reactor}. Feel free to set this to
        something else, but it probably ought to be set *before*
        calling L{startService}.

    @type _lastTime: C{float}
    @ivar _lastTime: The time at which this instance most recently scheduled
        itself to run.
    """

    def __init__(self, f, *a, **kw):
        self.call = None
        self.running = False
        self.schedule = None
        self._lastTime = 0.0
        self.starttime = None
        self.f = f
        self.a = a
        self.kw = kw
        from twisted.internet import reactor

        self.clock = reactor

    def start(self, schedule, now=False):
        """Start running function based on the provided schedule.

        @param schedule: An object that provides or can be adapted to an
        ISchedule interface.
        """
        assert not self.running, "Tried to startService an already running ScheduledCall."
        self.schedule = ISchedule(schedule)
        try:
            self.running = True
            self.starttime = self.clock.seconds()
            self._lastTime = None

            self._reschedule(now=now)
        except Exception, e:
            log.error('Exception while starting %r: %s' % (self, str(e),))
            self.running = False
            if self.call is not None:
                try:
                    self.call.cancel()
                except:
                    pass
            raise e
        finally:
            log.debug('%r.startService(%r) started' % (self, schedule))

    def stop(self):
        """ Stop running function. """
        assert self.running, ("Tried to stop a ScheduledCall that was "
                              "not running.")
        self.running = False
        if self.call is not None:
            self.call.cancel()
            self.call = None

    def __call__(self):
        self.call = None
        d = defer.maybeDeferred(self.f, *self.a, **self.kw)
        d.addBoth(self._reschedule)

    def _reschedule(self, result=None, now=False):
        """ Schedule the next iteration of this scheduled call. """
        if self.call is None:
            delay = 0 if now else self.schedule.getDelayForNext()
            self._lastTime = self.clock.seconds() + delay
            self.call = self.clock.callLater(delay, self)
        if isinstance(result, Failure):
            log.error('Failed at schedule: %s', result.value)

    def __repr__(self):
        if hasattr(self.f, 'func_name'):
            func = self.f.func_name
            if hasattr(self.f, 'im_class'):
                func = self.f.im_class.__name__ + '.' + func
        else:
            func = reflect.safe_repr(self.f)

        return 'ScheduledCall%s(%s, *%s, **%s)' % (
            self.schedule, func, reflect.safe_repr(self.a),
            reflect.safe_repr(self.kw))