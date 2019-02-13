#!/usr/bin/python

import os
import platform


def setenv():
	""" Set some environment variables for basic operation.
	"""
	# Set version string
	os.environ['RQ_VERSION'] = "0.2.0"

	# Set vendor string
	os.environ['RQ_VENDOR'] = "UNIT"

	# Standardise some environment variables across systems.
	# Usernames will always be stored as lowercase for compatibility.
	if platform.system() == "Windows":  # Windows
		#os.environ['RQ_RUNNING_OS'] = "Windows"
		if not 'RQ_USERNAME' in os.environ:
			os.environ['RQ_USERNAME'] = os.environ['USERNAME'].lower()
		userHome = os.environ['USERPROFILE']
	elif platform.system() == "Darwin":  # Mac OS
		#os.environ['RQ_RUNNING_OS'] = "MacOS"
		if not 'RQ_USERNAME' in os.environ:
			os.environ['RQ_USERNAME'] = os.environ['USER'].lower()
		userHome = os.environ['HOME']
	else:  # Linux
		#os.environ['RQ_RUNNING_OS'] = "Linux"
		if not 'RQ_USERNAME' in os.environ:
			os.environ['RQ_USERNAME'] = os.environ['USER'].lower()
		userHome = os.environ['HOME']

	# Check for environment awareness
	try:
		os.environ['RQ_ENV']
	except KeyError:
		os.environ['RQ_ENV'] = "STANDALONE"

	# Set up basic paths
	os.environ['RQ_DATABASE'] = 'J:/rq_database'
	#os.environ['RQ_BASEDIR'] = os.getcwd()
	os.environ['RQ_CONFIGDIR'] = os.path.join(os.environ['RQ_DATABASE'], 'config')
	os.environ['RQ_USERPREFS'] = os.path.join(os.environ['RQ_CONFIGDIR'], 'users', os.environ['RQ_USERNAME'])  # User prefs stored on server
	#os.environ['RQ_USERPREFS'] = os.path.join(userHome, '.renderqueue')  # User prefs stored in user home folder
	os.environ['RQ_HISTORY'] = os.path.join(os.environ['RQ_USERPREFS'], 'history')

	appendSysPaths()

