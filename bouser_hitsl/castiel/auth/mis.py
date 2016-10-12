#!/usr/bin/env python
# -*- coding: utf-8 -*-
from hashlib import md5

from sqlalchemy import Column, Integer, String, Unicode
from sqlalchemy.ext.declarative import declarative_base
from zope.interface import implementer

from bouser.helpers.plugin_helpers import Dependency, BouserPlugin
from bouser.helpers.twisted_helpers import deferred_to_thread
from bouser.castiel.exceptions import EInvalidCredentials
from bouser.castiel.interfaces import IAuthenticator, IAuthObject

__author__ = 'viruzzz-kun'
__created__ = '08.02.2015'

Base = declarative_base()
metadata = Base.metadata


class Person(Base):
    __tablename__ = "Person"

    id = Column(Integer, primary_key=True, nullable=False)
    login = Column(String, index=True, nullable=False)
    password = Column(String, nullable=False)
    code = Column(String(12), nullable=False)
    regionalCode = Column(String(16), nullable=False)
    lastName = Column(Unicode(30), nullable=False)
    firstName = Column(Unicode(30), nullable=False)
    patrName = Column(Unicode(30), nullable=False)

    @property
    def full_name(self):
        return u' '.join((u'%s %s %s' % (self.lastName, self.firstName, self.patrName)).split())


@implementer(IAuthObject)
class MisAuthObject(object):
    __slots__ = ['user_id', 'login', 'groups', 'person_info']

    def __init__(self, person=None):
        if person:
            self.user_id = person.id
            self.login = person.login
            self.person_info = {
                'full_name': person.full_name,
                'code': person.code,
                'regional_code': person.regionalCode
            }
        else:
            self.user_id = None
            self.login = None
            self.person_info = None
        self.groups = []

    def __getstate__(self):
        return [
            self.user_id,
            self.login,
            self.groups,
        ]

    def __setstate__(self, state):
        self.user_id, self.login, self.groups = state
        self.person_info = None

    def get_description(self):
        return u'{0} {1} ({2})'.format(
            self.person_info['full_name'],
            self.user_id,
            self.person_info['regional_code'] or self.person_info['code']
        ) if self.person_info is not None else self.login


@implementer(IAuthenticator)
class MisAuthenticator(BouserPlugin):
    signal_name = 'bouser.auth'
    db = Dependency('bouser.db')

    @deferred_to_thread
    def get_user(self, login, password):
        if not self.db:
            raise Exception('Database is not initialized')
        with self.db.context_session(True) as session:
            if isinstance(password, unicode):
                pwd = password.encode('utf-8', errors='ignore')
            elif isinstance(password, str):
                pwd = password
            else:
                raise TypeError('password should be either unicode ot str')
            result = session.query(Person).filter(
                Person.login == login,
                Person.password == md5(pwd).hexdigest()).first()

            if result:
                return MisAuthObject(result)
            raise EInvalidCredentials


def make(config):
    return MisAuthenticator()