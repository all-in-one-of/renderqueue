#!/usr/bin/python

# submit_deadline.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Render Submitter (Deadline)
# This module contains functions specifically for submitting jobs to Deadline.


import os
import re
import sys
import tempfile
import traceback

# Import custom modules
import oswrapper

# temporary assignment - store in prefs file e.g. submitter.deadlinecommand
os.environ['DEADLINECMDVERSION'] = "/opt/Thinkbox/Deadline9/bin/deadlinecommand"


def get_pools():
	""" Get Deadline pools and return in a list.
	"""
	try:
		pools = oswrapper.execute([os.environ['DEADLINECMDVERSION'], '-pools'])[1]
		return pools.splitlines()
	except:
		print("Warning: Could not retrieve Deadline pools.")
		return None


def get_groups():
	""" Get Deadline groups and return in a list.
	"""
	try:
		groups = oswrapper.execute([os.environ['DEADLINECMDVERSION'], '-groups'])[1]
		return groups.splitlines()
	except:
		print("Warning: Could not retrieve Deadline groups.")
		return None


def temp_file(scene, suffix=""):
	""" Return a path to a config file stored in a temp dir according to OS.
		The filename is derived from the 'scene' parameter.
	"""
	if os.path.isfile(scene):
		scene_file = os.path.basename(scene)
		settings_file = oswrapper.sanitize(scene_file, replace='_') + suffix

		return os.path.join(tempfile.gettempdir(), settings_file)

	else:
		return False


def generate_job_info_file(**kwargs):
	""" Generate job submission info file.
	"""
	if kwargs['renderLayer']:
		job_info_file_suffix = "_%s_deadlineJobInfo.txt" % kwargs['renderLayer']
	else:
		job_info_file_suffix = "_deadlineJobInfo.txt"
	job_info_file = temp_file(kwargs['scene'], suffix=job_info_file_suffix)

	with open(job_info_file, 'w') as fh:
		fh.write("Plugin=%s\n" % kwargs['plugin'])

		if kwargs['renderLayer']:
			fh.write("Name=%s - %s\n" % (kwargs['jobName'], kwargs['renderLayer']))
			fh.write("BatchName=%s\n" % kwargs['jobName'])
		else:
			fh.write("Name=%s\n" % kwargs['jobName'])

		fh.write("Comment=%s\n" % kwargs['comment'])
		fh.write("Frames=%s\n" % kwargs['frames'])
		fh.write("ChunkSize=%s\n" % kwargs['taskSize'])
		fh.write("Pool=%s\n" % kwargs['pool'])
		fh.write("SecondaryPool=%s\n" % kwargs['secondaryPool'])
		fh.write("Group=%s\n" % kwargs['group'])
		fh.write("Priority=%s\n" % kwargs['priority'])
		fh.write("UserName=%s\n" % kwargs['username'])

		if kwargs['priority'] == 0:
			fh.write("InitialStatus=Suspended\n")

		try:
			if kwargs['renderLayer']:  # Single layer output
				output_path = kwargs['output'][kwargs['renderLayer']]
				fh.write("OutputDirectory0=%s\n" % output_path[0])
				fh.write("OutputFilename0=%s\n" % output_path[1])
			else:  # Multiple layer outputs
				for i, layer in enumerate(kwargs['output']):
					output_path = kwargs['output'][layer]
					fh.write("OutputDirectory%d=%s\n" % (i, output_path[0]))
					fh.write("OutputFilename%d=%s\n" % (i, output_path[1]))
		except:
			print("Warning: Could not determine render output path(s).")

		for i, key in enumerate(kwargs['envVars']):
			try:
				fh.write("EnvironmentKeyValue%d=%s=%s\n" % (i, key, os.environ[key]))
			except KeyError:
				print("Warning: environment variable '%s' not set." % key)

		# fh.write("ExtraInfo0=%s\n" %os.environ['JOB'])
		# fh.write("ExtraInfo1=%s\n" %os.environ['SHOT'])

	return job_info_file


