# -*- coding: utf-8 -*-
import sys
import PIL.Image
import signal
from pyinsane.abstract import Scanner
from pyinsane.rawapi import SaneException


__author__ = 'viruzzz-kun'


max_size = 1440


def handler(number, frame):
    print('INTERRUPTED')
    exit(0)


signal.signal(signal.SIGINT, handler)


def main():
    dev_name = sys.argv[1]
    file_format = sys.argv[2] if len(sys.argv) > 2 else 'png'
    try:
        resolution = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    except ValueError:
        resolution = 300
    mode = sys.argv[4] if len(sys.argv) > 4 else 'Color'
    sys.stdout.write('DEVICE:%s\n' % dev_name)
    sys.stdout.write('OPTIONS: %s\n' % ', '.join(
        ['%s: %s' % (opt, val) for opt, val in zip(
            ['format', 'resolution', 'mode'],
            [file_format, resolution, mode]
        )]
    ))
    device = Scanner(dev_name)
    for i in xrange(10):
        try:
            device.options['resolution'].value = resolution
            device.options['mode'].value = mode
        except SaneException, e:
            if i == 9:
                print('CANNOT SET DPI: %r' % e)
                return exit(1)
        else:
            if i:
                print('TOOK ATTEMPTS TO SET DPI: %s' % (i+1))
            break
    sys.stdout.write('SCANNING\n')
    try:
        scan_session = device.scan(multiple=False)
    except SaneException, e:
        print('FAILED: %r' % e)
        return exit(1)
    try:
        while True:
            scan_session.scan.read()
    except EOFError:
        pass
    sys.stdout.write('ACQUIRED\n')
    img = scan_session.images[0]
    img = resize_image(img)
    sys.stdout.write('DATA\n')
    img.save(sys.stdout, file_format, optimize=True)


def resize_image(img):
    w, h = img.size
    print('image size: %s x %s' % (w, h))
    over_w = max(w - max_size, 0)
    over_h = max(h - max_size, 0)
    if over_h == 0 and over_w == 0:
        return img
    elif over_w > over_h:
        new_w = max_size
        new_h = int(h * (float(new_w) / w))
    else:
        new_h = max_size
        new_w = int(w * (float(new_h) / h))
    img = img.resize((new_w, new_h), PIL.Image.LANCZOS)
    return img


if __name__ == "__main__":
    main()