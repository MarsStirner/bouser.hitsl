# -*- coding: utf-8 -*-
from . import external_cas


def make(config):
    return external_cas.ExternalCastielService(config)