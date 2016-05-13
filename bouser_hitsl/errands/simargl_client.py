# -*- coding: utf-8 -*-
import datetime

from twisted.internet.threads import deferToThread

from bouser.helpers.plugin_helpers import Dependency
from bouser_simargl.client import SimarglClient
from bouser.ext.simargl.message import Message
from .models import Errand, rbCounter



class Client(SimarglClient):
    db = Dependency('bouser.db')

    def send(self, message):
        """
        :type message: simargl.message.Message
        :param message:
        :return:
        """
        if message.control and message.topic == 'errand:new':
            return self.new_mail(message)

    def new_mail(self, message):
        def worker_single():
            with self.db.context_session() as session:
                obj = Errand()
                number = get_new_errand_number(session)
                obj.from_message(message, number)
                session.add(obj)
                return {
                    'usermail_id': obj.id,
                    'recipient_id': obj.execPerson_id
                }

        def worker_envelope():
            result = []
            with self.db.context_session() as session:
                for msg in message.data:
                    obj = Errand()
                    obj.from_message(msg)
                    session.add(obj)
                    result.append({
                        'usermail_id': obj.id,
                        'recipient_id': obj.execPerson_id
                    })

        def on_finish(new_mail_result):
            if isinstance(new_mail_result, dict):
                message = Message()
                message.topic = 'errand:notify'
                message.sender = None
                message.recipient = new_mail_result['recipient_id']
                message.data = {
                    'subject': u'Новое поручение',
                    'id': new_mail_result['usermail_id']
                }
                return self.simargl.inject_message(message)


        if message.envelope:
            deferToThread(worker_envelope).addCallback(on_finish)
        else:
            deferToThread(worker_single).addCallback(on_finish)


def get_new_errand_number(session):
    """Формирование number (номера поручения)."""
    counter = session.query(rbCounter).filter(rbCounter.code == 8).with_for_update().first()
    if not counter:
        return ''
    external_id = _get_errand_number_from_counter(counter.prefix,
                                                  counter.value + 1,
                                                  counter.separator)
    counter.value += 1
    session.add(counter)
    return external_id


def _get_errand_number_from_counter(prefix, value, separator):
    def get_date_prefix(val):
        val = val.replace('Y', 'y').replace('m', 'M').replace('D', 'd')
        if val.count('y') not in [0, 2, 4] or val.count('M') > 2 or val.count('d') > 2:
            return None
        # qt -> python date format
        _map = {'yyyy': '%Y', 'yy': '%y', 'mm': '%m', 'dd': '%d'}
        try:
            format_ = _map.get(val, '%Y')
            date_val = datetime.date.today().strftime(format_)
            check = datetime.datetime.strptime(date_val, format_)
        except ValueError, e:
            return None
        return date_val

    prefix_types = {'date': get_date_prefix}

    prefix_parts = prefix.split(';')
    prefix = []
    for p in prefix_parts:
        for t in prefix_types:
            pos = p.find(t)
            if pos == 0:
                val = p[len(t):]
                if val.startswith('(') and val.endswith(')'):
                    val = prefix_types[t](val[1:-1])
                    if val:
                        prefix.append(val)
    return separator.join(prefix + ['%d' % value])


