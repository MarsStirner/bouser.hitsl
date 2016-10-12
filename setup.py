# -*- coding: utf-8 -*-
from setuptools import setup

__author__ = 'viruzzz-kun'
__version__ = '0.2.2'


if __name__ == '__main__':
    setup(
        name="bouser_hitsl",
        version=__version__,
        description="Hitsl extensions for Bouser.",
        long_description='',
        author=__author__,
        author_email="viruzzz.soft@gmail.com",
        license='MIT',
        url="http://twistedmatrix.com/projects/core/documentation/howto/tutorial/index.html",
        packages=[
            "bouser_hitsl",
            "bouser_hitsl.errands",
            "bouser_hitsl.scanner",
            "bouser_hitsl.schedule_manager",
            "bouser_hitsl.schedule_manager.txscheduling",
            "bouser_hitsl.schedule_manager.txscheduling.tests",
            "bouser_hitsl.simargl",
            "bouser_hitsl.simargl.clients",
            "bouser_hitsl.castiel",
            "bouser_hitsl.castiel.auth",
        ],
        zip_safe=False,
        package_data={},
        install_requires=[
            'bouser',
            'bouser_db',
            'bouser_simargl[DB]',
            'ldaptor',
        ],
        classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: No Input/Output (Daemon)",
            "Programming Language :: Python",
        ])

