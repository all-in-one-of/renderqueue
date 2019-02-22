#!/usr/bin/python

# database.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Interface for the Render Queue database.
# Manages jobs, tasks and workers.


import glob
import json
import os
import re
import time
import uuid

# Import custom modules
import common
import oswrapper
# import sequence


class RenderQueue():
	""" Class to manage the render queue database.
	"""
	def __init__(self, location=None):
		self.time_format = "%Y/%m/%d %H:%M:%S"

		self.debug = False
		if self.debug:
			self.io_reads = 0
			self.io_writes = 0

		# Set up paths
		self.db = {}
		self.db['root'] = location
		self.db['jobs'] = os.path.join(location, 'jobs')
		self.db['tasks'] = os.path.join(location, 'tasks')
		self.db['queued'] = os.path.join(location, 'tasks', 'queued')
		self.db['completed'] = os.path.join(location, 'tasks', 'completed')
		self.db['failed'] = os.path.join(location, 'tasks', 'failed')
		self.db['workers'] = os.path.join(location, 'workers')
		self.db['logs'] = os.path.join(location, 'logs')
		print("Connecting to render queue database at: %s" %location)

		# Check database is valid, if not create folder structure 
		if not self.validate():
			self.create()

		# Set up logging
		logfile = os.path.join(self.db['logs'], 'renderqueue.log')
		self.queue_logger = common.setup_logger('queue_logger', logfile)


	def validate(self):
		""" Check the database is valid (directory structure exists).
		"""
		for directory in self.db.values():
			if not os.path.isdir(directory):
				return False
		return True


	def create(self):
		""" Create the database directory structure.
		"""
		for directory in self.db.values():
			oswrapper.createDir(directory)


	def read(self, datafile):
		""" Read values from a JSON file and return as a dictionary.
		"""
		try:
			with open(datafile, 'r') as f:
				data = json.load(f)
				if self.debug:
					self.io_reads += 1
					print("[Database I/O] Read #%d: %s" %(self.io_reads, datafile))
			return data
		except:
			return {}


	def write(self, data, datafile):
		""" Write values from a dictionary to a JSON file.
		"""
		try:
			with open(datafile, 'w') as f:
				json.dump(data, f, indent=4)
				if self.debug:
					self.io_writes += 1
					print("[Database I/O] Write #%d: %s" %(self.io_writes, datafile))
			return True
		except:
			return False


	########
	# JOBS #
	########

	def newJob(self, **kwargs):
		""" Create a new render job and associated tasks.
			Generates a JSON file with the job UUID to hold data for the
			render job. Also generates a JSON file for each task. These are
			placed in the 'queued' subfolder ready to be picked up by workers.
		"""
		jobID = uuid.uuid4().hex  # Generate UUID
		kwargs['jobID'] = jobID

		# Write job data file
		datafile = os.path.join(self.db['jobs'], '%s.json' %jobID)
		self.write(kwargs, datafile)

		# Write tasks and place in queue
		tasks = kwargs['tasks']
		for i in range(len(tasks)):
			taskdata = {}
			taskdata['jobID'] = jobID
			taskdata['taskNo'] = i
			taskdata['frames'] = tasks[i]
			# taskdata['command'] = kwargs['command']
			# taskdata['flags'] = kwargs['flags']

			datafile = os.path.join(self.db['queued'], 
				'%s_%s.json' %(jobID, str(i).zfill(4)))
			self.write(taskdata, datafile)

		self.queue_logger.info("Created job %s" %jobID)
		self.queue_logger.info("Created %d task(s) for job %s" %(len(tasks), jobID))

		# Set up job logging
		# logger_name = '%s_logger' %jobID
		# logfile = os.path.join(self.db['logs'], '%s.log' %jobID)
		# print(logger_name, logfile)
		# self.job_logger = common.setup_logger(logger_name, logfile)


	def deleteJob(self, jobID):
		""" Delete a render job and associated tasks.
			Searches for all JSON files with job UUID under the queue folder
			structure and deletes them. Also kills processes for tasks that
			are rendering.
		"""
		datafile = os.path.join(self.db['jobs'], '%s.json' %jobID)
		oswrapper.remove(datafile)

		path = '%s/*/*/%s_*.json' %(self.db['root'], jobID)
		for filename in glob.glob(path):
			if 'workers' in filename:
				# TODO: Deal nicely with tasks that are currently rendering
				print("Task %s currently rendering." %filename)
			oswrapper.remove(filename)  # add return value for check

		self.queue_logger.info("Deleted job %s" %jobID)

		return True


	def archiveJob(self, jobID):
		""" Archive a render job and associated tasks.
			Moves all files associated with a particular job UUID into a
			special archive folder. Perhaps don't archive tasks?
		"""
		pass


	def requeueJob(self, jobID):
		""" Requeue a render job and associated tasks.
		"""
		#statuses = ['queued', 'working', 'completed', 'failed']
		path = '%s/*/*/%s_*.json' %(self.db['root'], jobID)
		for filename in glob.glob(path):
			if 'queued' not in filename:
				oswrapper.move(filename, self.db['queued'])
				self.queue_logger.info("Requeued job %s" %jobID)


	def getJobs(self):
		""" Return a list of all jobs in the database.
		"""
		jobs = []
		path = '%s/jobs/*.json' %self.db['root']
		for filename in glob.glob(path):
			jobs.append(self.read(filename))
		return jobs


	def getJob(self, jobID):
		""" Return a specific job.
		"""
		filename = os.path.join(self.db['jobs'], '%s.json' %jobID)
		try:
			job = self.read(filename)
			return job
		except:
			return None


	def getJobDatafile(self, jobID):
		""" Return the path to the specified job's JSON data file.
		"""
		return os.path.join(self.db['jobs'], '%s.json' %jobID)


	def getPriority(self, jobID):
		""" Get the priority of a render job.
		"""
		filename = os.path.join(self.db['jobs'], '%s.json' %jobID)
		job = self.read(filename)
		return job['priority']


	def setPriority(self, jobID, priority):
		""" Set the priority of a render job.
		"""
		filename = os.path.join(self.db['jobs'], '%s.json' %jobID)
		job = self.read(filename)
		if 0 <= priority <= 100:
			# Only write file if priority has changed
			if job['priority'] != priority:
				job['priority'] = priority
				self.write(job, filename)
				self.queue_logger.info("Set priority of job %s to %d" %(jobID, priority))
		# elif priority == 0:
		# 	job['priorityold'] = job['priority']
		# 	job['priority'] = priority


	def getTasks(self, jobID):
		""" Read tasks for a specified job.
		"""
		tasks = []
		#statuses = ['queued', 'working', 'completed', 'failed']
		path = '%s/*/*/%s_*.json' %(self.db['root'], jobID)
		for filename in glob.glob(path):
			taskdata = self.read(filename)

			if 'workers' in filename:
				workerID = os.path.split(os.path.dirname(filename))[-1]
				worker = self.getWorker(workerID)
				taskdata['worker'] = worker['name']
				taskdata['status'] = 'Rendering on %s' %worker['name']
			elif 'queued' in filename:
				taskdata['status'] = 'Queued'
			elif 'completed' in filename:
				taskdata['status'] = 'Done'
			elif 'failed' in filename:
				taskdata['status'] = 'Failed'
			else:
				taskdata['status'] = 'Unknown'

			tasks.append(taskdata)

		return tasks


	def getQueuedTasks(self, jobID):
		""" Return all queued tasks for a specified job.
		"""
		tasks = []
		path = '%s/%s_*.json' %(self.db['queued'], jobID)
		for filename in glob.glob(path):
			taskdata = self.read(filename)
			tasks.append(taskdata)
		return tasks


	def getTaskToRender(self):
		""" Find a task to render by finding the highest priority job with
			tasks queued and return its first queued task.
		"""
		from operator import itemgetter

		# Get jobs and sort by priority, then submit time (FIFO)
		jobs = self.getJobs()
		if jobs:
			jobs.sort(key=itemgetter('submitTime'))
			for job in sorted(jobs, key=itemgetter('priority'), reverse=True):
				if job['priority'] > 0:  # Ignore paused jobs

					# Get queued tasks, sort by ID, return first result
					tasks = self.getQueuedTasks(job['jobID'])
					if tasks:
						return sorted(tasks, key=itemgetter('taskNo'))[0]

		# No suitable tasks found
		return None


	#########
	# TASKS #
	#########

	def getTaskID(self, jobID, taskNo):
		""" Return the task ID: a string made up of the job UUID appended with
			the four-digit padded task number.
			e.g. da60928a4a0746cebf56e5c3283e513b_0001
		"""
		return '%s_%s' %(jobID, str(taskNo).zfill(4))


	def getTaskLog(self, jobID, taskNo):
		""" Return the path to the specified task's log file.
		"""
		logfile = '%s.log' %self.getTaskID(jobID, taskNo)
		return os.path.join(self.db['logs'], logfile)


	# def updateTaskStatus(self, jobID, taskID, progress):
	# 	""" Update task progress.
	# 	"""
	# 	self.loadXML(quiet=True) # reload XML data
	# 	element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
	# 	if element is not None:
	# 		if "Working" in element.find('status').text: # only update progress for in-progress tasks
	# 			element.find('status').text = "[%d%%] Working" %progress
	# 			self.saveXML()


	def dequeueTask(self, jobID, taskNo, workerID):
		""" Dequeue a task by moving it from the 'queued' folder to the
			worker's folder. At the same time we store the current time in
			order to keep a running timer. It's important that we do not
			modify the file until it is inside the worker folder, to prevent
			data corruption.
		"""
		taskID = self.getTaskID(jobID, taskNo)

		filename = os.path.join(self.db['queued'], '%s.json' %taskID)
		dst_dir = os.path.join(self.db['workers'], workerID)

		if oswrapper.move(filename, dst_dir):
			dst_filename = os.path.join(dst_dir, '%s.json' %taskID)
			task = self.read(dst_filename)
			task['startTime'] = time.time()
			task.pop('endTime', None)
			self.write(task, dst_filename)
			self.queue_logger.info("Worker %s dequeued task %s" %(workerID, taskID))
			return True
		else:
			self.queue_logger.warning("Worker %s failed to dequeue task %s" %(workerID, taskID))
			return False


	def completeTask(self, jobID, taskNo, workerID=None, taskTime=0):
		""" Mark the specified task as 'Done'.
		"""
		taskID = self.getTaskID(jobID, taskNo)

		path = '%s/*/*/%s.json' %(self.db['root'], taskID)
		for filename in glob.glob(path):
			if 'completed' not in filename:
				# task = self.read(filename)
				# if 'endTime' not in task:
				# 	task['endTime'] = time.time()
				# self.write(task, filename)

				if oswrapper.move(filename, self.db['completed']):
					self.queue_logger.info("Worker %s completed task %s" %(workerID, taskID))
					return True
				else:
					return False


	def failTask(self, jobID, taskNo, workerID=None, taskTime=0):
		""" Mark the specified task as 'Failed'.
		"""
		taskID = self.getTaskID(jobID, taskNo)

		path = '%s/*/*/%s.json' %(self.db['root'], taskID)
		for filename in glob.glob(path):
			if 'failed' not in filename:
				# task = self.read(filename)
				# if 'endTime' not in task:
				# 	task['endTime'] = time.time()
				# self.write(task, filename)

				if oswrapper.move(filename, self.db['failed']):
					self.queue_logger.info("Worker %s failed task %s" %(workerID, taskID))
					return True
				else:
					return False


	def requeueTask(self, jobID, taskNo):
		""" Requeue the specified task, mark it as 'Queued'.
		"""
		taskID = self.getTaskID(jobID, taskNo)

		path = '%s/*/*/%s.json' %(self.db['root'], taskID)
		for filename in glob.glob(path):
			if 'queued' not in filename:
				# task = self.read(filename)
				# task.pop('startTime', None)
				# task.pop('endTime', None)
				# self.write(task, filename)

				if oswrapper.move(filename, self.db['queued']):
					self.queue_logger.info("Requeued task %s" %taskID)
					return True
				else:
					return False


	# def combineTasks(self, jobID, taskIDs):
	# 	""" Combine the specified tasks.
	# 	"""
	# 	print(jobID, taskIDs)
	# 	if len(taskIDs) < 2:
	# 		print("Error: Need at least two tasks to combine.")
	# 		return None

	# 	tasks_to_delete = []
	# 	frames = []
	# 	for taskID in taskIDs:
	# 		filename = os.path.join(self.db['queued'], 
	# 			'%s.json' %self.getTaskID(jobID, taskNo))
	# 		with open(filename, 'r') as f:
	# 			taskdata = json.load(f)
	# 		frames += sequence.numList(taskdata['frames'])
	# 		if taskID == taskIDs[0]:  # Use data from first task in list
	# 			newtaskdata = taskdata
	# 		else:
	# 			tasks_to_delete.append(filename)  # Mark other tasks for deletion

	# 	# Sanity check on new frame range
	# 	try:
	# 		start, end = sequence.numRange(frames).split("-")
	# 		start = int(start)
	# 		end = int(end)
	# 		assert start<end, "Error: Start frame must be smaller than end frame."
	# 		newframerange = "%s-%s" %(start, end)
	# 		print("New frame range: " + newframerange)
	# 	except:
	# 		print("Error: Cannot combine tasks - combined frame range must be contiguous.")
	# 		return None

	# 	# Delete redundant tasks
	# 	for filename in tasks_to_delete:
	# 		oswrapper.remove(filename)

	# 	# Write new task
	# 	newtaskdata['frames'] = newframerange
	# 	datafile = os.path.join(self.db['queued'], 
	# 		'%s_%s.json' %(jobID, str(taskIDs[0]).zfill(4)))
	# 	with open(datafile, 'w') as f:
	# 		json.dump(newtaskdata, f, indent=4)

	# 	return taskIDs[0]


	###########
	# WORKERS #
	###########

	def newWorker(self, **kwargs):
		""" Create a new worker.
		"""
		workerID = uuid.uuid4().hex  # Generate UUID
		kwargs['id'] = workerID

		# Check name is unique...
		# Look for numeric suffix in brackets, replace with n hashes
		name_ls = []
		for name in self.getWorkerNames():
			suffix_pattern = re.compile(r" \([0-9]*\)$")
			suffix = re.findall(suffix_pattern, name)
			if suffix:
				num_suffix = re.findall(r"\d+", str(suffix))
				num_suffix = int(num_suffix[0])
			else:
				num_suffix = 0

			hashes = "#" * num_suffix
			new_name = re.sub(suffix_pattern, hashes, name)
			name_ls.append(new_name)

		# Keep appending hashes until name is unique
		name = kwargs['name']
		while name in name_ls:
			name += "#"

		# Replace hashes with number
		num_suffix = name.count('#')
		kwargs['name'] = re.sub(r"\#+$", " (%d)" %num_suffix, name)

		# Create worker folder and data file
		workerdir = os.path.join(self.db['workers'], workerID)
		oswrapper.createDir(workerdir)
		datafile = os.path.join(workerdir, 'workerinfo.json')
		self.write(kwargs, datafile)
		self.queue_logger.info("Created worker %s (%s)" 
			%(kwargs['name'], workerID))


	def getWorkers(self):
		""" Return a list of workers in the database. Check if there's a task
			associated with it and add it to the dictionary.
		"""
		workers = []

		# Read data from each worker entry
		path = '%s/*/workerinfo.json' %self.db['workers']
		for filename in glob.glob(path):
			status = "Idle"

			# Check if the worker has a task
			workertaskpath = '%s/*_*.json' %os.path.dirname(filename)
			for datafile in glob.glob(workertaskpath):
				task = self.read(datafile)
				job = self.getJob(task['jobID'])
				if job:
					status = "Rendering frame(s) %s from %s" %(task['frames'], job['jobName'])

			# Determine status of worker
			worker = self.read(filename)
			if not worker['enable']:
				status = "Disabled"

			# Check if remote workers have checked in recently
			if worker['online']:
				timeSinceLastOnline = time.time() - worker['online']
				# Mark as offline if not seen for 60 seconds
				# DISABLED as system clocks not synced
				# if timeSinceLastOnline > 60:
				# 	status = "Offline"
			else:
				status = "Offline"

			worker['status'] = status
			workers.append(worker)

		return workers


	def getWorkerNames(self):
		""" Return a list of worker names in the database.
		"""
		workerNames = []

		# Read data from each worker entry
		path = '%s/*/workerinfo.json' %self.db['workers']
		for filename in glob.glob(path):
			worker = self.read(filename)
			workerNames.append(worker['name'])

		return workerNames


	def getWorkerDatafile(self, workerID):
		""" Return the path to the specified worker's JSON data file.
		"""
		return os.path.join(self.db['workers'], workerID, 'workerinfo.json')


	def getWorker(self, workerID):
		""" Get a specific worker.
		"""
		return self.read(self.getWorkerDatafile(workerID))


	def deleteWorker(self, workerID):
		""" Delete a worker from the database.
		"""
		path = os.path.join(self.db['workers'], workerID)

		if oswrapper.remove(path)[0]:
			self.queue_logger.info("Deleted worker %s" %workerID)
			return True
		else:
			self.queue_logger.warning("Failed to delete worker %s" %workerID)
			return False


	def enableWorker(self, workerID):
		""" Enable the specified worker.
		"""
		datafile = self.getWorkerDatafile(workerID)
		worker = self.read(datafile)
		if worker['enable'] == False:
			worker['enable'] = True
			self.write(worker, datafile)
			self.queue_logger.info("Enabled worker %s (%s)" 
				%(worker['name'], workerID))


	def disableWorker(self, workerID):
		""" Disable the specified worker.
		"""
		datafile = self.getWorkerDatafile(workerID)
		worker = self.read(datafile)
		if worker['enable'] == True:
			worker['enable'] = False
			self.write(worker, datafile)
			self.queue_logger.info("Disabled worker %s (%s)" 
				%(worker['name'], workerID))


	def checkinWorker(self, workerID, hostname):
		""" Check in the local worker from the client.
		"""
		datafile = self.getWorkerDatafile(workerID)
		worker = self.read(datafile)
		worker['online'] = time.time() #time.strftime(self.time_format)
		self.write(worker, datafile)
		# self.queue_logger.info("Worker %s (%s) checked in from host %s" 
		# 	%(worker['name'], workerID, hostname))


	def checkoutWorker(self, workerID, hostname):
		""" Check out the local worker (mark as offline).
		"""
		datafile = self.getWorkerDatafile(workerID)
		worker = self.read(datafile)
		worker['online'] = False
		self.write(worker, datafile)
		# self.queue_logger.info("Worker %s (%s) checked out from host %s" 
		# 	%(worker['name'], workerID, hostname))


	# def getWorkerStatus(self, workerID):
	# 	""" Get the status of the specified worker.
	# 	"""
	# 	worker = self.read(self.getWorkerDatafile(workerID))
	# 	return worker['status']


	# def setWorkerStatus(self, workerID, status):
	# 	""" Set the status of the specified worker.
	# 	"""
	# 	datafile = self.getWorkerDatafile(workerID)
	# 	worker = self.read(datafile)
	# 	if worker['status'] != status:
	# 		worker['status'] = status
	# 		self.write(worker, datafile)
	# 		self.queue_logger.info("Set status of worker %s (%s) to %s" 
	# 			%(worker['name'], workerID, status))