def generate_plugin_info_file(**kwargs):
	""" Generate plugin submission info file.
	"""
	if kwargs['renderLayer']:
		plugin_info_file_suffix = "_%s_deadlinePluginInfo.txt" % kwargs['renderLayer']
	else:
		plugin_info_file_suffix = "_deadlinePluginInfo.txt"

	plugin_info_file = temp_file(kwargs['scene'], suffix=plugin_info_file_suffix)
	with open(plugin_info_file, 'w') as fh:

		# Command Line -------------------------------------------------------
		if kwargs['plugin'] == "CommandLine":
			pass
			# fh.write("Executable=%s\n" % kwargs['executable'])
			# fh.write("Arguments=%s\n" % kwargs['flags'])
			# fh.write("Shell=Default\n")
			# fh.write("ShellExecute=False\n")
			# fh.write("StartupDirectory=%s\n" % kwargs['startupDir'])

		# Maya ---------------------------------------------------------------
		elif kwargs['plugin'] == "MayaBatch":
			fh.write("Version=%s\n" % kwargs['version'])
			fh.write("Build=64bit\n")
			fh.write("Camera=%s\n" % kwargs['camera'])
			fh.write("Renderer=%s\n" % kwargs['renderer'])
			fh.write("StrictErrorChecking=1\n")
			fh.write("ProjectPath=%s\n" % kwargs['mayaProject'])
			fh.write("OutputFilePath=%s\n" % kwargs['outputFilePath'])
			fh.write("OutputFilePrefix=%s\n" % kwargs['outputFilePrefix'])
			fh.write("SceneFile=%s\n" % kwargs['scene'])
			fh.write("UseLegacyRenderLayers=%s\n" % (not kwargs['useRenderSetup']))
			if kwargs['renderLayer']:
				fh.write("UsingRenderLayers=1\n")
				fh.write("RenderLayer=%s\n" % kwargs['renderLayer'])

		# Houdini ------------------------------------------------------------
		elif kwargs['plugin'] == "Houdini":
			fh.write("Version=%s\n" % kwargs['version'])
			fh.write("SceneFile=%s\n" % kwargs['scene'])
			fh.write("OutputDriver=%s\n" % kwargs['outputDriver'])

		# Nuke ---------------------------------------------------------------
		elif kwargs['plugin'] == "Nuke":
			fh.write("BatchMode=True\n")
			# fh.write("BatchModeIsMovie=%s\n" % kwargs['isMovie'])
			fh.write("NukeX=%s\n" % kwargs['nukeX'])
			fh.write("Version=%s\n" % kwargs['version'])
			fh.write("SceneFile=%s\n" % kwargs['scene'])
			if kwargs['renderLayers']:
				fh.write("WriteNode=%s\n" % kwargs['renderLayer'])
				fh.write("BatchModeIsMovie=%s\n" % kwargs['isMovie'])

	return plugin_info_file


def generate_batch_file(scene, job_info_file_list, plugin_info_file_list):
	""" Generate batch job submission file given corresponding lists of job
		and plugin info files.
	"""
	batch_submission_file = temp_file(scene, suffix="_deadlineBatchArgs.txt")
	with open(batch_submission_file, 'w') as fh:
		fh.write("-SubmitMultipleJobs\n")
		for i in range(len(job_info_file_list)):
			fh.write("-job\n")
			fh.write("%s\n" % job_info_file_list[i])
			fh.write("%s\n" % plugin_info_file_list[i])

	return batch_submission_file


def submit_job(**kwargs):
	""" Submit job to Deadline.
	"""
	cmd_output = ""
	result_msg = ""

	# if kwargs is not None:
	# 	for key, value in kwargs.items():
	# 		print("%24s = %s" %(key, value))

	try:
		if kwargs['renderLayers']:  # Batch submission -----------------------
			# Generate submission info files
			num_jobs = 0
			job_info_file_list = []
			plugin_info_file_list = []
			for render_layer in re.split(r',\s*', kwargs['renderLayers']): # may be better to pass as list
				kwargs['renderLayer'] = render_layer
				# kwargs['isMovie'] = False
				job_info_file = generate_job_info_file(**kwargs)
				job_info_file_list.append(job_info_file)
				plugin_info_file = generate_plugin_info_file(**kwargs)
				plugin_info_file_list.append(plugin_info_file)
				num_jobs += 1

			# Generate batch file
			batch_submission_file = generate_batch_file(
				kwargs['scene'], 
				job_info_file_list,
				plugin_info_file_list)

			# Execute deadlinecommand
			cmd_result, cmd_output = oswrapper.execute([os.environ['DEADLINECMDVERSION'], batch_submission_file])
			if cmd_result:
				result_msg = "Successfully submitted %d job(s) to Deadline." % num_jobs

		else:  # Single job submission ---------------------------------------
			# Generate submission info files
			kwargs['renderLayer'] = None
			job_info_file = generate_job_info_file(**kwargs)
			plugin_info_file = generate_plugin_info_file(**kwargs)

			# Execute deadlinecommand
			cmd_result, cmd_output = oswrapper.execute([os.environ['DEADLINECMDVERSION'], job_info_file, plugin_info_file])
			if cmd_result:
				result_msg = "Successfully submitted job to Deadline."

		if cmd_result:
			result = True
			print(cmd_output) #.decode())
			print(result_msg)
		else:
			raise RuntimeError(cmd_output)

	except:  # Submission failed ---------------------------------------------
		result = False
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_exception(exc_type, exc_value, exc_traceback)
		result_msg = "Failed to submit job to Deadline."
		print(result_msg)
		if (exc_type == RuntimeError) and cmd_output:
			result_msg += "\n" + cmd_output
		else:
			result_msg += "\nCheck console output for details."
		#output_str = "Either the Deadline executable could not be found, or the submission info files could not be written."
		#output_str = traceback.format_exception_only(exc_type, exc_value)[0]

	return result, result_msg
