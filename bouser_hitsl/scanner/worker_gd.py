# -*- coding: utf-8 -*-
import sys
import json

from pyinsane.abstract import get_devices


__author__ = 'viruzzz-kun'


def make(item):
    return {
        'name': item.name,
        'vendor': item.vendor,
        'model': item.model,
        'dev_type': item.dev_type
    }


def main():
    json.dump({
        'devices': map(make, get_devices())
    }, sys.stdout)


if __name__ == "__main__":
    main()