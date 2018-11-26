#!/usr/bin/python

# database.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2018
#
# Interface for the Render Queue database.


import glob
import json
import os
import uuid

# Import custom modules
import oswrapper
import sequence


# class RenderTask():
# 	""" Class to hold an individual task.
# 	"""


class RenderQueue():
	""" Class to manage the render queue database.
	"""
	def __init__(self):
		self.rq_database = 'queue'
		# try:
		# 	self.rq_database = os.environ['RQ_DATABASE']
		# except KeyError:
		# 	return None


	def newJob(self, **kwargs):
		""" Create a new render job and associated tasks.
			Generates a JSON file with the job UUID to hold data for the
			render job. Also generates a JSON file for each task. These are
			placed in the 'queued' subfolder ready to be picked up by workers.
		"""
		jobID = uuid.uuid4().hex  # generate UUID
		kwargs['jobID'] = jobID

		# Write job data file
		#datafile = 'queue/jobs/%s.json' %jobID
		datafile = '%s/jobs/%s.json' %(self.rq_database, jobID)
		with open(datafile, 'w') as json_file:
			json.dump(kwargs, json_file, indent=4)

		# Write tasks and place in queue
		tasks = kwargs['tasks']
		for i in range(len(kwargs['tasks'])):
			taskdata = {}
			taskdata['jobID'] = jobID
			taskdata['taskNo'] = i
			taskdata['frames'] = tasks[i]
			# taskdata['command'] = kwargs['command']
			# taskdata['flags'] = kwargs['flags']

			#datafile = 'queue/tasks/queued/%s_%s.json' %(jobID, str(i).zfill(4))
			datafile = '%s/tasks/queued/%s_%s.json' %(self.rq_database, jobID, str(i).zfill(4))
			with open(datafile, 'w') as json_file:
				json.dump(taskdata, json_file, indent=4)


	def deleteJob(self, jobID):
		""" Delete a render job and associated tasks.
			Searches for all JSON files with job UUID under the queue folder
			structure and deletes them. Also kills processes for tasks that
			are rendering.
		"""
		datafile = '%s/jobs/%s.json' %(self.rq_database, jobID)
		oswrapper.recurseRemove(datafile)


	def archiveJob(self, jobID):
		""" Archive a render job and associated tasks.
			Moves all files associated with a particular job UUID into a
			special archive folder.
		"""
		pass


	def getJobs(self):
		""" Read jobs.
		"""
		jobs = []
		path = '%s/jobs/*.json' %self.rq_database
		for filename in glob.glob(path):
			with open(filename, 'r') as f:
				jobs.append(json.load(f))
		return jobs


	def getTasks(self, jobID):
		""" Read tasks for a specified job.
		"""
		tasks = []
		#statuses = ['queued', 'working', 'completed', 'failed']
		path = '%s/*/*/%s_*.json' %(self.rq_database, jobID)
		for filename in glob.glob(path):
			if 'workers' in filename:
				status = 'Working'
			elif 'queued' in filename:
				status = 'Queued'
			elif 'completed' in filename:
				status = 'Done'
			elif 'failed' in filename:
				status = 'Failed'
			else:
				status = 'Unknown'
			with open(filename, 'r') as f:
				taskdata = json.load(f)
				taskdata['status'] = status
				tasks.append(taskdata)
		return tasks


	# def getJob(self, jobID):
	# 	""" Read job.
	# 	"""
	# 	datafile = 'queue/jobs/%s.json' %jobID
	# 	with open(datafile) as json_file:
	# 		data = json.load(json_file)
	# 	return data


	# def getValue(self, element, tag):
	# 	""" Return the value of 'tag' belonging to 'element'. - this is now in xmlData.py
	# 	"""
	# 	elem = element.find(tag)
	# 	if elem is not None:
	# 		text = elem.text
	# 		if text is not None:
	# 			return text

	# 	#return "" # return an empty string, not None, so value can be stored in an environment variable without raising an error


	def getPriority(self, jobID):
		""" Get the priority of a render job.
		"""
		return 0
		# element = self.root.find("./job[@id='%s']/priority" %jobID)
		# return int(element.text)


	def setPriority(self, jobID, priority):
		""" Set the priority of a render job.
		"""
		pass
		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/priority" %jobID)
		# if 0 <= priority <= 100:
		# 	element.text = str(priority)
		# self.saveXML()


	def setStatus(self, jobID, status):
		""" Set the status of a render job.
		"""
		pass
		# #self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/status" %jobID)
		# #print "Set status", element
		# if element.text == str(status): # do nothing if status hasn't changed
		# 	return
		# else:
		# 	element.text = str(status)
		# 	self.saveXML()


	def dequeueJob(self):
		""" Find a job with the highest priority that isn't paused or
			completed.
		"""
		# self.loadXML(quiet=True) # reload XML data

		# for priority in range(100, 0, -1): # iterate over range starting at 100 and ending at 1 (zero is omitted)
		# 	elements = self.root.findall("./job/[priority='%s']" %priority) # get all <job> elements with the highest priority
		# 	if elements is not None:
		# 		for element in elements:
		# 			#print "[Priority %d] Job ID %s: %s (%s)" %(priority, element.get('id'), element.find('name').text, element.find('status').text),
		# 			if element.find('status').text != "Done":
		# 				if element.find("task/[status='Queued']") is not None: # does this job have any queued tasks?
		# 					#print "This will do, let's render it!"
		# 					return element
		# 			#print "Not yet, keep searching..."

		return None


	def dequeueTask(self, jobID, hostID):
		""" Dequeue the next queued task belonging to the specified job, mark
			it as 'Working' (in-progress), and return the task ID and the
			frame range.
		"""
		return False, False
		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task/[status='Queued']" %jobID) # get the first <task> element with 'Queued' status
		# #element = self.root.find("./job[@id='%s']/task" %jobID) # get the first <task> element
		# if element is not None:
		# 	#if element.find('status').text is not "Done":
		# 	element.find('status').text = "Working"
		# 	element.find('worker').text = str(hostID)
		# 	self.saveXML()
		# 	return element.get('id'), element.find('frames').text

		# else:
		# 	return False, False


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


	def completeTask(self, jobID, taskID, hostID=None, taskTime=0):
		""" Mark the specified task as 'Done'.
		"""
		pass
		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
		# if element is not None:
		# 	if element.find('status').text == "Done": # do nothing if status is 'Done'
		# 		return
		# 	# elif element.find('status').text == "Working": # do nothing if status is 'Working'
		# 	# 	return
		# 	else:
		# 		element.find('status').text = "Done"
		# 		element.find('worker').text = str(hostID)
		# 		element.find('totalTime').text = str(taskTime)
		# 		self.saveXML()


	def failTask(self, jobID, taskID, hostID=None, taskTime=0):
		""" Mark the specified task as 'Failed'.
		"""
		pass
		# self.loadXML(quiet=True) # reload XML data
		# element = self.root.find("./job[@id='%s']/task[@id='%s']" %(jobID, taskID)) # get the <task> element
		# if element is not None:
		# 	if element.find('status').text == "Failed": # do nothing if status is 'Failed'
		# 		return
		# 	# elif element.find('status').text == "Working": # do nothing if status is 'Working'
		# 	# 	return
		# 	else:
		# 		element.find('status').text = "Failed"
		# 		element.find('worker').text = str(hostID)
		# 		element.find('totalTime').text = str(taskTime)
		# 		self.saveXML()


	def requeueTask(self, jobID, taskID):
		""" Requeue the specified task, mark it as 'Queued'.
		"""
		pass
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

