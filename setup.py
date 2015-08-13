#!/usr/bin/env python

from setuptools import setup

setup(name='taskcluster-checkout',
      version='0.1.0',
      description='Checkout cached repositories served by TaskCluster',
      author='Anthony Miyaguchi',
      author_email='amiyaguchi@mozilla.com',
      url='https://github.com/acmiyaguchi/taskcluster-checkout.git',
      py_modules=['checkout'],
      license='MPL2',
      install_requires=['python-hglib'],
      extras_require={
          'test': [
              'nose',
              'mock',
              'pep8',
              'pyflakes',
              'coverage',
              'testfixtures',
          ]
      },
      entry_points={
          'console_scripts': ['tc-checkout = checkout:main'],
      })