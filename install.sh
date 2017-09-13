#!/bin/sh

#Install application dependencies in /vendored folder
pip install -r requirements.txt -t vendored

#Install local dev environment & test dependencies in default site_packages path
pip install -r requirements-dev.txt



