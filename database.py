#!/usr/bin/python

# database.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Interface for the Render Queue database.


import glob
import json
import os
import re
import time
import uuid

# Import custom modules
import oswrapper
# import sequence
# import ui_template as UI


# class RenderJob(UI.SettingsData):
# 	""" Class to hold an render job.
# 	"""


# class RenderTask(UI.SettingsData):
# 	""" Class to hold an individual task.
# 	"""


class RenderQueue():
	""" Class to manage the render queue database.
	"""
	def __init__(self, location=None):
		self.debug = False
		if self.debug:
			self.io_reads = 0
			self.io_writes = 0

		self.db_root = location
		self.db_jobs = os.path.join(location, 'jobs')
		self.db_tasks = os.path.join(location, 'tasks')
		self.db_queued = os.path.join(location, 'tasks', 'queued')
		self.db_completed = os.path.join(location, 'tasks', 'completed')
		self.db_failed = os.path.join(location, 'tasks', 'failed')
		self.db_workers = os.path.join(location, 'workers')
		print("Connecting to render queue database at: " + location)
		# Create folder structure (could be more dynamic)
		oswrapper.createDir(self.db_jobs)
		oswrapper.createDir(self.db_tasks)
		oswrapper.createDir(self.db_queued)
		oswrapper.createDir(self.db_completed)
		oswrapper.createDir(self.db_failed)
		oswrapper.createDir(self.db_workers)


	def read(self, datafile):
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
		try:
			with open(datafile, 'w') as f:
				json.dump(data, f, indent=4)
				if self.debug:
					self.io_writes += 1
					print("[Database I/O] Write #%d: %s" %(self.io_writes, datafile))
			return True
		except:
			return False


	def newJob(self, **kwargs):
		""" Create a new render job and associated tasks.
			Generates a JSON file with the job UUID to hold data for the
			render job. Also generates a JSON file for each task. These are
			placed in the 'queued' subfolder ready to be picked up by workers.
		"""
		jobID = uuid.uuid4().hex  # Generate UUID
		kwargs['jobID'] = jobID

		# Write job data file
		datafile = os.path.join(self.db_jobs, '%s.json' %jobID)
		self.write(kwargs, datafile)

		# Write tasks and place in queue
		tasks = kwargs['tasks']
		for i in range(len(kwargs['tasks'])):
			taskdata = {}
			taskdata['jobID'] = jobID
			taskdata['taskNo'] = i
			taskdata['frames'] = tasks[i]
			# taskdata['command'] = kwargs['command']
			# taskdata['flags'] = kwargs['flags']

			datafile = os.path.join(self.db_queued, 
				'%s_%s.json' %(jobID, str(i).zfill(4)))
			self.write(taskdata, datafile)


	def deleteJob(self, jobID):
		""" Delete a render job and associated tasks.
			Searches for all JSON files with job UUID under the queue folder
			structure and deletes them. Also kills processes for tasks that
			are rendering.
		"""
		datafile = os.path.join(self.db_jobs, '%s.json' %jobID)
		oswrapper.recurseRemove(datafile)

		path = '%s/*/*/%s_*.json' %(self.db_root, jobID)
		for filename in glob.glob(path):
			if 'workers' in filename:
				# TODO: Deal nicely with tasks that are currently rendering
				print("Task %s currently rendering." %filename)
			oswrapper.recurseRemove(filename)

		return True


	def archiveJob(self, jobID):
		""" Archive a render job and associated tasks.
			Moves all files associated with a particular job UUID into a
			special archive folder.
		"""
		pass


	def requeueJob(self, jobID):
		""" Requeue a render job and associated tasks.
		"""
		#statuses = ['queued', 'working', 'completed', 'failed']
		path = '%s/*/*/%s_*.json' %(self.db_root, jobID)
		for filename in glob.glob(path):
			if 'queued' not in filename:
				oswrapper.move(filename, self.db_queued)


	def getJobs(self):
		""" Return a list of all jobs in the database.
		"""
		jobs = []
		path = '%s/jobs/*.json' %self.db_root
		for filename in glob.glob(path):
			jobs.append(self.read(filename))
		return jobs


	def getJob(self, jobID):
		""" Return a specific job.
		"""
		filename = os.path.join(self.db_jobs, '%s.json' %jobID)
		try:
			job = self.read(filename)
			return job
		except:
			return None


	def getJobDatafile(self, jobID):
		""" Return the path to the specified job's JSON data file.
		"""
		return os.path.join(self.db_jobs, '%s.json' %jobID)


	def getTasks(self, jobID):
		""" Read tasks for a specified job.
		"""
		tasks = []
		#statuses = ['queued', 'working', 'completed', 'failed']
		path = '%s/*/*/%s_*.json' %(self.db_root, jobID)
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
		path = '%s/%s_*.json' %(self.db_queued, jobID)
		for filename in glob.glob(path):
			taskdata = self.read(filename)
			tasks.append(taskdata)
		return tasks


	def getPriority(self, jobID):
		""" Get the priority of a render job.
		"""
		filename = os.path.join(self.db_jobs, '%s.json' %jobID)
		job = self.read(filename)
		return job['priority']


	def setPriority(self, jobID, priority):
		""" Set the priority of a render job.
		"""
		filename = os.path.join(self.db_jobs, '%s.json' %jobID)
		job = self.read(filename)
		if 0 <= priority <= 100:
			# Only write file if priority has changed
			if job['priority'] != priority:
				job['priority'] = priority
				self.write(job, filename)
		# elif priority == 0:
		# 	job['priorityold'] = job['priority']
		# 	job['priority'] = priority


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


	def updateTaskStatus(self, jobID, taskID, progress):
		""" Update task progress.
		"""
		pass
		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
		# if element is not None:
		# 	if "Working" in element.find('status').text: # only update progress for in-progress tasks
		# 		element.find('status').text = "[%d%%] Working" %progress
		# 		self.saveXML()


	def dequeueTask(self, jobID, taskID, workerID):
		"""
		"""
		#self.startTimeSec = time.time()  # Used to measure the time spent rendering
		#startTime = time.strftime(self.time_format)

		filename = os.path.join(self.db_queued, '%s_%s.json' %(jobID, str(taskID).zfill(4)))
		task = self.read(filename)
		task['startTime'] = time.time()
		task.pop('endTime', None)
		self.write(task, filename)

		dst = os.path.join(self.db_workers, workerID)

		oswrapper.move(filename, dst)


	def completeTask(self, jobID, taskID, worker=None, taskTime=0):
		""" Mark the specified task as 'Done'.
		"""
		path = '%s/*/*/%s_%s.json' %(self.db_root, jobID, str(taskID).zfill(4))
		for filename in glob.glob(path):
			if 'completed' not in filename:
				task = self.read(filename)
				if 'endTime' not in task:
					task['endTime'] = time.time()
				self.write(task, filename)

				oswrapper.move(filename, self.db_completed)

		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
		# if element is not None:
		# 	if element.find('status').text == "Done": # do nothing if status is 'Done'
		# 		return
		# 	# elif element.find('status').text == "Working": # do nothing if status is 'Working'
		# 	# 	return
		# 	else:
		# 		element.find('status').text = "Done"
		# 		element.find('worker').text = str(worker)
		# 		element.find('totalTime').text = str(taskTime)
		# 		self.saveXML()


	def failTask(self, jobID, taskID, worker=None, taskTime=0):
		""" Mark the specified task as 'Failed'.
		"""
		path = '%s/*/*/%s_%s.json' %(self.db_root, jobID, str(taskID).zfill(4))
		for filename in glob.glob(path):
			if 'failed' not in filename:
				task = self.read(filename)
				if 'endTime' not in task:
					task['endTime'] = time.time()
				self.write(task, filename)

				oswrapper.move(filename, self.db_failed)

		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
		# if element is not None:
		# 	if element.find('status').text == "Failed": # do nothing if status is 'Failed'
		# 		return
		# 	# elif element.find('status').text == "Working": # do nothing if status is 'Working'
		# 	# 	return
		# 	else:
		# 		element.find('status').text = "Failed"
		# 		element.find('worker').text = str(worker)
		# 		element.find('totalTime').text = str(taskTime)
		# 		self.saveXML()


	def requeueTask(self, jobID, taskID):
		""" Requeue the specified task, mark it as 'Queued'.
		"""
		path = '%s/*/*/%s_%s.json' %(self.db_root, jobID, str(taskID).zfill(4))
		for filename in glob.glob(path):
			if 'queued' not in filename:
				task = self.read(filename)
				task.pop('startTime', None)
				task.pop('endTime', None)
				self.write(task, filename)

				oswrapper.move(filename, self.db_queued)

		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
		# if element.find('status').text == "Queued": # do nothing if status is 'Queued'
		# 	return
		# # elif element.find('status').text == "Working": # do nothing if status is 'Working'
		# # 	return
		# else:
		# 	element.find('status').text = "Queued"
		# 	element.find('totalTime').text = ""
		# 	element.find('worker').text = ""
		# 	self.saveXML()


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
	# 		filename = os.path.join(self.db_queued, 
	# 			'%s_%s.json' %(jobID, str(taskID).zfill(4)))
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
	# 		oswrapper.recurseRemove(filename)

	# 	# Write new task
	# 	newtaskdata['frames'] = newframerange
	# 	datafile = os.path.join(self.db_queued, 
	# 		'%s_%s.json' %(jobID, str(taskIDs[0]).zfill(4)))
	# 	with open(datafile, 'w') as f:
	# 		json.dump(newtaskdata, f, indent=4)

	# 	return taskIDs[0]


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
		workerdir = os.path.join(self.db_workers, workerID)
		oswrapper.createDir(workerdir)
		datafile = os.path.join(workerdir, 'workerinfo.json')
		self.write(kwargs, datafile)


	def getWorkers(self):
		""" Return a list of workers in the database. Check if there's a task
			associated with it and add it to the dictionary.
		"""
		workers = []
		# Read data from each worker entry
		path = '%s/*/workerinfo.json' %self.db_workers
		for filename in glob.glob(path):
			# Check if the worker has a task
			workerdir = os.path.dirname(filename)
			workertaskpath = '%s/*_*json' %workerdir
			tasks = []
			status = ""
			for datafile in glob.glob(workertaskpath):
				task = self.read(datafile)
				job = self.getJob(task['jobID'])
				if job:
					status = "Rendering frame(s) %s from %s" %(task['frames'], job['jobName'])
			worker = self.read(filename)
			if status:
				worker['status'] = status
			workers.append(worker)

		return workers


	def getWorkerNames(self):
		""" Return a list of worker names in the database.
		"""
		workerNames = []
		# Read data from each worker entry
		path = '%s/*/workerinfo.json' %self.db_workers
		for filename in glob.glob(path):
			worker = self.read(filename)
			workerNames.append(worker['name'])

		return workerNames


	def getWorker(self, workerID):
		""" Get a specific worker.
		"""
		filename = os.path.join(self.db_workers, workerID, 'workerinfo.json')
		return self.read(filename)


	def getWorkerDatafile(self, workerID):
		""" Return the path to the specified worker's JSON data file.
		"""
		return os.path.join(self.db_workers, workerID, 'workerinfo.json')


	def deleteWorker(self, workerID):
		""" Delete a worker from the database.
		"""
		path = os.path.join(self.db_workers, workerID)
		oswrapper.recurseRemove(path)
		return True


	def getWorkerStatus(self, workerID):
		""" Get the status of the specified worker.
		"""
		datafile = os.path.join(self.db_workers, workerID, 'workerinfo.json')
		worker = self.read(datafile)
		return worker['status']


	def setWorkerStatus(self, workerID, status):
		""" Set the status of the specified worker.
		"""
		datafile = os.path.join(self.db_workers, workerID, 'workerinfo.json')
		worker = self.read(datafile)
		if worker['status'] != status:
			worker['status'] = status
			#print(worker['status'])
			self.write(worker, datafile)

