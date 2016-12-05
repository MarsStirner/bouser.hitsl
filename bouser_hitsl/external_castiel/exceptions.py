#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bouser.excs import SerializableBaseException


class EUnsuccesfulCheckTGT(SerializableBaseException):
    """
    Raised when error in checking external CAS' TGT occurs
    """
    def __init__(self, message):
        self.message = 'Cannot validate TGT in external CAS: {0}'.format(message)
