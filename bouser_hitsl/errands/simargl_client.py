# -*- coding: utf-8 -*-

from twisted.internet.threads import deferToThread

from bouser.helpers.plugin_helpers import Dependency
from bouser_simargl.client import SimarglClient
from bouser.ext.simargl.message import Message


class Client(SimarglClient):
    db = Dependency('bouser.db')

    def send(self, message):
        """
        :type message: simargl.message.Message
        :param message:
        :return:
        """
        if message.control and message.topic == 'errand:new':
            return self.new_errand_notify(message)
        elif message.control and message.topic == 'errand:markread':
            return self.errand_read_notify(message)
        elif message.control and message.topic == 'errand:execute':
            return self.errand_exec_notify(message)
        elif message.control and message.topic == 'errand:delete':
            return self.errand_delete_notify(message)

    def new_errand_notify(self, message):
        def worker_single():
            # with self.db.context_session() as session:
            #    errand = Errand.query.get(message.data['errand_id'])
            #    ...
            return message

        def worker_envelope():
            return message

        def on_finish(errand_create_message):
            notify_message = Message()
            notify_message.topic = 'errand:notify'
            notify_message.sender = None
            notify_message.recipient = errand_create_message.recipient
            notify_message.data = {
                'subject': u'Новое поручение',
                'id': errand_create_message.data['errand_id']
            }
            return self.simargl.inject_message(notify_message)

        if message.envelope:
            deferToThread(worker_envelope).addCallback(on_finish)
        else:
            deferToThread(worker_single).addCallback(on_finish)

    def errand_read_notify(self, message):
        notify_message = Message()
        notify_message.topic = 'errand:notify'
        notify_message.sender = None
        notify_message.recipient = message.recipient
        notify_message.data = {
            'subject': u'Изменение отметки о прочтении поручения',
            'id': message.data['errand_id']
        }
        return self.simargl.inject_message(notify_message)

    def errand_exec_notify(self, message):
        notify_message = Message()
        notify_message.topic = 'errand:notify'
        notify_message.sender = None
        notify_message.recipient = message.recipient
        notify_message.data = {
            'subject': u'Изменение отметки об исполнении поручения',
            'id': message.data['errand_id']
        }
        return self.simargl.inject_message(notify_message)

    def errand_delete_notify(self, message):
        notify_message = Message()
        notify_message.topic = 'errand:notify'
        notify_message.sender = None
        notify_message.recipient = message.recipient
        notify_message.data = {
            'subject': u'Поручение удалено',
            'id': message.data['errand_id']
        }
        return self.simargl.inject_message(notify_message)
