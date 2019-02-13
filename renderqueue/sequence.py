#!/usr/bin/python

# sequence.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# Benjamin Parry <ben.parry@gps-ldn.com>
# (c) 2015-2018
#
# These functions convert formatted sequences to lists and vice-versa.


import re
from collections import OrderedDict

# Import custom modules
# import verbose


def numList(num_range_str, sort=True, quiet=False):
	""" Takes a formatted string describing a range of numbers and returns a
		list of integers, with duplicates removed.
		e.g. '1-5, 20, 24, 50-55x2, 1001-1002'
		returns [1, 2, 3, 4, 5, 20, 24, 50, 52, 54, 1001, 1002]
	"""
	# Check that num_range_str isn't empty
	if num_range_str == "":
		if not quiet:
			#verbose.warning("No frame range specified.")
			print("Warning: No frame range specified.")
		return None

	num_int_list = []

	# Regex for sequences including x# for steps
	seq_format = re.compile(r'^\d+-\d+(x\d+)?$')

	# Split into groups of ranges separated by commas and spaces
	if num_range_str[-1] != ",":
		num_range_str += ","
	grps = [x[:-1] for x in num_range_str.split()]

	# Try/except statements used instead of if statements for speed-up
	for grp in grps:
		# Check if 'grp' is a single number (e.g. 10)
		try:
			num_int_list.append(int(grp))

		except ValueError:
			# Check if 'grp' is a number sequence (e.g. 1-10)
			if seq_format.match(grp) is not None:
				step = 1
				first, last = grp.split('-')
				first = int(first)

				try:
					last = int(last)
				except ValueError:
					last, step = last.split('x')
					last = int(last)
					step = int(step)

				# Deal with ranges in normal/reverse order
				if first > last:
					num_int_list += list(range(first, last-1, -step))
				else:
					num_int_list += list(range(first, last+1, step))

			else:
				if not quiet:
					#verbose.error("Sequence format is invalid.")
					print("ERROR: Sequence format is invalid.")
				return None

	# Remove duplicates & sort list
	if sort:
		return sorted(list(set(num_int_list)), key=int)
	else:
		return list(OrderedDict.fromkeys(num_int_list))


def numRange(num_int_list, padding=0, quiet=False):
	""" Takes a list of integer values and returns a formatted string
		describing the range of numbers.
		e.g. [1, 2, 3, 4, 5, 20, 24, 1001, 1002]
		returns '1-5, 20, 24, 1001-1002'
	"""
	num_range_str = ''

	# Remove duplicates & sort list
	try:
		sorted_list = sorted(list(set(num_int_list)), key=int)
	except (ValueError, TypeError):
		if not quiet:
			#verbose.error("Number list only works with integer values.")
			print("ERROR: Number list only works with integer values.")
		return False

	# Find sequences
	first = None
	for x in sorted_list:
		if first is None:
			first = last = x
		elif x == last+1:
			last = x
		else:
			if first == last:
				num_range_str += "%s, " %str(first).zfill(padding)
			else:
				num_range_str += "%s-%s, " %(str(first).zfill(padding), str(last).zfill(padding))
			first = last = x
	if first is not None:
		if first == last:
			num_range_str += "%s" %str(first).zfill(padding)
		else:
			num_range_str += "%s-%s" %(str(first).zfill(padding), str(last).zfill(padding))

	return num_range_str


def seqRange(sorted_list, gen_range=False):
	""" Generate first and last values, or ranges of values, from sequences.
	"""
	first = None
	for x in sorted_list:
		if first is None:
			first = last = x
		elif x == last+1:
			last = x
		else:
			if gen_range:
				yield range(first, last+1)
			else:
				yield first, last
			first = last = x
	if first is not None:
		if gen_range:
			yield range(first, last+1)
		else:
			yield first, last


def chunks(l, n):
	""" Yield successive n-sized chunks from l.
	"""
	# for i in xrange(0, len(l), n):  # Python 2.x only
	for i in range(0, len(l), n):
		yield l[i:i+n]

