#!/usr/bin/python

# render_common.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2018
#
# This module contains some common functions for the rendering modules.


import os

# Import custom modules
#import osOps


def settings_file(scene, suffix=""):
	""" Determine the path to the settings file based on the full path of the
		scene file. N.B. This function is duplicated in render_submit.py
	"""
	if os.path.isfile(scene):
		sceneDir, sceneFile = os.path.split(scene)
		# settingsDir = os.path.join(sceneDir, os.environ['IC_METADATA'])
		# settingsFile = osOps.sanitize(sceneFile, replace='_') + suffix

		# # Create settings directory if it doesn't exist
		# if not os.path.isdir(settingsDir):
		# 	osOps.createDir(settingsDir)

		# return os.path.join(settingsDir, settingsFile)

	else:
		return False
