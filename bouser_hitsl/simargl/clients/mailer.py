# -*- coding: utf-8 -*-
import datetime

from sqlalchemy import Column, Integer, Text, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from twisted.internet.threads import deferToThread

from bouser.helpers.plugin_helpers import Dependency
from bouser.ext.simargl.client import SimarglClient
from bouser.ext.simargl.message import Message

__author__ = 'viruzzz-kun'


Base = declarative_base()
metadata = Base.metadata


class UserMail(Base):
    __tablename__ = "UserMail"
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, nullable=True)
    recipient_id = Column(Integer, nullable=True)
    subject = Column(String(256), nullable=False)
    text = Column(Text, nullable=False)
    datetime = Column(DateTime, nullable=False)
    read = Column(Integer)
    mark = Column(Integer)
    parent_id = Column(Integer, nullable=True)
    folder = Column(String(50), nullable=False)

    def __json__(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'subject': self.subject,
            'text': self.text,
        }

    def from_message(self, message):
        self.sender_id = message.sender
        self.recipient_id = message.recipient
        self.subject = message.data.get('subject', '')
        self.text = message.data.get('text', '')
        self.datetime = message.data.get('datetime', datetime.datetime.now())
        self.parent_id = message.data.get('parent_id', None)
        self.mark = message.data.get('mark') and 1 or 0
        self.folder = message.data.get('folder', 'inbox')
        self.read = 0

    def as_message(self):
        message = Message()
        message.topic = 'mail'
        message.sender = self.sender_id
        message.recipient = self.recipient_id
        message.tags = set()
        message.data = {
            'subject': self.subject,
            'text': self.text,
            'datetime': self.datetime,
            'read': self.read,
            'mark': self.mark,
            'parent_id': self.parent_id,
            'folder': self.folder,
        }
        return message


class Client(SimarglClient):
    db = Dependency('bouser.db')

    def send(self, message):
        """
        :type message: simargl.message.Message
        :param message:
        :return:
        """
        if message.control and message.topic == 'mail:new':
            return self.new_mail(message)

    def new_mail(self, message):
        def worker_single():
            with self.db.context_session() as session:
                obj = UserMail()
                obj.from_message(message)
                session.add(obj)
                return {
                    'usermail_id': obj.id,
                    'recipient_id': obj.recipient_id
                }

        def worker_envelope():
            result = []
            with self.db.context_session() as session:
                for msg in message.data:
                    obj = UserMail()
                    obj.from_message(msg)
                    session.add(obj)
                    result.append({
                        'usermail_id': obj.id,
                        'recipient_id': obj.recipient_id
                    })

        def on_finish(new_mail_result):
            if isinstance(new_mail_result, dict):
                message = Message()
                message.topic = 'mail:notify'
                message.sender = None
                message.recipient = new_mail_result['recipient_id']
                message.data = {
                    'subject': u'Новое письмо',
                    'id': new_mail_result['usermail_id']
                }
                self.simargl.inject_message(message)

        if message.envelope:
            deferToThread(worker_envelope).addCallback(on_finish)
        else:
            deferToThread(worker_single).addCallback(on_finish)
