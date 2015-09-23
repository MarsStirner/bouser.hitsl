#!/usr/bin/env python
# -*- coding: utf-8 -*-

from . import service


def make(config):
    return service.ScheduleManager(config)