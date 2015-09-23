# -*- coding: utf-8 -*-
import itertools

import blinker
from sqlalchemy import Column, Integer, String, Index
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from twisted.internet.threads import deferToThread

from bouser.helpers.plugin_helpers import Dependency
from bouser.ext.simargl.client import SimarglClient
from bouser.ext.simargl.message import Message

__author__ = 'viruzzz-kun'


Base = declarative_base()
metadata = Base.metadata


class UserSubscriptions(Base):
    __tablename__ = "UserSubscriptions"
    __table_args__ = (Index(u'object_id', u'person_id'), )

    id = Column(Integer, primary_key=True)
    object_id = Column(String(256), index=True)
    person_id = Column(Integer)


class Client(SimarglClient):
    db = Dependency('bouser.db')

    def send(self, message):
        """
        :type message: simargl.message.Message
        :param message:
        :return:
        """
        if message.control and message.topic == 'subscription:add':
            return self.add_subscription(message)
        elif message.control and message.topic == 'subscription:del':
            return self.del_subscription(message)
        elif message.control and message.topic == 'subscription:notify':
            self.mail_notification(message)

    def add_subscription(self, message):
        def worker():
            with self.db.context_session(True) as session:
                obj = UserSubscriptions()
                obj.object_id = message.data['object_id']
                obj.person_id = message.data['person_id']
                session.add(obj)
                try:
                    session.commit()
                except (OperationalError, IntegrityError):
                    pass
        deferToThread(worker)

    def del_subscription(self, message):
        def worker():
            with self.db.context_session() as session:
                session.query(UserSubscriptions).filter(
                    UserSubscriptions.person_id == message.data['person_id'],
                    UserSubscriptions.object_id == message.data['object_id'],
                ).delete()

        deferToThread(worker)

    def mail_notification(self, envelope):
        def worker(message):
            result = []
            with self.db.context_session() as session:
                query = session.query(UserSubscriptions).filter(UserSubscriptions.object_id == message.data['object_id'])
                for o in query:
                    msg = Message()
                    msg.sender = message.sender
                    msg.recipient = o.person_id
                    msg.secondary = True
                    msg.immediate = True
                    msg.topic = 'mail:new'
                    msg.ctrl = True
                    data = data_from_message(message, str(o.person_id))
                    data['folder'] = 'system'
                    msg.data = data
                    result.append(msg)
            return result

        def on_finish(message_list):
            result = Message()
            result.control = True
            result.secondary = True
            result.recipient = None
            result.sender = None
            result.envelope = True
            result.topic = 'mail:new'
            result.data = message_list
            result.immediate = True
            self.simargl.message_received(self, result)

        def process_single():
            return worker(envelope)

        def process_envelope():
            return list(itertools.chain(itertools.imap(worker, envelope.data)))

        if envelope.envelope:
            deferToThread(process_envelope).addCallback(on_finish)
        else:
            deferToThread(process_single).addCallback(on_finish)


templates = {
    'exec_assigned': u'Вы назначены исполнителем',
    'exec_unassigned': u'Вы более не исполнитель',
    'altered': u'Действие изменено',
    'results': u'Получены результаты',
}

template = u'<p>Вы подписаны на уведомления {subject}</p><p>Причины уведомления: <ul>{reasons}</ul></p>'


def data_from_message(message, recipient):
    data = message.data
    reasons_codes = message.data['reasons'].get(recipient, []) + [message.data['default_reason']]
    reasons_texts = map(templates.get, reasons_codes)

    if data['object_id'].startswith('hitsl.action.'):
        template = u'''
        <p>Пациент: <b><a href="{client_url}">{client_name}</a></b></p>
        <p>Действие: <b><a href="{action_url}">{action_name}</a></b></p>
        <p>Причины уведомления:</p>
        <ul>{reasons_ul}</ul>
        '''
        subject = u'{reasons_comma}: {action_name} ({client_name})'.format(
            reasons_comma=u', '.join(reasons_texts),
            **data['kwargs']
        )

        reasons_ul = u''.join(map(u'<li>{0}</li>'.format, reasons_texts))

        return {
            'subject': subject,
            'text': template.format(reasons_ul=reasons_ul, **data['kwargs']),
        }
    return {
        'subject': u'Уведомление',
        'text': u'Уведомление по объекту {object_id}'
    }
