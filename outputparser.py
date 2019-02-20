#!/usr/bin/python

# render_output_parser.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2018
#
# Render Output Parser
# This module processes output line-by-line and checks for known error
# messages.


import re


# Define list of known errors - store in config file
known_errors_maya = []
#known_errors_maya.append(re.compile(r'Error: file: .* line [\d]+: Cannot load scene "[\w]*"\. Please check the scene name\.'))
known_errors_maya.append('File not found')
known_errors_maya.append('Cannot load scene')

def parse(line, job_type, renderer=None):
	""" Parse line of output.
	"""
	if job_type == 'Maya':
		for error_msg in known_errors_maya:
			#if bool(error_msg.search(line)):
			if error_msg in line:
				#print(line)
				return True

	return False
