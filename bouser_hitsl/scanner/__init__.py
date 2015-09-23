# -*- coding: utf-8 -*-
from . import interfaces, resource, service

__author__ = 'viruzzz-kun'


def make(config):
    return service.ScanService()
