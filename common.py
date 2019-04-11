#!/usr/bin/python

# render_common.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# This module contains some common functions for the rendering modules.


import logging
import os

# Import custom modules
import oswrapper


formatter = logging.Formatter("%(asctime)-15s %(levelname)-8s %(message)s")


def setup_logger(name, log_file, level=logging.INFO):
	""" Function to create and setup multiple loggers.
	"""
	handler = logging.FileHandler(log_file)
	handler.setFormatter(formatter)

	logger = logging.getLogger(name)
	logger.setLevel(level)
	logger.addHandler(handler)

	return logger


def settings_file(scene, suffix=""):
	""" Determine the path to the settings file based on the full path of the
		scene file. N.B. This function is duplicated in render_submit.py
	"""
	if os.path.isfile(scene):
		scene_dir, scene_file = os.path.split(scene)
		# settings_dir = os.path.join(scene_dir, os.environ['IC_METADATA'])
		settings_file = oswrapper.sanitize(scene_file, replace='_') + suffix

		# # Create settings directory if it doesn't exist
		# if not os.path.isdir(settings_dir):
		# 	oswrapper.createDir(settings_dir)

		# return os.path.join(settings_dir, settings_file)
		return os.path.join('/var/tmp', settings_file)  # temp - linux only

	else:
		return False

