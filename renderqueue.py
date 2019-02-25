#!/usr/bin/python

# renderqueue.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Render Queue Manager
# A UI for managing a queue of distributed rendering jobs.
# Possible names:
# U-Queue, U-Farm, UQ, FQ, FarQ


import datetime
import getpass
#import json
#import logging
import math
import os
import socket
import sys
import time

from Qt import QtCore, QtGui, QtWidgets
import icons_rc
import ui_template as UI

# Import custom modules
import about
import database
import oswrapper
#import outputparser
import sequence
#import verbose
import worker


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

VENDOR = ""
COPYRIGHT = "(c) 2015-2019"
DEVELOPERS = "Mike Bonnington"
os.environ['RQ_VERSION'] = "0.2.1"

# Set window title and object names
WINDOW_TITLE = "Render Queue"
WINDOW_OBJECT = "RenderQueueUI"

# Set the UI and the stylesheet
UI_FILE = 'renderqueue.ui'
STYLESHEET = 'style.qss'  # Set to None to use the parent app's stylesheet

# Other options
PREFS_FILE = 'config/userprefs.json'
STORE_WINDOW_GEOMETRY = True


# ----------------------------------------------------------------------------
# Begin main application class
# ----------------------------------------------------------------------------

class RenderQueueApp(QtWidgets.QMainWindow, UI.TemplateUI):
	""" Main application class.
	"""
	def __init__(self, parent=None):
		super(RenderQueueApp, self).__init__(parent)
		self.parent = parent

		# Set up logging (TEST)
		# task_log_path = oswrapper.absolutePath('$RQ_DATADIR/test.log')
		# logging.basicConfig(level=logging.DEBUG, filename=task_log_path, filemode="a+",
		#                     format="%(asctime)-15s %(levelname)-8s %(message)s")

		# Define global variables
		self.time_format = "%Y/%m/%d %H:%M:%S"
		self.localhost = socket.gethostname()
		self.ip_address = socket.gethostbyname(self.localhost)
		self.selection = []
		self.expandedJobs = {}

		self.setupUI(window_object=WINDOW_OBJECT, 
					 window_title=WINDOW_TITLE, 
					 ui_file=UI_FILE, 
					 stylesheet=STYLESHEET, 
					 prefs_file=PREFS_FILE, 
					 store_window_geometry=STORE_WINDOW_GEOMETRY)  # re-write as **kwargs ?

		# Set window flags
		self.setWindowFlags(QtCore.Qt.Window)
		self.setWindowTitle("%s - %s" %(WINDOW_TITLE, self.localhost.split(".")[0]))

		# Set other Qt attributes
		#self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

		#verbose.registerStatusBar(self.ui.statusBar)  # only in standalone?

		# Get tree view column header indices
		self.queue_header = self.getHeaderIndices(self.ui.queue_treeWidget)
		self.workers_header = self.getHeaderIndices(self.ui.workers_treeWidget)

		# Restore widget state
		self.restoreView()

		# Define standard UI colours
		self.colBlack     = QtGui.QColor("#0a0a0a")  # black
		self.colWhite     = QtGui.QColor("#ffffff")  # white
		self.colBorder    = QtGui.QColor("#222222")  # dark grey
		self.colNormal    = self.col['text']  #QtGui.QColor("#cccccc")  # light grey
		self.colActive    = QtGui.QColor(self.prefs.getValue('user', 'colorActive', "#00ffbb"))
		self.colInactive  = QtGui.QColor(self.prefs.getValue('user', 'colorInactive', "#808080"))
		self.colCompleted = QtGui.QColor(self.prefs.getValue('user', 'colorSuccess', "#00bbff"))
		self.colError     = QtGui.QColor(self.prefs.getValue('user', 'colorFailure', "#ff5533"))

		# Instantiate render queue class and load data
		# databaseLocation = oswrapper.translatePath(
		# 	self.prefs.getValue('user', 'databaseLocation', './rq_database'), 
		# 	'L:', '/Volumes/Library', '/mnt/Library')
		try:
			databaseLocation = oswrapper.translatePath(
				self.prefs.getValue('user', 'databaseLocation'), 
				'L:', '/Volumes/Library', '/mnt/Library')
		except:
			databaseLocation = None

		# If database location is not set or doesn't exist, prompt user to set
		# the location.
		if (not databaseLocation) or (not os.path.isdir(databaseLocation)):
			# print("ERROR: Database not found: %s" %databaseLocation)
			dialog_title = "Database not found"
			dialog_msg = "The render queue database could not be found. Please set the database location in the settings dialog."
			self.promptDialog(dialog_msg, dialog_title, conf=True)
			self.openSettings()

			# databaseLocation = self.folderDialog('.')
			# self.prefs.setValue('user', 'databaseLocation', databaseLocation)
			# self.prefs.write()

		self.rq = database.RenderQueue(databaseLocation)

		# Temporarily disable some actions until properly implemented
		#self.ui.actionResetView.setEnabled(False)
		self.ui.actionResubmit.setEnabled(False)
		self.ui.actionRemote.setEnabled(False)
		self.ui.actionSplit.setEnabled(False)

		# --------------------------------------------------------------------
		# Connect signals & slots
		# --------------------------------------------------------------------

		self.ui.queue_treeWidget.itemSelectionChanged.connect(self.updateSelection)
		self.ui.queue_treeWidget.expanded.connect(self.storeExpandedJobs)
		self.ui.queue_treeWidget.collapsed.connect(self.storeExpandedJobs)
		self.ui.queue_treeWidget.header().sectionResized.connect(lambda logicalIndex, oldSize, newSize: self.updateColumn(logicalIndex, oldSize, newSize))  # Resize progress indicator
		self.ui.queue_treeWidget.header().sectionClicked.connect(self.sortTasks)

		# Queue menu & toolbar
		self.ui.actionSubmitJob.triggered.connect(self.launchRenderSubmit)
		self.ui.actionSubmitJob.setIcon(self.iconSet('document-new.svg'))
		self.ui.submitJob_toolButton.clicked.connect(self.launchRenderSubmit)
		self.ui.submitJob_toolButton.setIcon(self.iconSet('document-new.svg'))

		self.ui.actionRefresh.triggered.connect(self.refreshViews)
		self.ui.actionRefresh.setIcon(self.iconSet('view-refresh.svg'))
		self.ui.refresh_toolButton.clicked.connect(self.refreshViews)
		self.ui.refresh_toolButton.setIcon(self.iconSet('view-refresh.svg'))

		self.ui.actionResetView.triggered.connect(self.resetView)

		self.ui.actionResizeColumns.triggered.connect(self.resizeColumns)

		self.ui.actionSettings.triggered.connect(self.openSettings)
		self.ui.actionSettings.setIcon(self.iconSet('configure.svg'))
		self.ui.settings_toolButton.clicked.connect(self.openSettings)
		self.ui.settings_toolButton.setIcon(self.iconSet('configure.svg'))

		self.ui.actionAbout.triggered.connect(self.about)
		self.ui.actionAbout.setIcon(self.iconSet('help-about.svg'))

		self.ui.actionExit.triggered.connect(self.close)
		self.ui.actionExit.setIcon(self.iconSet('application-exit.svg'))

		# Job menu & toolbar
		self.ui.actionEditJob.triggered.connect(self.editJob)
		self.ui.actionEditJob.setIcon(self.iconSet('edit.svg'))

		self.ui.actionBrowse.triggered.connect(self.launchRenderBrowser)
		self.ui.actionBrowse.setIcon(self.iconSet('view-preview.svg'))

		self.ui.actionBrowseFolder.triggered.connect(self.openRenderFolder)
		self.ui.actionBrowseFolder.setIcon(self.iconSet('icon_folder.png'))

		# self.ui.actionViewJobLog.triggered.connect(self.viewJobLog)  # not yet implemented
		# self.ui.actionViewJobLog.setIcon(self.iconSet('log.svg'))

		self.ui.actionPause.triggered.connect(lambda *args: self.changePriority(0, absolute=True))  # this lambda function is what's causing the multiple windows issue, no idea why though
		self.ui.actionPause.setIcon(self.iconSet('media-playback-pause.svg'))
		self.ui.jobPause_toolButton.clicked.connect(lambda *args: self.changePriority(0, absolute=True))  # this lambda function is what's causing the multiple windows issue, no idea why though
		self.ui.jobPause_toolButton.setIcon(self.iconSet('media-playback-pause.svg'))

		self.ui.actionResume.setIcon(self.iconSet('media-playback-start.svg'))
		#self.ui.actionResume.triggered.connect(lambda *args: self.changePriority(0, absolute=True))  # this lambda function is what's causing the multiple windows issue, no idea why though

		self.ui.actionStop.triggered.connect(self.stopJob)
		self.ui.actionStop.setIcon(self.iconSet('process-stop.svg'))
		self.ui.jobStop_toolButton.clicked.connect(self.stopJob)
		self.ui.jobStop_toolButton.setIcon(self.iconSet('process-stop.svg'))

		self.ui.actionDelete.triggered.connect(self.deleteJob)
		self.ui.actionDelete.setIcon(self.iconSet('edit-delete.svg'))
		self.ui.jobDelete_toolButton.clicked.connect(self.deleteJob)
		self.ui.jobDelete_toolButton.setIcon(self.iconSet('edit-delete.svg'))

		#self.ui.actionResubmit.triggered.connect(self.resubmitJob)  # not yet implemented
		self.ui.actionResubmit.setIcon(self.iconSet('resubmit.png'))
		#self.ui.jobResubmit_toolButton.clicked.connect(self.resubmitJob)  # not yet implemented
		#self.ui.jobResubmit_toolButton.setIcon(self.iconSet('gtk-convert'))

		self.ui.jobPriority_slider.sliderMoved.connect(lambda value: self.changePriority(value)) # this lambda function is what's causing the multiple windows issue, no idea why though
		self.ui.jobPriority_slider.sliderReleased.connect(self.updatePriority)

		# Task menu & toolbar
		self.ui.actionViewTaskLog.triggered.connect(self.viewTaskLog)  # not yet implemented
		# self.ui.actionViewTaskLog.setIcon(self.iconSet('log.svg'))

		self.ui.actionCompleteTask.triggered.connect(self.completeTask)
		self.ui.actionCompleteTask.setIcon(self.iconSet('dialog-ok-apply.svg'))
		self.ui.taskComplete_toolButton.clicked.connect(self.completeTask)
		self.ui.taskComplete_toolButton.setIcon(self.iconSet('dialog-ok-apply.svg'))

		self.ui.actionFailTask.triggered.connect(self.failTask)
		self.ui.actionFailTask.setIcon(self.iconSet('paint-none.svg'))

		self.ui.actionRequeueTask.triggered.connect(self.requeueTask)
		self.ui.actionRequeueTask.setIcon(self.iconSet('gtk-convert.svg'))
		self.ui.taskRequeue_toolButton.clicked.connect(self.requeueTask)
		self.ui.taskRequeue_toolButton.setIcon(self.iconSet('gtk-convert.svg'))

		#self.ui.actionCombine.triggered.connect(self.combineTasks)  # not yet implemented

		#self.ui.actionSplit_task.triggered.connect(self.splitTasks)  # not yet implemented

		# Worker menu & toolbar
		self.ui.actionNewWorker.triggered.connect(self.newWorker)
		self.ui.actionNewWorker.setIcon(self.iconSet('list-add.svg'))

		self.ui.actionEditWorker.triggered.connect(self.editWorker)
		self.ui.actionEditWorker.setIcon(self.iconSet('edit.svg'))

		self.ui.actionStartWorker.triggered.connect(self.enableWorkers)
		#self.ui.actionStartWorker.setIcon(self.iconSet('media-playback-start.svg'))

		self.ui.actionStopWorker.triggered.connect(self.disableWorkers)
		#self.ui.actionStopWorker.setIcon(self.iconSet('media-playback-stop.svg'))

		#self.ui.actionStopWorkerImmediately.triggered.connect(self.cancelRender)
		#self.ui.actionStopWorkerImmediately.setIcon(self.iconSet('paint-none.svg'))

		self.ui.actionDeleteWorker.triggered.connect(self.deleteWorker)
		self.ui.actionDeleteWorker.setIcon(self.iconSet('edit-delete.svg'))

		# self.ui.actionViewWorkerLog.triggered.connect(self.viewWorkerLog)  # not yet implemented
		# self.ui.actionViewWorkerLog.setIcon(self.iconSet('log.svg'))

		self.ui.actionPing.triggered.connect(self.ping)

		self.ui.actionRemote.triggered.connect(self.rdesktop)
		self.ui.actionRemote.setIcon(self.iconSet('computer.png'))

		# self.ui.actionDequeue.triggered.connect(self.dequeue)  # functionality removed

		# Add context menu items to worker control tool button
		# self.ui.workerControl_toolButton.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
		self.ui.workerControl_toolButton.setIcon(self.iconSet('computer.png'))

		# self.actionWorkerStart = QtWidgets.QAction("Start Worker", None)
		# self.actionWorkerStart.triggered.connect(self.enableWorkers)
		# self.ui.workerControl_toolButton.addAction(self.actionWorkerStart)

		# self.actionWorkerStop = QtWidgets.QAction("Stop Worker", None)
		# self.actionWorkerStop.triggered.connect(self.disableWorkers)
		# self.ui.workerControl_toolButton.addAction(self.actionWorkerStop)

		# self.actionKillTask = QtWidgets.QAction("Stop Worker Immediately and Kill Current Task", None)
		# # self.actionKillTask.triggered.connect(self.killRenderProcess)
		# self.ui.workerControl_toolButton.addAction(self.actionKillTask)

		# self.actionWorkerContinueAfterTask = QtWidgets.QAction("Continue after current task completion", None)
		# self.actionWorkerContinueAfterTask.setCheckable(True)
		# self.ui.workerControl_toolButton.addAction(self.actionWorkerContinueAfterTask)

		# self.actionWorkerStopAfterTask = QtWidgets.QAction("Stop after current task completion", None)
		# self.actionWorkerStopAfterTask.setCheckable(True)
		# self.ui.workerControl_toolButton.addAction(self.actionWorkerStopAfterTask)

		workerControlAfterTaskGroup = QtWidgets.QActionGroup(self)
		workerControlAfterTaskGroup.addAction(self.actionContinueAfterTask)
		workerControlAfterTaskGroup.addAction(self.actionStopWorkerAfterTask)
		self.actionContinueAfterTask.setChecked(True)

		# Set up context menus for render queue and workers tree widgets
		self.ui.queue_treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.ui.queue_treeWidget.customContextMenuRequested.connect(self.openContextMenu)
		self.ui.workers_treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.ui.workers_treeWidget.customContextMenuRequested.connect(self.openContextMenu)

		self.updateSelection()


	def launchRenderSubmit(self, **kwargs):
		""" Launch Render Submitter window.
		"""
		import submit
		try:
			self.renderSubmitUI.display(**kwargs)
		except AttributeError:
			self.renderSubmitUI = submit.RenderSubmitUI(parent=self)
			self.renderSubmitUI.display(**kwargs)


	def getOutputDir(self):
		""" Get render output directory.
			Some horrible hackery going on here.
		"""
		header = self.queue_header
		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has no parent then it must be a top level item, and
				# therefore also a job
				if not item.parent():
					jobID = item.text(header['ID'])
					job = self.rq.getJob(jobID)
					output = job['output']
					mayaproj = job['mayaProject']
					frameRange = item.text(header['Frames'])

		except ValueError:
			pass

		# hackery to get this functional...
		os.environ['MAYADIR'] = mayaproj
		for key in output.keys():
			directory = oswrapper.absolutePath(output[key][0])
			directory = os.path.split(directory)[:-1][0]
		print(directory)

		return directory, frameRange


	def launchRenderBrowser(self):
		""" Launch Render Browser window.
		"""
		directory, frameRange = self.getOutputDir()

		import browser
		try:
			self.renderBrowserUI.display(
				directory=directory, frameRange=frameRange)
		except AttributeError:
			self.renderBrowserUI = browser.RenderBrowserUI(parent=self)
			self.renderBrowserUI.display(
				directory=directory, frameRange=frameRange)


	def openRenderFolder(self):
		""" Open a file explorer to browse the render output directory.
		"""
		directory = self.getOutputDir()[0]
		os.system('xdg-open %s' %directory)


	def openSettings(self):
		""" Open settings dialog.
		"""
		import settings
		self.settingsEditor = settings.SettingsDialog(parent=self)
		result = self.settingsEditor.display(
			settingsType=WINDOW_TITLE, 
			categoryLs=['user', 'database'], 
			startPanel=None, 
			datafile='config/userprefs.json', 
			inherit=None, 
			autoFill=False)

		if result:  # Dialog accepted
			self.prefs.read()
			self.refreshViews()  # Update view to refresh colours


	def ping(self):
		""" Ping the selected worker's IP address.
			Ideally this should run on its own thread to prevent locking the
			UI.
		"""
		header = self.workers_header

		try:
			for item in self.ui.workers_treeWidget.selectedItems():
				workerName = item.text(header['Name'])
				workerID = item.text(header['ID'])
				workerIP = item.text(header['IP Address'])
				status = item.text(header['Status'])

				args = ['ping', '-c', '1', workerIP]
				# args = ['ping', '-n', '1', workerIP]  # Windows
				result, output = oswrapper.execute(args)
				if result == True:
					print("%s is Online" %workerName)
					print(output)
				else:
					print("%s is Offline" %workerName)
					print(output)
					#self.rq.setWorkerStatus(workerID, "Offline")

		except ValueError:
			pass


	# def pingRemote(self):
	# 	""" Automatically mark remote workers as offline if they do not
	# 		respond to a ping.
	# 		This function is called by a timer.
	# 		Ideally this should run on its own thread to prevent locking the
	# 		UI.
	# 	"""
	# 	header = self.workers_header

	# 	#print("ping")
	# 	try:
	# 		for item in self.ui.workers_treeWidget.selectedItems():
	# 			workerID = item.text(header['ID'])
	# 			workerIP = item.text(header['IP Address'])
	# 			workerType = item.text(header['Type'])
	# 			status = item.text(header['Status'])

	# 			if status != "Offline":  # Only ping online workers
	# 				if workerType == "Remote":  # Only remote workers
	# 					args = ['ping', '-c', '1', workerIP]
	# 					# args = ['ping', '-n', '1', workerIP]  # Windows
	# 					result, output = oswrapper.execute(args)

	# 					if not result: # != 0:
	# 						pass
	# 						#self.rq.setWorkerStatus(workerID, "Offline")

	# 	except ValueError:
	# 		pass


	def closeRemote(self):
		""" Close the remote client. Not yet implemented.
		"""
		print("close")


	def rdesktop(self):
		""" Connect to remote desktop (currently linux only).
		"""
		header = self.workers_header

		try:
			for item in self.ui.workers_treeWidget.selectedItems():
				ip = item.text(header['IP Address'])
				cmd = 'rdesktop -g 1920x1200 -x 0x80 -a 32 -u %s -KD %s' %(os.environ.get('IC_USERNAME', getpass.getuser()), ip)
				#os.system('rdesktop -g 1920x1200 -x 0x80 -a 32 -u vfx -p vfx -KD %s' %ip)
				print(cmd)
				os.system(cmd)

		except ValueError:
			pass


	def about(self):
		""" Show about dialog.
		"""
		info_ls = []
		sep = " | "
		for key, value in self.getInfo().items():
			if key in ['Environment', 'OS']:
				pass
			else:
				info_ls.append("{} {} ".format(key, value))
		info_str = sep.join(info_ls)

		about_msg = """
%s
v%s

Developers: %s
%s %s

%s
""" %(WINDOW_TITLE, os.environ['RQ_VERSION'], DEVELOPERS, COPYRIGHT, VENDOR, info_str)

		aboutDialog = about.AboutDialog(parent=self)
		aboutDialog.display(image='config/splash/scott-goodwill-408543-unsplash.jpg', message=about_msg)


	# @QtCore.Slot()
	def openContextMenu(self, position):
		""" Display right-click context menu for items in render queue and
			worker tree view widgets.
		"""
		level = -1  # Initialise with null value in case of empty queue
		menu = None
		indices = self.sender().selectedIndexes()
		if len(indices) > 0:
			level = 0
			index = indices[0]
			while index.parent().isValid():
				index = index.parent()
				level += 1

		# Select correct menu to display
		if self.sender() == self.ui.queue_treeWidget:
			if level == 0:  # Job
				menu = self.ui.menuJob
			elif level == 1:  # Task
				menu = self.ui.menuTask
		elif self.sender() == self.ui.workers_treeWidget:
			if level == 0:  # Worker
				menu = self.ui.menuWorker

		if menu:
			menu.exec_(self.sender().viewport().mapToGlobal(position))


	def restoreView(self):
		""" Restore and apply saved state of tree widgets.
		"""
		try:
			self.ui.splitter.restoreState(self.settings.value("splitterSizes")) #.toByteArray())
			self.ui.queue_treeWidget.header().restoreState(self.settings.value("renderQueueView")) #.toByteArray())
			self.ui.workers_treeWidget.header().restoreState(self.settings.value("workersView")) #.toByteArray())
		except:
			pass


	def resetView(self):
		""" Reset state of tree widgets to default.
		"""
		self.settings.remove("renderQueueView")
		self.settings.remove("workersView")
		#self.resetColumnWidth()


	# def resetColumnWidth(self):
	# 	""" Resize all columns of the specified widget to fit content.
	# 	"""
	# 	widgets = [self.ui.queue_treeWidget, self.ui.workers_treeWidget]

	# 	for widget in widgets:
	# 		width = widget.headerItem().defaultSectionSize()
	# 		for i in range(widget.columnCount()):
	# 			widget.setColumnWidth(i, width)


	def resizeColumns(self):
		""" Resize all columns of the specified widget to fit content.
		"""
		widgets = [self.ui.queue_treeWidget, self.ui.workers_treeWidget]

		for widget in widgets:
			for i in range(widget.columnCount()):
				widget.resizeColumnToContents(i)


	def getHeaderIndex(self, widget, text):
		""" Returns the column index number for the specified header text in
			the specified widget.
		"""
		for i in range(widget.columnCount()):
			if text == widget.headerItem().text(i):
				return i
		return -1


	def getHeaderIndices(self, widget):
		""" Returns a dictionary containing the column headers as keys and
			the index numbers as values for the specified widget. This gives
			a more robust way to reference data from tree widgets.
		"""
		col_headers = {}
		for i in range(widget.columnCount()):
			col_headers[widget.headerItem().text(i)] = i
		return col_headers


	def refreshViews(self):
		""" Clears and rebuilds the render queue and worker tree view widgets,
			populating with entries for render jobs and tasks.
		"""
		widgets = [self.ui.queue_treeWidget, self.ui.workers_treeWidget]

		# Instantiate render queue class and load data
		databaseLocation = oswrapper.translatePath(
			self.prefs.getValue('user', 'databaseLocation'), 
			'L:', '/Volumes/Library', '/mnt/Library')

		self.rq = database.RenderQueue(databaseLocation)

		# Set custom colours
		self.colActive    = QtGui.QColor(self.prefs.getValue('user', 'colorActive',   "#00ffbb"))
		self.colInactive  = QtGui.QColor(self.prefs.getValue('user', 'colorInactive', "#808080"))
		self.colCompleted = QtGui.QColor(self.prefs.getValue('user', 'colorSuccess',  "#00bbff"))
		self.colError     = QtGui.QColor(self.prefs.getValue('user', 'colorFailure',  "#ff5533"))

		for widget in widgets:
			# Clear widgets
			widget.clear()

			# Hide ID column(s)
			# id_col = self.getHeaderIndex(widget, 'ID')
			# widget.setColumnHidden(id_col, True)

		# Populate tree widget with render jobs and tasks
		self.updateQueueView()
		self.updateWorkerView()


	def updateQueueView(self):
		""" Update the render queue tree view widget with entries for render
			jobs and tasks.
			This function will refresh the view by updating the existing
			items, without completely rebuilding it.
		"""
		widget = self.ui.queue_treeWidget
		header = self.queue_header

		# Stop the widget from emitting signals
		widget.blockSignals(True)

		# Populate tree widget with render jobs
		jobs = self.rq.getJobs()
		if not jobs:
			return
		for job in jobs:

			# Set default job status
			jobStatus = "Queued"

			# Get the render job item or create it if it doesn't exist
			jobItem = self.getQueueItem(widget, widget.invisibleRootItem(), job['jobID'])

			# Fill columns with data
			jobItem.setText(header['Name'], job['jobName'])
			jobItem.setIcon(header['Name'], self.iconSet('app_icon_%s.png' %job['jobType'].lower()))
			jobItem.setText(header['ID'], job['jobID'])
			jobItem.setText(header['Type'], job['jobType'])
			jobItem.setText(header['Frames'], job['frames'])
			jobItem.setText(header['Status'], jobStatus)
			jobItem.setText(header['Priority'], str(job['priority']))
			jobItem.setText(header['User'], job['username'])
			jobItem.setText(header['Submitted'], job['submitTime'])

			# Initialise counters and timers
			jobTotalTimeSeconds = 0
			inProgressTaskCount = 0
			completedTaskCount = 0
			failedTaskCount = 0
			inProgressTaskFrameCount = 0
			completedTaskFrameCount = 0
			failedTaskFrameCount = 0
			if not job['frames'] or job['frames'] == 'Unknown':
				totalFrameCount = -1
			else:
				totalFrameCount = len(sequence.numList(job['frames']))

			# Populate render tasks
			tasks = self.rq.getTasks(job['jobID'])
			for task in tasks:

				# Get values from XML
				taskID = str(task['taskNo']).zfill(4)  # Must match padding format in database.py
				taskStatus = task['status']

				# Calculate elapsed time
				try:
					taskTotalTime = task['endTime'] - task['startTime']
				except KeyError:
					try:
						taskTotalTime = time.time() - task['startTime']
					except KeyError:
						taskTotalTime = 0

				try:
					taskWorker = task['worker']
				except KeyError:
					taskWorker = "None"

				# Get the render task item or create it if it doesn't exist
				taskItem = self.getQueueItem(widget, jobItem, taskID)

				# Fill columns with data
				taskItem.setText(header['Name'], "Task %d" %task['taskNo'])
				taskItem.setText(header['ID'], taskID)
				taskItem.setText(header['Frames'], task['frames'])
				taskItem.setText(header['Status'], taskStatus)

				# Calculate progress
				if task['frames'] == 'Unknown':
					if taskStatus.startswith("Rendering"):
						inProgressTaskCount += 1
						inProgressTaskFrameCount = -1
					if taskStatus == "Done":
						completedTaskCount += 1
						completedTaskFrameCount = -1
					# if taskStatus == "Failed":
					# 	failedTaskCount += 1
					# 	failedTaskFrameCount = -1
				else:
					taskFrameCount = len(sequence.numList(task['frames']))
					if taskStatus.startswith("Rendering"):
						inProgressTaskCount += 1
						inProgressTaskFrameCount += taskFrameCount
					if taskStatus == "Done":
						completedTaskCount += 1
						completedTaskFrameCount += taskFrameCount
					# if taskStatus == "Failed":
					# 	failedTaskCount += 1
					# 	failedTaskFrameCount += taskFrameCount

				# Colour the status text
				for col in range(widget.columnCount()):
					# taskItem.setForeground(col, QtGui.QBrush(self.colInactive))
					# if taskStatus == "Queued": # and taskWorker == self.localhost:
					# 	taskItem.setForeground(header['Status'], QtGui.QBrush(self.colInactive))
					# 	# taskItem.setIcon(header['Status'], self.nullIcon)
					if taskStatus.startswith("Rendering"): # and taskWorker == self.localhost:
						taskItem.setForeground(header['Status'], QtGui.QBrush(self.colActive))
						# taskItem.setIcon(header['Status'], self.readyIcon)
					elif taskStatus == "Done": # and taskWorker == self.localhost:
						taskItem.setForeground(header['Status'], QtGui.QBrush(self.colCompleted))
						#taskItem.setIcon(header['Status'], self.iconSet('dialog-ok-apply.svg'))
						# taskItem.setIcon(header['Status'], self.doneIcon)
					elif taskStatus == "Failed": # and taskWorker == self.localhost:
						taskItem.setForeground(header['Status'], QtGui.QBrush(self.colError))
						# taskItem.setIcon(header['Status'], self.errorIcon)
					else:
						taskItem.setForeground(header['Status'], QtGui.QBrush(self.colNormal))

				# Update timers
				try:
					totalTimeSeconds = float(taskTotalTime)  # Use float and round for millisecs
					jobTotalTimeSeconds += totalTimeSeconds
					totalTime = str(datetime.timedelta(seconds=int(totalTimeSeconds)))
				except (TypeError, ValueError):
					totalTime = None

				taskItem.setText(header['Clock'], totalTime)
				taskItem.setText(header['Worker'], taskWorker)
			# End task setup

			# Always sort tasks by ID (ignore column sort order)
			jobItem.sortChildren(header['ID'], QtCore.Qt.AscendingOrder)

			# Calculate job progress and update status
			colBg = self.colBlack
			colProgress = self.colCompleted
			#jobItem.setForeground(4, QtGui.QBrush(self.colWhite))
			if completedTaskFrameCount == 0:
				if inProgressTaskFrameCount == 0:
					jobStatus = "Queued"
				else:
					jobStatus = "[0%] Working"
			elif completedTaskFrameCount == totalFrameCount:
				jobStatus = "Done"
				#jobItem.setForeground(4, QtGui.QBrush(self.colBorder))
			else:
				percentComplete = (float(completedTaskFrameCount) / float(totalFrameCount)) * 100
				if inProgressTaskFrameCount == 0:
					jobStatus = "[%d%%] Waiting" %percentComplete
					colProgress = self.colInactive
				else:
					jobStatus = "[%d%%] Working" %percentComplete
					colProgress = self.colCompleted
				# if failedTaskCount == 0:
				# 	colBg = self.colBlack
				# else:
				# 	colBg = self.colError

			self.drawJobProgressIndicator(
				header['Status'], 
				jobItem, 
				completedTaskFrameCount, 
				failedTaskFrameCount, 
				inProgressTaskFrameCount, 
				totalFrameCount, 
				colProgress)

			# self.rq.setStatus(job['jobID'], jobStatus)  # Write to XML if status has changed
			jobItem.setText(header['Status'], jobStatus)

			# Calculate time taken
			try:
				jobTotalTime = str(datetime.timedelta(seconds=int(jobTotalTimeSeconds)))
			except (TypeError, ValueError):
				jobTotalTime = None

			jobItem.setText(header['Clock'], str(jobTotalTime))
			if inProgressTaskCount:
				jobItem.setText(header['Worker'], "[%d rendering]" %inProgressTaskCount)
			else:
				jobItem.setText(header['Worker'], "")
			jobItem.setText(header['Pool'], job['pool'])
			jobItem.setText(header['Comment'], job['comment'])

			# Attempt to restore expanded job items
			try:
				jobItem.setExpanded(self.expandedJobs[job['jobID']])
			except:
				pass

		# Re-enable signals
		widget.blockSignals(False)


	def updateWorkerView(self):
		""" Update the information in the worker view.
		"""
		widget = self.ui.workers_treeWidget
		header = self.workers_header

		# Stop the widget from emitting signals
		widget.blockSignals(True)

		# Populate tree widget with workers
		workers = self.rq.getWorkers()
		if not workers:
			return
		for worker in workers:

			# Get the worker item or create it if it doesn't exist
			workerItem = self.getQueueItem(widget, widget.invisibleRootItem(), worker['id'])

			# Name, ID and icon
			workerItem.setText(header['Name'], worker['name'])
			workerItem.setIcon(header['Name'], self.iconSet('computer.png'))
			workerItem.setText(header['ID'], worker['id'])

			# Check if workers are local or remote
			if worker['ip_address'] == self.ip_address:
				workerItem.setText(header['Type'], 'Local')

				# Check-in worker if it's local
				# Note this introduces a JSON write so not optimal
				self.rq.checkinWorker(worker['id'], self.localhost)
			else:
				workerItem.setText(header['Type'], 'Remote')

				# for col in range(widget.columnCount()):
				# 	workerItem.setForeground(col, QtGui.QBrush(self.colInactive))

			# Set worker status
			workerItem.setText(header['Status'], worker['status'])

			# Colour the status text
			if worker['status'].startswith("Rendering"):
				workerItem.setForeground(header['Status'], QtGui.QBrush(self.colActive))
			elif worker['status'] == "Disabled":
				workerItem.setForeground(header['Status'], QtGui.QBrush(self.colInactive))
			elif worker['status'] == "Offline":
				workerItem.setForeground(header['Status'], QtGui.QBrush(self.colError))
			else:
				workerItem.setForeground(header['Status'], QtGui.QBrush(self.colNormal))

			# Fill remaining columns
			workerItem.setText(header['Hostname'], worker['hostname'])
			workerItem.setText(header['IP Address'], worker['ip_address'])
			workerItem.setText(header['User'], worker['username'])
			#workerItem.setText(header['Clock'], worker['runningTime'])
			workerItem.setText(header['Pool'], worker['pool'])
			workerItem.setText(header['Comment'], worker['comment'])

		# Re-enable signals
		widget.blockSignals(False)

		#self.checkinLocalWorkers()


	def getQueueItem(self, widget, parent, itemID=None):
		""" Return the tree widget item identified by 'itemID' belonging to
			'parent'.
			If it doesn't exist, return a new item.
			If 'itemID' is not specified, return a list of all the child
			items.
		"""
		child_count = parent.childCount()

		# Return list of children
		if itemID is None:
			items = []
			for i in range(child_count):
				items.append(parent.child(i))
			return items

		# Return specified child
		else:
			for i in range(child_count):
				item = parent.child(i)
				id_col = self.getHeaderIndex(widget, 'ID')
				if item.text(id_col) == itemID:
					return item

			# Return a new item
			return QtWidgets.QTreeWidgetItem(parent)


	def drawJobProgressIndicator(self, col, jobItem, 
		completedTaskFrameCount, failedTaskFrameCount, 
		inProgressTaskFrameCount, totalFrameCount, 
		colProgress):
		""" Draw a pixmap progress bar to represent the progress of a job.
		"""
		border = 1
		width = self.ui.queue_treeWidget.columnWidth(col)
		height = self.ui.queue_treeWidget.rowHeight(self.ui.queue_treeWidget.indexFromItem(jobItem))
		barWidth = width - (border*2)
		barHeight = height - (border*2)
		completedRatio = float(completedTaskFrameCount) / float(totalFrameCount)
		# failedRatio = float(failedTaskFrameCount) / float(totalFrameCount)
		inProgressRatio = float(inProgressTaskFrameCount) / float(totalFrameCount)
		completedLevel = math.ceil(completedRatio*barWidth)
		# failedLevel = math.ceil(failedRatio*barWidth)
		inProgressLevel = math.ceil((completedRatio+inProgressRatio)*barWidth)

		image = QtGui.QPixmap(width, height)

		qp = QtGui.QPainter()
		qp.begin(image)
		pen = QtGui.QPen()
		pen.setStyle(QtCore.Qt.NoPen)
		qp.setPen(pen)
		qp.setBrush(self.colBorder)  # Draw border
		qp.drawRect(0, 0, width, height)
		qp.setBrush(self.colBlack)  # Draw background
		qp.drawRect(border, border, barWidth, barHeight)
		qp.setBrush(self.colActive.darker())  # Draw in-progress bar
		qp.drawRect(border, border, inProgressLevel, barHeight)
		qp.setBrush(colProgress.darker())  # Draw completed level bar
		qp.drawRect(border, border, completedLevel, barHeight)
		# qp.setBrush(self.colError.darker())  # Draw failed level bar
		# qp.drawRect(border, border, failedLevel, barHeight)
		qp.end()

		#jobItem.setBackground(col, image)  # PyQt5 doesn't like this
		jobItem.setBackground(col, QtGui.QBrush(image))  # Test with Qt4/PySide
		#jobItem.setForeground(col, QtGui.QBrush(self.colWhite))


	# @QtCore.Slot()
	def updateColumn(self, logicalIndex, oldSize, newSize):
		""" Update the progress indicator when the column is resized.
		"""
		#print "Column %s resized from %s to %s pixels" %(logicalIndex, oldSize, newSize)

		if logicalIndex == self.getHeaderIndex(self.ui.queue_treeWidget, 'Status'):
			# jobItems = self.getQueueItem(self.ui.queue_treeWidget.invisibleRootItem())
			# for jobItem in jobItems:
			# 	self.drawJobProgressIndicator(jobItem, 0, 0, 100, self.colInactive)

			self.updateQueueView()


	# @QtCore.Slot()
	def storeExpandedJobs(self):
		""" Store the expanded status of all jobs.
		"""
		header = self.queue_header
		root = self.ui.queue_treeWidget.invisibleRootItem()
		for i in range(root.childCount()):
			jobItem = root.child(i)
			jobID = jobItem.text(header['ID'])
			self.expandedJobs[jobID] = jobItem.isExpanded()
		# print(self.expandedJobs)


	# @QtCore.Slot()
	def sortTasks(self):
		""" Sort all tasks by ID, regardless of sort column. Called whenever
			the user resizes a column of the render queue tree view widget.
		"""
		header = self.queue_header
		root = self.ui.queue_treeWidget.invisibleRootItem()
		for i in range(root.childCount()):
			jobItem = root.child(i)
			jobItem.sortChildren(header['ID'], QtCore.Qt.AscendingOrder)


	def updateSelection(self):
		""" Store the current selection.
			Only allow jobs OR tasks to be selected, not both.
			Update the toolbar and menus based on the selection.
		"""
		widget = self.ui.queue_treeWidget
		header = self.queue_header

		self.selection = []  # Clear selection
		selectionType = None
		sameJob = True
		frames = []

		for item in widget.selectedItems():

			if item.parent():  # Task is selected
				currentItem = widget.currentItem()
				if selectionType == "Job":
					self.selection = []
					widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
					widget.clearSelection()
					widget.setCurrentItem(currentItem)
				else:
					selectionType = "Task"
					widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
					id_col = header['ID']
					jobTaskID = item.parent().text(id_col), int(item.text(id_col))
					self.selection.append(jobTaskID)

					if jobTaskID[0] == self.selection[0][0]:
						try:
							frames += sequence.numList(item.text(header['Frames']), quiet=True)
						except:
							pass
					else:
						sameJob = False

					self.ui.job_frame.setEnabled(False)
					self.ui.task_frame.setEnabled(True)
					self.ui.menuJob.setEnabled(False)
					self.ui.menuTask.setEnabled(True)

			else:  # Job is selected
				currentItem = widget.currentItem()
				if selectionType == "Task":
					self.selection = []
					widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
					widget.clearSelection()
					widget.setCurrentItem(currentItem)
				else:
					selectionType = "Job"
					widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
					jobTaskID = item.text(header['ID']), -1
					self.selection.append(jobTaskID)

					self.ui.job_frame.setEnabled(True)
					self.ui.task_frame.setEnabled(False)
					self.ui.menuJob.setEnabled(True)
					self.ui.menuTask.setEnabled(False)

		if not self.selection:  # Nothing is selected
			self.ui.job_frame.setEnabled(False)
			self.ui.task_frame.setEnabled(False)
			self.ui.menuJob.setEnabled(False)
			self.ui.menuTask.setEnabled(False)
			self.ui.statusBar.clearMessage()

		else:
			# Check for contiguous frame range selection
			try:
				start, end = sequence.numRange(frames).split("-")
				start = int(start)
				end = int(end)
				# assert start<end, "Error: Start frame must be smaller than end frame."
				contiguous_frame_range = "%s-%s" %(start, end)
			except:
				contiguous_frame_range = None

			# Print status message
			count = len(self.selection)
			# if selectionType == "Job":
			if self.selection[0][1] == -1:
				message = "%d job(s) selected" %count
			# elif selectionType == "Task":
			else:
				if count == 1:
					message = "Task %s selected" %self.selection[0][1]
				else:
					message = "%d tasks selected" %count
			if selectionType == "Task" and count > 1 and sameJob and contiguous_frame_range:
				message += ", frames %s" %contiguous_frame_range
				# self.ui.actionCombine.setEnabled(True) # Re-enable when implementing this feature
			else:
				self.ui.actionCombine.setEnabled(False)
			#verbose.message("%d %s selected." %(count, verbose.pluralise(selectionType, count).lower()))
			self.ui.statusBar.showMessage(message + ".")

		# Disable submit button if shot is not set (temporary)
		# try:
		# 	os.environ['SHOT']
		# 	self.ui.submitJob_toolButton.setEnabled(True)
		# except KeyError:
		# 	self.ui.submitJob_toolButton.setEnabled(False)


	def stopJob(self):
		""" Stops selected render job(s). All tasks currently rendering will
			be stopped immediately.
		"""
		header = self.queue_header

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has no parent then it must be a top level item, and
				# therefore also a job
				if not item.parent():
					jobID = item.text(header['ID'])
					self.rq.requeueJob(jobID)

			self.changePriority(0, absolute=True)  # Pause job(s)

			#self.updateQueueView()

		except ValueError:
			pass


	def deleteJob(self):
		""" Removes selected render job(s) from the database and updates the
			view.
		"""
		header = self.queue_header

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has no parent then it must be a top level item, and
				# therefore also a job
				if not item.parent():
					jobID = item.text(header['ID'])

					# Remove item from view
					if self.rq.deleteJob(jobID):
						self.ui.queue_treeWidget.takeTopLevelItem(self.ui.queue_treeWidget.indexOfTopLevelItem(item))
						#verbose.message("Job ID %s deleted." %jobID)
					#else:
					#	verbose.warning("Job ID %s cannot be deleted while in progress." %jobID)

			#self.updateQueueView()

		except ValueError:
			pass


	def deleteWorker(self):
		""" Removes selected worker(s) from the database and updates the view.
		"""
		header = self.workers_header

		if self.promptDialog("Are you sure?", "Delete worker(s)"):
			try:
				for item in self.ui.workers_treeWidget.selectedItems():
					workerID = item.text(header['ID'])

					# Remove item from view
					if self.rq.deleteWorker(workerID):
						self.ui.workers_treeWidget.takeTopLevelItem(self.ui.workers_treeWidget.indexOfTopLevelItem(item))
					# 	verbose.message("Job ID %s deleted." %jobID)
					# else:
					# 	verbose.warning("Job ID %s cannot be deleted while in progress." %jobID)

				#self.updateQueueView()

			except ValueError:
				pass



	def editJob(self):
		""" Edit selected render job(s).
			Currently just opens a text editor to edit the JSON file, in lieu
			of a proper editor UI (currently linux only).
		"""
		header = self.queue_header

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has no parent then it must be a top level item, and
				# therefore also a job
				if not item.parent():
					jobID = item.text(header['ID'])
					os.system('xdg-open %s' %self.rq.getJobDatafile(jobID))

			#self.updateWorkerView()

		except ValueError:
			pass


	def editWorker(self):
		""" Edit selected worker(s).
			Currently just opens a text editor to edit the JSON file, in lieu
			of a proper editor UI (currently linux only).
		"""
		header = self.workers_header

		try:
			for item in self.ui.workers_treeWidget.selectedItems():
				workerID = item.text(header['ID'])
				os.system('xdg-open %s' %self.rq.getWorkerDatafile(workerID))

			#self.updateWorkerView()

		except ValueError:
			pass


	def changePriority(self, amount=0, absolute=False):
		""" Changes priority of the selected render.
			This function is called with 'absolute=False' when the
			'Reprioritise' slider is dragged.
			And 'absolute=True' when we want to set the priority directly,
			e.g. when a job is paused.
		"""
		header = self.queue_header

		self.timerUpdateView.stop()  # Don't update the view when dragging the slider

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has no parent then it must be a top level item, and
				# therefore also a job
				if not item.parent():
					jobID = item.text(header['ID'])
					minPriority = 0
					maxPriority = 100

					if absolute:
						newPriority = amount
					else:
						currentPriority = self.rq.getPriority(jobID)
						newPriority = currentPriority+amount

					if newPriority <= minPriority:
						item.setText(header['Priority'], str(minPriority))
					elif newPriority >= maxPriority:
						item.setText(header['Priority'], str(maxPriority))
					else:
						item.setText(header['Priority'], str(newPriority))

					if absolute:
						self.updatePriority()

		except ValueError:
			pass


	def updatePriority(self):
		""" Read the the changed priority value(s) from the UI and store in
			the database.
			This function is called when the 'Reprioritise' slider is
			released, or when we want to set the priority directly.
		"""
		header = self.queue_header

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has no parent then it must be a top level item, and
				# therefore also a job
				if not item.parent():
					jobID = item.text(header['ID'])
					priority = int(item.text(header['Priority']))
					self.rq.setPriority(jobID, priority)

			self.updateQueueView()

		except ValueError:
			pass

		self.ui.jobPriority_slider.setValue(0)  # Reset priority slider to zero when released
		self.timerUpdateView.start()  # Restart the timer to periodically update the view


	# def resubmitJob(self):
	# 	""" Resubmit selected job(s) to render queue.
	# 	"""
	# 	try:
	# 		for item in self.ui.queue_treeWidget.selectedItems():
	# 			if not item.parent(): # if item has no parent then it must be a top level item, and therefore also a job

	# 				jobName = self.rq.getValue(item, 'name')
	# 				jobType = self.rq.getValue(item, 'type')
	# 				priority = self.rq.getValue(item, 'priority')
	# 				frames = self.rq.getValue(item, 'frames')
	# 				taskSize = self.rq.getValue(item, 'taskSize')

	# 				mayaScene = self.rq.getValue(item, 'mayaScene')
	# 				mayaProject = self.rq.getValue(item, 'mayaProject')
	# 				mayaFlags = self.rq.getValue(item, 'mayaFlags')
	# 				mayaRenderCmd = self.rq.getValue(item, 'mayaRenderCmd')

	# 				taskList = []

	# 				genericOpts = jobName, jobType, priority, frames, taskSize
	# 				mayaOpts = mayaScene, mayaProject, mayaFlags, mayaRenderCmd

	# 				self.rq.newJob(genericOpts, mayaOpts, taskList, os.environ['IC_USERNAME'], time.strftime(self.time_format))

	# 	except ValueError:
	# 		pass


	def viewTaskLog(self):
		""" View the log for the selected task(s).
		"""
		header = self.queue_header

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has parent then it must be a subitem, and therefore
				# also a task
				if item.parent():
					jobID = item.parent().text(header['ID'])
					taskID = int(item.text(header['ID']))
					os.system('xdg-open %s' %self.rq.getTaskLog(jobID, taskID))

		except ValueError:
			pass


	def completeTask(self):
		""" Mark the selected task as completed.
		"""
		self.setTaskStatus("Completed")


	def failTask(self):
		""" Mark the selected task as failed.
		"""
		self.setTaskStatus("Failed")


	def requeueTask(self):
		""" Requeue the selected task.
		"""
		self.setTaskStatus("Queued")


	def setTaskStatus(self, status):
		""" Mark the selected task as completed, failed, or queued.
		"""
		header = self.queue_header

		jobTaskIDs = []  # This will hold a tuple containing (job id, task id)

		try:
			for item in self.ui.queue_treeWidget.selectedItems():
				# If item has parent then it must be a subitem, and therefore
				# also a task
				if item.parent():
					jobTaskID = item.parent().text(
						header['ID']), int(item.text(header['ID']))
					jobTaskIDs.append(jobTaskID)

			for jobTaskID in jobTaskIDs:
				if status == "Queued":
					self.rq.requeueTask(jobTaskID[0], jobTaskID[1])
				elif status == "Completed":
					self.rq.completeTask(jobTaskID[0], jobTaskID[1], taskTime=0)
				elif status == "Failed":
					self.rq.failTask(jobTaskID[0], jobTaskID[1], taskTime=0)

			self.updateQueueView()
			self.updateWorkerView()

		except ValueError:
			pass


	# def toggleWorker(self):
	# 	""" Enable or disable the selected worker(s).
	# 	"""
	# 	# if self.workerStatus == "Disabled":
	# 	if self.rq.getWorkerStatus == "Disabled":
	# 		self.setWorkerStatus("Idle")
	# 	else:
	# 		self.setWorkerStatus("Disabled")


	def enableWorkers(self):
		""" Enable the selected worker(s).
		"""
		header = self.workers_header

		try:
			for item in self.ui.workers_treeWidget.selectedItems():
				if item.text(header['Status']) == "Offline":
					print("Offline workers cannot be enabled/disabled")
				else:
					self.rq.enableWorker(item.text(header['ID']))

			self.updateWorkerView()

		except ValueError:
			pass


	def disableWorkers(self):
		""" Disable the selected worker(s).
		"""
		header = self.workers_header

		try:
			for item in self.ui.workers_treeWidget.selectedItems():
				if item.text(header['Status']) == "Offline":
					print("Offline workers cannot be enabled/disabled")
				else:
					self.rq.disableWorker(item.text(header['ID']))

			self.updateWorkerView()

		except ValueError:
			pass


	# def checkinLocalWorkers(self):
	# 	""" Check in local worker(s).
	# 	"""
	# 	header = self.workers_header

	# 	root = self.ui.workers_treeWidget.invisibleRootItem()
	# 	for i in range(root.childCount()):
	# 		workerID = root.child(i).text(header['ID'])
	# 		workerType = root.child(i).text(header['Type'])
	# 		workerStatus = root.child(i).text(header['Status'])

	# 		if workerType == "Local":
	# 			self.rq.checkinWorker(workerID, self.localhost)


	def checkoutLocalWorkers(self):
		""" Check out local worker(s).
			This should happen when the Render Queue client UI is closed.
		"""
		header = self.workers_header

		root = self.ui.workers_treeWidget.invisibleRootItem()
		for i in range(root.childCount()):
			workerID = root.child(i).text(header['ID'])
			workerType = root.child(i).text(header['Type'])

			if workerType == "Local":
				self.rq.checkoutWorker(workerID, self.localhost)


	# def setWorkerStatus(self, status):
	# 	""" Set the local worker status, and update the tool button and menu.
	# 	"""
	# 	header = self.workers_header
	# 	workerIDs = []

	# 	try:
	# 		for item in self.ui.workers_treeWidget.selectedItems():
	# 			workerIDs.append(item.text(header['ID']))

	# 		for workerID in workerIDs:
	# 			if status == "Disabled":
	# 				# self.rq.requeueTask(workerID[0], workerID[1])
	# 				self.rq.setWorkerStatus(workerID, "Disabled")
	# 			elif status == "Idle":
	# 				# self.rq.completeTask(workerID[0], workerID[1], taskTime=0)
	# 				self.rq.setWorkerStatus(workerID, "Idle")
	# 			# elif status == "Rendering":
	# 			# 	# self.rq.failTask(workerID[0], workerID[1], taskTime=0)
	# 			# 	self.rq.setWorkerStatus(workerID, "Rendering")

	# 		self.updateWorkerView()

	# 	except ValueError:
	# 		pass


	def combineTasks(self):
		""" Combine the selected tasks into a new task. Only works for tasks
			belonging to the same job, all of which are queued and have a
			contiguous frame range.
		"""
		pass # Re-enable when implementing this feature
		# header = self.queue_header

		# # for item in self.selection:
		# jobIDs = []
		# taskIDs = []
		# # frames = []

		# try:
		# 	for item in self.ui.queue_treeWidget.selectedItems():
		# 		# If item has parent then it must be a subitem, and therefore
		# 		# also a task
		# 		if item.parent():
		# 			# Only add task if it belongs to the same job as the first
		# 			jobID = item.parent().text(header['ID'])
		# 			jobIDs.append(jobID)
		# 			if jobID == jobIDs[0]:
		# 				# frames += sequence.numList(item.text(header['Frames']))

		# 				taskIDs.append(int(item.text(header['Frames'])))
		# 			else:
		# 				print("Warning: Only tasks belonging to the same job can be combined.")
		# 				return False

		# 	# print(sequence.numRange(frames))
		# 	combinedTaskID = self.rq.combineTasks(jobIDs[0], taskIDs)
		# 	if combinedTaskID is not None:
		# 		self.ui.queue_treeWidget.clear()  # Needed to remove deleted tasks
		# 		self.updateQueueView()
		# 		# select new task
		# 		#self.ui.queue_treeWidget.setCurrentItem(currentItem)

		# except ValueError:
		# 	pass


	def newWorker(self):
		""" Create a new local worker node.
		"""
		worker_args = {}
		worker_args['name'] = self.localhost.split(".")[0]
		worker_args['hostname'] = self.localhost
		worker_args['ip_address'] = self.ip_address
		#worker_args['status'] = "Disabled"
		worker_args['enable'] = False
		worker_args['online'] = time.time()
		worker_args['username'] = os.environ.get('IC_USERNAME', getpass.getuser())
		worker_args['pool'] = "None"
		worker_args['comment'] = ""

		self.rq.newWorker(**worker_args)
		self.updateWorkerView()


	def dequeue(self):
		""" Dequeue a render task from the queue and start rendering.
		"""
		header = self.workers_header
		# workerIDs = []

		self.renderTaskInterrupted = False
		self.renderTaskErrors = 0
		self.renderOutput = ""
		# self.startTimeSec = time.time()  # Used to measure the time spent rendering
		# startTime = time.strftime(self.time_format)

		# Look for a suitable task to render
		task = self.rq.getTaskToRender()
		if task is None:
			# verbose.message("[%s] No jobs to render." %self.localhost)
			# print("No suitable tasks to render.")
			return False

		# # Get workers - from JSON
		# workers = self.rq.getWorkers()
		# if not workers:
		# 	print("No workers.")
		# 	return False
		# for worker in workers:
		# 	if worker['ip_address'] == self.ip_address:  # Local workers only
		# 		if worker['status'] == "Idle":  # Worker is ready
		# 			# ---SNIP---

		# Get workers - from widget
		root = self.ui.workers_treeWidget.invisibleRootItem()
		for i in range(root.childCount()):
			workerItem = root.child(i)
			workerID = workerItem.text(header['ID'])
			workerType = workerItem.text(header['Type'])
			workerStatus = workerItem.text(header['Status'])
			if workerType == "Local":  # Local workers only
				if workerStatus == "Idle":  # Worker is ready
					# ---SNIP---
					self.rq.dequeueTask(task['jobID'], task['taskNo'], workerID)

					job = self.rq.getJob(task['jobID'])
					node = self.rq.getWorker(workerID)
					# result = worker.renderTask(job, task, node)

					# if result:
					# 	self.rq.completeTask(task['jobID'], task['taskNo'], taskTime=1)
					# else:
					# 	self.rq.failTask(task['jobID'], task['taskNo'], taskTime=1)

					# Initialise worker thread, connect signals & slots, start processing
					logfile = os.path.join(self.rq.db['logs'], '%s_%s.log' %(task['jobID'], str(task['taskNo']).zfill(4)))
					#print(logfile)
					self.workerThread = worker.WorkerThread(
						job, task, node, logfile, 
						ignore_errors=True)
					# self.workerThread.printError.connect(verbose.error)
					# self.workerThread.printMessage.connect(verbose.message)
					# self.workerThread.printProgress.connect(verbose.progress)
					# self.workerThread.updateProgressBar.connect(self.updateProgressBar)
					# self.workerThread.taskCompleted.connect(self.taskCompleted)
					self.workerThread.taskCompleted.connect(self.rq.completeTask)
					self.workerThread.taskFailed.connect(self.rq.failTask)
					self.workerThread.finished.connect(self.renderFinished)
					self.workerThread.start()

					# Update views
					self.updateQueueView()
					self.updateWorkerView()



	def renderFinished(self):
		""" Function to execute when the render operation finishes.
		"""
		print("Render finished.")


	def cancelRender(self):
		""" Stop the rename operation.
		"""
		print("Aborting render.")
		# self.workerThread.terminate()  # Enclose in try/except?
		self.workerThread.quit()  # Enclose in try/except?
		self.workerThread.wait()  # Enclose in try/except?

		# self.ui.taskList_treeWidget.resizeColumnToContents(self.getHeaderIndex("Status"))


	def updateTimers(self):
		""" Calculate elapsed time and update relevant UI fields.
		"""
		pass
		# if self.workerStatus == "rendering":
		# 	elapsedTimeSec = time.time() - self.startTimeSec
		# 	self.ui.runningTime_label.setText( str(datetime.timedelta(seconds=int(elapsedTimeSec))) )
		# 	# this could also update the appropriate render queue tree widget item, if I can figure out how to do that


	def dragEnterEvent(self, e):
		if e.mimeData().hasUrls:
			e.accept()
		else:
			e.ignore()


	def dragMoveEvent(self, e):
		if e.mimeData().hasUrls:
			e.accept()
		else:
			e.ignore()


	def dropEvent(self, e):
		""" Event handler for files dropped on to the widget.
		"""
		if e.mimeData().hasUrls:
			e.setDropAction(QtCore.Qt.CopyAction)
			e.accept()
			for url in e.mimeData().urls():
				# # Workaround for macOS dragging and dropping
				# if os.environ['IC_RUNNING_OS'] == "MacOS":
				# 	fname = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path())
				# else:
				# 	fname = str(url.toLocalFile())
				fname = str(url.toLocalFile())

			#print("Dropped '%s' on to window." %fname)
			if os.path.isdir(fname):
				pass
			elif os.path.isfile(fname):
				filetype = os.path.splitext(fname)[1]
				if filetype in ['.ma', '.mb']:  # Maya files
					self.launchRenderSubmit(jobtype='Maya', scene=fname)
				if filetype in ['.hip']:  # Houdini files
					self.launchRenderSubmit(jobtype='Houdini', scene=fname)
				if filetype in ['.nk', ]:  # Nuke files
					self.launchRenderSubmit(jobtype='Nuke', scene=fname)
		else:
			e.ignore()


	def showEvent(self, event):
		""" Event handler for when window is shown.
		"""
		# Create timers to refresh the view, dequeue tasks, and update elapsed
		# time readouts every n milliseconds
		self.timerUpdateView = QtCore.QTimer(self)
		self.timerUpdateView.timeout.connect(self.updateQueueView)
		self.timerUpdateView.timeout.connect(self.updateWorkerView)
		self.timerUpdateView.start(5000)

		self.timerDequeue = QtCore.QTimer(self)
		self.timerDequeue.timeout.connect(self.dequeue)
		self.timerDequeue.start(5000)  # Should only happen when worker is enabled

		# self.timerUpdateTimer = QtCore.QTimer(self)
		# self.timerUpdateTimer.timeout.connect(self.updateTimers)
		# self.timerUpdateTimer.start(1000)

		# self.timerPing = QtCore.QTimer(self)
		# self.timerPing.timeout.connect(self.pingRemote)
		# self.timerPing.start(15000)

		# self.timerCheckin = QtCore.QTimer(self)
		# self.timerCheckin.timeout.connect(self.checkinLocalWorkers)
		# self.timerCheckin.start(15000)

		self.updateQueueView()
		self.updateWorkerView()
		#self.updateWorkerView()  # bodge - run twice to update online workers
		self.updateSelection()
		#self.checkinLocalWorkers()


	def closeEvent(self, event):
		""" Event handler for when window is closed.
		"""
		header = self.workers_header
		render_in_progress = False

		# Check if any local workers are rendering
		root = self.ui.workers_treeWidget.invisibleRootItem()
		for i in range(root.childCount()):
			workerID = root.child(i).text(header['ID'])
			workerType = root.child(i).text(header['Type'])
			workerStatus = root.child(i).text(header['Status'])

			if workerType == "Local":
				if workerStatus.startswith("Rendering"):
					render_in_progress = True

		# Confirmation dialog
		if render_in_progress:
			dialog_title = 'Render in progress'
			dialog_msg = ''
			dialog_msg += 'One or more local workers are currently rendering. Closing the Render Queue window will also stop the render(s).\n'
			dialog_msg += 'Are you sure you want to quit?'

			if not self.promptDialog(dialog_msg, dialog_title):
				return

		# Kill the rendering process
		#self.killRenderProcess()

		# Requeue the task that's currently rendering
		#self.rq.requeueTask(jobTaskID[0], jobTaskID[1])

		# Stop timers
		self.timerUpdateView.stop()
		self.timerDequeue.stop()
		# self.timerUpdateTimer.stop()
		# self.timerCheckin.stop()

		# Mark local worker(s) as offline
		self.checkoutLocalWorkers()

		# Store window geometry and state of certain widgets
		self.storeWindow()
		self.settings.setValue("splitterSizes", self.ui.splitter.saveState())
		self.settings.setValue("renderQueueView", self.ui.queue_treeWidget.header().saveState())
		self.settings.setValue("workersView", self.ui.workers_treeWidget.header().saveState())

		QtWidgets.QMainWindow.closeEvent(self, event)

# ----------------------------------------------------------------------------
# End main application class
# ============================================================================
# Run as standalone app
# ----------------------------------------------------------------------------

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)

	# Add missing image format plugins (only needed for PyQt4 on Linux?)
	QtWidgets.QApplication.addLibraryPath(os.getcwd())

	# Apply 'Fusion' application style for Qt5
	styles = QtWidgets.QStyleFactory.keys()
	if 'Fusion' in styles:
		app.setStyle('Fusion')

	# # Apply UI style sheet
	# if STYLESHEET is not None:
	# 	qss=os.path.join(os.environ['IC_FORMSDIR'], STYLESHEET)
	# 	with open(qss, "r") as fh:
	# 		app.setStyleSheet(fh.read())

	# Enable high DPI scaling
	# try:
	# 	QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
	# except AttributeError:
	# 	pass

	# Instantiate main application class
	rqApp = RenderQueueApp()

	# Show the application UI
	rqApp.show()
	sys.exit(app.exec_())

