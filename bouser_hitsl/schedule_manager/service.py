# -*- coding: utf-8 -*-
import re

from twisted.application.service import Service

from bouser.helpers.plugin_helpers import BouserPlugin, Dependency


class CronTask(object):
    __slots__ = ['cron', 'task']

    def __init__(self, src):
        self.cron = src['cron']
        self.task = src['task']


class ScheduleManager(Service, BouserPlugin):
    """
    I manage scheduled tasks
    """
    signal_name = 'bouser.schedule_manager'
    db = Dependency('bouser.db')

    re_cron = re.compile(ur'(.+?)\s+(.+?)\s+(.+?)\s+(.+?)\s+(.+?)')
    re_task = re.compile(ur'((\w+)(\s*\((.*?)\))?)')

    def __init__(self, config):
        self.task_functions = {}
        self.schedules = {}

        mixins = config.get('mixins', [])
        if isinstance(mixins, basestring):
            mixins = mixins.split(' ')
        elif not isinstance(mixins, (list, tuple, dict)):
            raise Exception('Mixins mus be either string or list/tuple. In worst case - dict')

        for mn in mixins:
            if '.' not in mn:
                continue
            module_name, func_name = mn.rsplit('.', 1)
            module = __import__(module_name, globals(), locals(), [func_name])
            self.task_functions[func_name] = getattr(module, func_name)

    @db.on
    def set_config(self, db):
        from .txscheduling.cron import parseCronEntry, CronSchedule
        from .txscheduling.task import ScheduledCall

        self.stopService()
        self.schedules = {}
        for s in [CronTask({'cron': '0 * * * *', 'task': 'errand_statuses'})]:
            # log.debug(u'Загрузка строки расписания: "%s %s"', s.cron, s.task)
            cron = s.cron
            if cron.startswith('@'):
                cron = cron\
                    .replace('@yearly', '0 0 1 1 *', 1)\
                    .replace('@annually', '0 0 1 1 *', 1)\
                    .replace('@monthly', '0 0 1 * *', 1)\
                    .replace('@weekly', '0 0 * * 0', 1)\
                    .replace('@daily', '0 0 * * *', 1)\
                    .replace('@hourly', '0 * * * *', 1)
            cron_match = self.re_cron.match(cron)
            task_match = self.re_task.match(s.task)
            if not cron_match:
                # log.error(u'Неверный формат строки расписания: "%s"', s.cron)
                continue
            m, h, d, M, w = cron_match.groups()
            full_name, name, _, arg = task_match.groups()
            if not name in self.task_functions:
                # log.warning(u'Задача "%s" не зарегистрирована', name)
                continue

            try:
                schedule = {
                    'minutes': parseCronEntry(m, 0, 59),
                    'hours':   parseCronEntry(h, 0, 23),
                    'doms':    parseCronEntry(d, 1, 31),
                    'months':  parseCronEntry(M, 1, 12),
                    'dows':    parseCronEntry(w, 0, 6),
                }
            except Exception, e:
                # log.error(u'Неверный формат значения в строке расписания\n%s', repr(e))
                continue

            if arg:
                sc = ScheduledCall(self.task_functions[name], self, arg)
            else:
                sc = ScheduledCall(self.task_functions[name], self)

            self.schedules[full_name] = CronSchedule(schedule), sc
        #     log.info(u'Задача "%s" поставлена в очередь', task_match.group(0))
        # log.info(u'Загрузка задач завершена')

    def startService(self, now=True):
        # log.debug(u'Запуск службы расписаний')
        for name, (schedule, call) in self.schedules.iteritems():
            call.start(schedule, now=now)

    def stopService(self):
        # log.debug(u'Останов службы расписаний')
        from twisted.internet.error import AlreadyCancelled, AlreadyCalled
        for name, (schedule, call) in self.schedules.iteritems():
            try:
                call.stop()
            except AlreadyCancelled:
                pass
            except AlreadyCalled:
                pass
