# -*- coding: utf-8 -*-
from zope.interface import Interface

__author__ = 'viruzzz-kun'


class IScanService(Interface):
    def getImage(self, dev_name, consumer, options):
        """
        Get IProducer for dev_name
        :param dev_name: Scanner Device name
        :param consumer: IConsumer provider
        :param options: scanning settings dict
        :return:
        """

    def getScanners(self, force=False):
        """
        Get scanners
        :param force: get scanners list even if cached
        :return:
        """