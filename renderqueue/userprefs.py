#!/usr/bin/python

# userprefs.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2013-2018
#
# Manages user preferences stored in JSON files.


import json
import os

import oswrapper
#import verbose


userPrefsDir = os.environ['IC_USERPREFS']
config = SafeConfigParser()
configFile = os.path.join(userPrefsDir, 'userPrefs.ini')


def read():
	""" Read config file - create it if it doesn't exist.
	"""
	if os.path.exists(configFile):
		config.read(configFile)
		verbose.print_("Read user prefs.", 4)

	else:
		create()
		verbose.print_("Created user prefs.", 4)


def write():
	""" Write config file to disk.
	"""
	try:
		# read()
		with open(configFile, 'w') as f:
			config.write(f)

	except IOError:
		verbose.error("Unable to write user prefs configuration file.")


def create():
	""" Create config file if it doesn't exist.
	"""
	if not os.path.exists(userPrefsDir):
		osOps.createDir(userPrefsDir)

	write()


def query(section, key, datatype='str', default=None, create=False):
	""" Get a value and from config file.
		If the value doesn't exist return a default value.
		If 'create' is true, also store the value in the config file.
	"""
	value = None

	if datatype == 'str':
		try:
			return config.get(section, key)
		except:
			if type(default) is str:
				value = default
			else:
				value = ""

	elif datatype == 'int':
		try:
			return config.getint(section, key)
		except:
			if type(default) is int:
				value = default
			else:
				value = 0

	elif datatype == 'float':
		try:
			return config.getfloat(section, key)
		except:
			if type(default) is float:
				value = default
			else:
				value = 0.0

	elif datatype == 'bool':
		try:
			return config.getboolean(section, key)
		except:
			if type(default) is bool:
				value = default
			else:
				value = False

	if create:
		edit(section, key, value)

	return value


def edit(section, key, value):
	""" Set a value and save config file to disk.
		If the section doesn't exist it will be created.
		Values are always stored as strings.
	"""
	if not config.has_section(section):
		config.add_section(section)

	config.set(section, key, str(value))

	write()


def updateRecentShots(newEntry):
	""" Update recent shots list and save config file to disk.
	"""
	read()

	# Create recent section and shots entry if they don't exist
	if not config.has_section('recent'):
		config.add_section('recent')
	if not config.has_option('recent', 'shots'):
		config.set('recent', 'shots', '')

	recentShotLs = []  # Clear recent shot list

	fileStr = config.get('recent', 'shots')
	if not fileStr=='':
		recentShotLs = fileStr.split('; ')
	else:
		recentShotLs = []

	if newEntry in recentShotLs:  # If entry already exists, delete it
		recentShotLs.remove(newEntry)

	recentShotLs.insert(0, newEntry)  # Prepend entry to the list

	while len(recentShotLs) > int(os.environ['IC_NUMRECENTFILES']):
		recentShotLs.pop()

	# Encode the list into a single line with entries separated by semicolons
	config.set('recent', 'shots', '; '.join(n for n in recentShotLs))

	write()


def getRecentShots(last=False):
	""" Read recent shots list and return list/array.
	"""
	read()

	try:
		recentShotLs = config.get('recent', 'shots').split('; ')
		recentShotLs = recentShotLs[:int(os.environ['IC_NUMRECENTFILES'])]
	except:
		recentShotLs = []

	if last:
		return recentShotLs[0]
	else:
		return recentShotLs

