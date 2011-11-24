#!/usr/bin/env python 

from distutils.core import setup 
import os 

setup(
    name = "django-simple-accounting",
    version = "dev",
    description = """A simple, but generic, accounting application for Django.
    
    This software was originally developed within Gasista Felice <http://www.gasistafelice.org>,
    a project by REES Marche <http://www.reesmarche.org>.
    """, 
    author="Lorenzo Franceschini",
    author_email="lorenzo.franceschini@informaetica.it",
    url = "https://github.com/seldon/django-simple-accounting",
    packages = ["simple_accounting"],
    classifiers = ["Development Status :: 3 - Alpha",
                   "Environment :: Web Environment",
                   "Framework :: Django",
                   "Intended Audience :: Developers",
                   "License :: OSI Approved :: GNU Affero General Public License v3",
                   "Operating System :: OS Independent",
                   "Programming Language :: Python",
                   "Topic :: Utilities"],
)