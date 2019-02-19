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
		sceneDir, sceneFile = os.path.split(scene)
		# settingsDir = os.path.join(sceneDir, os.environ['IC_METADATA'])
		settingsFile = oswrapper.sanitize(sceneFile, replace='_') + suffix

		# # Create settings directory if it doesn't exist
		# if not os.path.isdir(settingsDir):
		# 	oswrapper.createDir(settingsDir)

		# return os.path.join(settingsDir, settingsFile)
		return os.path.join('/var/tmp', settingsFile)  # temp - linux only

	else:
		return False

