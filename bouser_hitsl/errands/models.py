# -*- coding: utf-8 -*-
import datetime

from sqlalchemy import Column, Integer, Text, String, DateTime, Unicode, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()
metadata = Base.metadata


class Errand(Base):
    __tablename__ = u'Errand'
    _table_description = u'поручения'

    id = Column(Integer, primary_key=True)
    createDatetime = Column(DateTime, nullable=False, default=datetime.datetime.now)
    modifyDatetime = Column(DateTime, nullable=False, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    number = Column(String(30), nullable=False)
    deleted = Column(Integer, nullable=False, server_default=u"'0'")
    setPerson_id = Column(index=True)
    execPerson_id = Column(index=True)
    text = Column(Text, nullable=False)
    plannedExecDate = Column(DateTime, nullable=False)
    execDate = Column(DateTime, nullable=False)
    event_id = Column(Integer, index=True)
    result = Column(Text, nullable=False)
    readingDate = Column(DateTime)
    status_id = Column(ForeignKey('rbErrandStatus.id'), nullable=False)
    communications = Column(Text)

    status = relationship('rbErrandStatus')

    def __json__(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'create_datetime': self.createDatetime,
            'number': self.number,
            'set_person': self.setPerson,
            'exec_person': self.execPerson,
            'text': self.text,
            'communications': self.communications,
            'planned_exec_date': self.plannedExecDate,
            'exec_date': self.execDate,
            'result': self.result,
            'reading_date': self.readingDate
        }

    def from_message(self, message, number):
        self.setPerson_id = message.sender
        self.execPerson_id = message.recipient
        self.text = message.data.get('text', '')
        self.communications = message.data.get('communications', '')
        self.number = number
        self.event_id = message.data.get('event_id', '')
        self.plannedExecDate = message.data.get('planned_exec_date', datetime.datetime.now())
        self.status_id = message.data.get('status').get('id', 1)

    def as_message(self):
        from bouser_simargl.message import Message
        message = Message()
        message.topic = 'errand'
        message.sender = self.setPerson_id
        message.recipient = self.execPerson_id
        message.tags = set()
        message.data = {
            'text': self.text,
            'communications': self.communications
        }
        return message


class rbCounter(Base):
    __tablename__ = u'rbCounter'

    id = Column(Integer, primary_key=True)
    code = Column(String(8), nullable=False)
    name = Column(String(64), nullable=False)
    value = Column(Integer, nullable=False, server_default=u"'0'")
    prefix = Column(String(32))
    separator = Column(String(8), server_default=u"' '")
    reset = Column(Integer, nullable=False, server_default=u"'0'")
    startDate = Column(DateTime, nullable=False)
    resetDate = Column(DateTime)
    sequenceFlag = Column(Integer, nullable=False, server_default=u"'0'")


class rbErrandStatus(Base):
    __tablename__ = u'rbErrandStatus'
    _table_description = u'статусы поручений'

    id = Column(Integer, primary_key=True)
    code = Column(Unicode(16), index=True, nullable=False)
    name = Column(Unicode(64), nullable=False)
