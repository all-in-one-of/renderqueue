#!/usr/bin/python

# sequence.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# Benjamin Parry <ben.parry@gps-ldn.com>
# (c) 2015-2018
#
# These functions convert formatted sequences to lists and vice-versa.


import glob
import os
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


def getBases(path, delimiter="."):
	""" Find file sequence bases in path.
		Returns a list of bases (the first part of the filename, stripped of
		frame number padding and extension).
	"""
	# Get directory contents
	try:
		ls = os.listdir(path)
		ls.sort()
	except OSError:
		#verbose.error("No such file or directory: '%s'" %path)
		return False

	# Create list to hold all basenames of sequences
	all_bases = []

	# Get list of files in current directory
	for filename in ls:

		# Only work on files, not directories, and ignore files that start with a dot
		if os.path.isfile(os.path.join(path, filename)) and not filename.startswith('.'):

			# Extract file extension
			root, ext = os.path.splitext(filename)

			# Match file names which have a trailing number separated by the
			# delimiter character
			seqRE = re.compile(r'%s\d+$' %re.escape(delimiter))
			match = seqRE.search(root)

			# Store filename prefix
			if match is not None:
				prefix = root[:root.rfind(match.group())]
				all_bases.append('%s%s#%s' % (prefix, delimiter, ext))

	# Remove duplicates & sort list
	bases = list(set(all_bases))
	bases.sort()
	return bases


def getSequence(path, pattern, **kwargs):
	""" Looks for other frames in a sequence that fit a particular pattern.
		Pass the first (lowest-numbered) frame in the sequence to the
		detectSeq function and return its results.
	"""
	#filter_ls = glob.glob("%s*" %os.path.join(path, base))
	pattern = pattern.replace('#', '*')
	filter_ls = glob.glob(os.path.join(path, pattern))
	filter_ls.sort()
	#frame_ls = []

	return detectSeq(filter_ls[0], **kwargs)


def detectSeq(filepath, delimiter=".", ignorePadding=False, contiguous=False):
	""" Detect file sequences based on the provided file path.

		Returns a tuple containing 5 elements:
		1. path - the directory path containing the file
		2. prefix - the first part of the filename
		3. frame - the sequence of frame numbers computed from the numeric
		   part of the filename, represented as a string
		4. ext - the filename extension
		5. num_frames - the number of frames in the sequence

		The 'delimiter' flag specifies a character used to separate the
		numeric part of the filename.
		If 'ignorePadding' flag is True, return sequence even if the number
		of padding digits differ.
		If 'contiguous' flag is True, only return a contiguous sequence
		(no gaps).
	"""
	lsFrames = []  # Clear frame list

	# Parse file path
	filename = os.path.basename(filepath)
	path = os.path.dirname(filepath)
	base, ext = os.path.splitext(filename)
	try:
		if delimiter:
			prefix, framenumber = base.rsplit(delimiter, 1)
		else:
			match = re.search(r"\d*$", base)
			framenumber = match.group()
			prefix = re.sub(r"\d*$", "", base)
		padding = len(framenumber)
		framenumber = int(framenumber)
	except ValueError:
		#verbose.error("Could not parse sequence.")
		return (path, base, None, ext, 1)

	# Construct regular expression for matching files in the sequence
	if ignorePadding:
		re_seq_str = r"^%s%s\d+%s$" %(re.escape(prefix), re.escape(delimiter), re.escape(ext))
	else:
		re_seq_str = r"^%s%s\d{%d}%s$" %(re.escape(prefix), re.escape(delimiter), padding, re.escape(ext))
	re_seq_pattern = re.compile(re_seq_str)

	# Find other files in the sequence in the same directory
	for item in os.listdir(path):
		if re_seq_pattern.match(item) is not None:
			#lsFrames.append(item)  # whole filename
			#lsFrames.append(int(os.path.splitext(item)[0].rsplit('.', 1)[1]))  # just the frame number
			base = os.path.splitext(item)[0]
			if delimiter:
				framenumber = base.rsplit(delimiter, 1)[1]
			else:
				match = re.search(r"\d*$", base)
				framenumber = match.group()
			lsFrames.append(int(framenumber))  # just the frame number
			numFrames = len(lsFrames)

	if ignorePadding:
		numRangeStr = numRange(lsFrames)
	else:
		numRangeStr = numRange(lsFrames, padding=padding)

	if contiguous:
		chunks = numRangeStr.split(', ')
		if len(chunks) > 1:
			for chunk in chunks:
				contiguousChunkLs = numList(chunk, quiet=True)
				if framenumber in contiguousChunkLs:
					numRangeStr = chunk
					numFrames = len(contiguousChunkLs)

	#verbose.print_("%d frame sequence detected: %s" %(numFrames, numRangeStr))

	#return lsFrames
	return (path, prefix, numRangeStr, ext, numFrames)