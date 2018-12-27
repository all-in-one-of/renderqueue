#!/usr/bin/python

# worker.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2018
#
# Render Worker


import datetime
import json
import logging
import math
import os
import socket
import sys
import time
import uuid

from Qt import QtCore, QtGui, QtWidgets
import icons_rc
import ui_template as UI

# Import custom modules
import about
import oswrapper
import database
import outputparser
import sequence
#import verbose


class RenderWorker():
	def __init__(self, parent=None):
		workerID = uuid.uuid4().hex  # generate UUID
		kwargs['workerID'] = workerID

		# Write job data file
		datafile = os.path.join(self.db_workers, '%s.json' %jobID)
		with open(datafile, 'w') as f:
			json.dump(kwargs, f, indent=4)

		# Set up logging (TEST)
		# task_log_path = oswrapper.absolutePath('$RQ_DATADIR/test.log')
		# logging.basicConfig(level=logging.DEBUG, filename=task_log_path, filemode="a+",
		#                     format="%(asctime)-15s %(levelname)-8s %(message)s")

		self.setupUI(window_object=WINDOW_OBJECT, 
					 window_title=WINDOW_TITLE, 
					 ui_file=UI_FILE, 
					 stylesheet=STYLESHEET, 
					 prefs_file=PREFS_FILE, 
					 store_window_geometry=STORE_WINDOW_GEOMETRY)  # re-write as **kwargs ?

		# Set window flags
		self.setWindowFlags(QtCore.Qt.Window)

		# Set other Qt attributes
		#self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

		# Restore widget state
		# try:
		# 	self.ui.splitter.restoreState(self.settings.value("splitterSizes")) #.toByteArray())
		# 	self.ui.renderQueue_treeWidget.header().restoreState(self.settings.value("renderQueueView")) #.toByteArray())
		# except:
		# 	pass

		# Instantiate render queue class and load data
		databaseLocation = self.prefs.getValue('user', 'databaseLocation')
		self.rq = database.RenderQueue(databaseLocation)

		# Create a QProcess object to handle the rendering process
		# asynchronously
		self.renderProcess = QtCore.QProcess(self)
		self.renderProcess.finished.connect(self.renderComplete)
		self.renderProcess.readyReadStandardOutput.connect(self.updateWorkerView)

		# Define global variables
		self.timeFormatStr = "%Y/%m/%d %H:%M:%S"
		self.localhost = socket.gethostname()
		self.selection = []
		self.renderOutput = ""
		#verbose.registerStatusBar(self.ui.statusBar)  # only in standalone?

		# --------------------------------------------------------------------
		# Connect signals & slots
		# --------------------------------------------------------------------

		# # Set up context menus for render queue tree widget
		# self.ui.renderQueue_treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		# self.ui.renderQueue_treeWidget.customContextMenuRequested.connect(self.openContextMenu)

		# Add context menu items to worker control tool button
		self.ui.workerControl_toolButton.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

		self.actionWorkerStart = QtWidgets.QAction("Start Worker", None)
		self.actionWorkerStart.triggered.connect(self.toggleWorker)
		self.ui.workerControl_toolButton.addAction(self.actionWorkerStart)

		self.actionWorkerStop = QtWidgets.QAction("Stop Worker", None)
		self.actionWorkerStop.triggered.connect(self.toggleWorker)
		self.ui.workerControl_toolButton.addAction(self.actionWorkerStop)

		self.actionKillTask = QtWidgets.QAction("Stop Worker Immediately and Kill Current Task", None)
		self.actionKillTask.triggered.connect(self.killRenderProcess)
		self.ui.workerControl_toolButton.addAction(self.actionKillTask)

		self.actionWorkerContinueAfterTask = QtWidgets.QAction("Continue After Current Task Completion", None)
		self.actionWorkerContinueAfterTask.setCheckable(True)
		self.ui.workerControl_toolButton.addAction(self.actionWorkerContinueAfterTask)

		self.actionWorkerStopAfterTask = QtWidgets.QAction("Stop Worker After Current Task Completion", None)
		self.actionWorkerStopAfterTask.setCheckable(True)
		self.ui.workerControl_toolButton.addAction(self.actionWorkerStopAfterTask)

		workerControlAfterTaskGroup = QtWidgets.QActionGroup(self)
		workerControlAfterTaskGroup.addAction(self.actionWorkerContinueAfterTask)
		workerControlAfterTaskGroup.addAction(self.actionWorkerStopAfterTask)
		self.actionWorkerContinueAfterTask.setChecked(True)

		# Set local worker as disabled initially
		self.setWorkerStatus("disabled")  # Store this as a preference or something

		self.updateWorkerView()
		self.updateToolbarUI()


	# def openContextMenu(self, position):
	# 	""" Display right-click context menu for items in render queue tree
	# 		view widget.
	# 	"""
	# 	level = -1  # Initialise with null value in case of empty queue
	# 	menu = None
	# 	indices = self.ui.renderQueue_treeWidget.selectedIndexes()
	# 	if len(indices) > 0:
	# 		level = 0
	# 		index = indices[0]
	# 		while index.parent().isValid():
	# 			index = index.parent()
	# 			level += 1

	# 	if level == 0:  # Job
	# 		menu = self.ui.menuJob
	# 	elif level == 1:  # Task
	# 		menu = self.ui.menuTask

	# 	if menu:
	# 		menu.exec_(self.ui.renderQueue_treeWidget.viewport().mapToGlobal(position))


	# def resizeColumns(self):
	# 	""" Resize all columns of the specified widget to fit content.
	# 	"""
	# 	widget = self.ui.renderQueue_treeWidget
	# 	for i in range(0, widget.columnCount()):
	# 		widget.resizeColumnToContents(i)


	def updateWorkerView(self):
		""" Update the information in the worker info area.
			This function is also called by the render process signal in order
			to capture its output and display in the UI widget.
		"""
		self.ui.workerControl_toolButton.setText("%s (%s)" %(self.localhost, self.workerStatus))

		# try:
		# 	line = str(self.renderProcess.readAllStandardOutput(), 'utf-8')
		# except TypeError:  # Python 2.x compatibility
		# 	line = str(self.renderProcess.readAllStandardOutput())

		if int(sys.version[0]) <= 2:  # Python 2.x compatibility
			line = str(self.renderProcess.readAllStandardOutput())
		else:
			line = str(self.renderProcess.readAllStandardOutput(), 'utf-8')

		# task_log_path = oswrapper.absolutePath('$IC_CONFIGDIR/renderqueue/%s.log' %self.localhost)
		# with open(task_log_path, 'a') as fh:
		# 	fh.write(line)
		# 	#print(line, file=fh)
		# #logging.info(line)

		# Parse output
		if outputparser.parse(line, 'Maya'):
			#verbose.error(line)
			self.renderTaskErrors += 1

		self.renderOutput += line
		self.ui.output_textEdit.setPlainText(self.renderOutput)
		self.ui.output_textEdit.moveCursor(QtGui.QTextCursor.End)


		# Get the render job item or create it if it doesn't exist
		#workerListItem = self.getQueueItem(self.ui.workers_treeWidget.invisibleRootItem(), jobID)
		workerListItem = QtWidgets.QTreeWidgetItem(self.ui.workers_treeWidget.invisibleRootItem())

		# Fill columns with data
		workerListItem.setText(0, self.localhost)
		workerListItem.setText(1, self.workerStatus)
		# workerListItem.setText(2, workerRunningTime)
		# workerListItem.setText(3, workerPool)
		# workerListItem.setText(4, workerPriority)


	def toggleWorker(self):
		""" Enable or disable the local worker.
		"""
		if self.workerStatus == "disabled":
			self.setWorkerStatus("idle")
		else:
			self.setWorkerStatus("disabled")

		#self.updateWorkerView()


	def setWorkerStatus(self, status):
		""" Set the local worker status, and update the tool button and menu.
		"""
		statusIcon = QtGui.QIcon()
		self.workerStatus = status

		if status == "disabled":
			self.ui.workerControl_toolButton.setChecked(False)
			statusIcon.addPixmap(QtGui.QPixmap(":/rsc/rsc/status_icon_stopped.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
			self.actionWorkerStart.setVisible(True)
			self.actionWorkerStop.setVisible(False)
			self.actionKillTask.setVisible(False)
			self.actionWorkerContinueAfterTask.setVisible(False)
			self.actionWorkerStopAfterTask.setVisible(False)
			self.actionWorkerContinueAfterTask.setChecked(True)  # Reset this option for the next time the worker is enabled

			self.ui.taskInfo_label.setText("")
			self.ui.runningTime_label.setText("")

		elif status == "idle":
			self.ui.workerControl_toolButton.setChecked(True)
			statusIcon.addPixmap(QtGui.QPixmap(":/rsc/rsc/status_icon_null.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
			self.actionWorkerStart.setVisible(False)
			self.actionWorkerStop.setVisible(True)
			self.actionKillTask.setVisible(False)
			self.actionWorkerContinueAfterTask.setVisible(False)
			self.actionWorkerStopAfterTask.setVisible(False)

			self.ui.taskInfo_label.setText("")
			self.ui.runningTime_label.setText("")

		elif status == "rendering":
			self.ui.workerControl_toolButton.setChecked(True)
			statusIcon.addPixmap(QtGui.QPixmap(":/rsc/rsc/status_icon_ok.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
			self.actionWorkerStart.setVisible(False)
			self.actionWorkerStop.setVisible(False)
			self.actionKillTask.setVisible(True)
			self.actionWorkerContinueAfterTask.setVisible(True)
			self.actionWorkerStopAfterTask.setVisible(True)

			# self.ui.taskInfo_label.setText("Rendering %s %s from '%s'" %(verbose.pluralise("frame", len(frameList)), frames, self.rq.getValue(jobElement, 'name')))
			# self.ui.runningTime_label.setText(startTime)  # change this to display the task running time

		#verbose.message("[%s] Local worker %s." %(self.localhost, self.workerStatus))
		self.ui.workerControl_toolButton.setText("%s (%s)" %(self.localhost, self.workerStatus))
		self.ui.workerControl_toolButton.setIcon(statusIcon)

		#self.updateWorkerView()


	def dequeue(self):
		""" Dequeue a render task from the queue and start rendering.
			THIS IS ALL A BIT ROPEY ATM
		"""
		if self.workerStatus != "idle":
			return False
		#elif self.workerStatus != "rendering":

		self.renderTaskInterrupted = False
		self.renderTaskErrors = 0
		self.renderOutput = ""
		self.startTimeSec = time.time()  # Used for measuring the time spent rendering
		startTime = time.strftime(self.timeFormatStr)

		#self.rq.loadXML(quiet=True)  # Reload XML data - this is being done by the dequeuing function

		# Look for a suitable job to render - perhaps check here for a few
		# easy-to-detect errors, i.e. existence of scene, render command, etc.
		jobElement = self.rq.dequeueJob()
		if jobElement is None:
			#verbose.message("[%s] No jobs to render." %self.localhost)
			return False
		self.renderJobID = jobElement.get('id')

		# Look for tasks to start rendering
		self.renderTaskID, frames = self.rq.dequeueTask(self.renderJobID, self.localhost)
		if not self.renderTaskID:
			#verbose.message("[%s] Job ID %s: No tasks to render." %(self.localhost, self.renderJobID))
			return False

		#verbose.message("[%s] Job ID %s, Task ID %s: Starting render..." %(self.localhost, self.renderJobID, self.renderTaskID))
		if frames == 'Unknown':
			frameList = frames
		else:
			frameList = sequence.numList(frames)
			startFrame = min(frameList)
			endFrame = max(frameList)


		jobType = self.rq.getValue(jobElement, 'type')
		if jobType == 'Maya':
			# try:
			# 	renderCmd = '"%s"' %os.environ['MAYARENDERVERSION'] # store this in XML as maya version may vary with project
			# except KeyError:
			# 	print "ERROR: Path to Maya Render command executable not found. This can be set with the environment variable 'MAYARENDERVERSION'."
			#renderCmd = '"%s"' %os.path.normpath(self.rq.getValue(jobElement, 'mayaRenderCmd'))
			renderCmd = self.rq.getValue(jobElement, 'mayaRenderCmd')
			# if not os.path.isfile(renderCmd): # disabled this check 
			# 	print "ERROR: Maya render command not found: %s" %renderCmd
			# 	return False

			sceneName = self.rq.getValue(jobElement, 'mayaScene')
			# if not os.path.isfile(sceneName): # check scene exists - disabled for now as could cause worker to get stuck in a loop
			# 	print "ERROR: Scene not found: %s" %sceneName
			# 	self.rq.requeueTask(self.renderJobID, self.renderTaskID)
			# 	#self.rq.setStatus(self.renderJobID, "Failed")
			# 	return False

			cmdStr = ''
			args = '-proj "%s"' %self.rq.getValue(jobElement, 'mayaProject')

			mayaFlags = self.rq.getValue(jobElement, 'mayaFlags')
			if mayaFlags is not None:
				args += ' %s' %mayaFlags

			# Construct command(s)
			if frames == 'Unknown':
				cmdStr = '"%s" %s "%s"' %(renderCmd, args, sceneName)
			else:
				cmdStr += '"%s" %s -s %d -e %d "%s"' %(renderCmd, args, int(startFrame), int(endFrame), sceneName)

		elif jobType == 'Nuke':
			renderCmd = self.rq.getValue(jobElement, 'nukeRenderCmd')
			scriptName = self.rq.getValue(jobElement, 'nukeScript')

			cmdStr = ''
			args = ''

			nukeFlags = self.rq.getValue(jobElement, 'nukeFlags')
			if nukeFlags is not None:
				args += ' %s' %nukeFlags

			# Construct command(s)
			if frames == 'Unknown':
				cmdStr = '"%s" %s -x "%s"' %(renderCmd, args, scriptName)
			else:
				cmdStr += '"%s" %s -F %s -x "%s"' %(renderCmd, args, frames, scriptName)


		# Set rendering status
#		verbose.print_(cmdStr, 4)

		# Fill info fields
		#self.ui.taskInfo_label.setText("Rendering %s %s from '%s'" %(verbose.pluralise("frame", len(frameList)), frames, self.rq.getValue(jobElement, 'name')))
		#self.ui.runningTime_label.setText(startTime)  # change this to display the task running time
		self.ui.runningTime_label.setText( str(datetime.timedelta(seconds=0)) )

		self.setWorkerStatus("rendering")
		self.renderProcess.start(cmdStr)
		self.updateRenderQueueView()


	def updateTimers(self):
		""" Calculate elapsed time and update relevant UI fields.
		"""
		if self.workerStatus == "rendering":
			elapsedTimeSec = time.time() - self.startTimeSec
			self.ui.runningTime_label.setText( str(datetime.timedelta(seconds=int(elapsedTimeSec))) )
			# this could also update the appropriate render queue tree widget item, if I can figure out how to do that


	def renderComplete(self):
		""" This code should only be executed after successful task
			completion.
		"""
		totalTimeSec = time.time() - self.startTimeSec  # Calculate time spent rendering task

		# self.ui.taskInfo_label.setText("")
		# self.ui.runningTime_label.setText("")
		if self.renderTaskInterrupted:
			self.rq.requeueTask(self.renderJobID, self.renderTaskID)  # perhaps set a special status to indicate render was killed, allowing the user to requeue manually?
		elif self.renderTaskErrors:
			self.rq.failTask(self.renderJobID, self.renderTaskID, self.localhost, taskTime=totalTimeSec)
		else:
			self.rq.completeTask(self.renderJobID, self.renderTaskID, self.localhost, taskTime=totalTimeSec)

		# Set worker status based on user option
		if self.actionWorkerStopAfterTask.isChecked():
			self.setWorkerStatus("disabled")
		else:
			self.setWorkerStatus("idle")
			self.dequeue()  # Dequeue next task immediately to prevent wait for next polling interval

		self.updateRenderQueueView()


	def killRenderProcess(self):
		""" Kill the rendering process. This will also stop the local worker.
		"""
		#verbose.message("Attempting to kill process %s" %self.renderProcess)

		self.actionWorkerStopAfterTask.setChecked(True)  # This is a fudge to prevent the renderComplete function from re-enabling the worker after rendering task was killed by user
		self.renderTaskInterrupted = True

		if self.workerStatus == "rendering":
			#self.renderProcess.terminate()
			self.renderProcess.kill()
		#else:
		#	verbose.message("No render in progress.")

		#totalTimeSec = time.time() - self.startTimeSec  # Calculate time spent rendering task

		# self.ui.taskInfo_label.setText("")
		# self.ui.runningTime_label.setText("")
		#self.rq.completeTask(self.renderJobID, self.renderTaskID)
		#self.rq.requeueTask(self.renderJobID, self.renderTaskID)  # perhaps set a special status to indicate render was killed, allowing the user to requeue manually?

		#self.setWorkerStatus("disabled")

		#self.updateRenderQueueView()


	def showEvent(self, event):
		""" Event handler for when window is shown.
		"""
		# Create timers to refresh the view, dequeue tasks, and update elapsed
		# time readouts every n milliseconds
		self.timerUpdateView = QtCore.QTimer(self)
		self.timerUpdateView.timeout.connect(self.updateRenderQueueView)
		self.timerUpdateView.start(5000)

		self.timerDequeue = QtCore.QTimer(self)
		self.timerDequeue.timeout.connect(self.dequeue)
		self.timerDequeue.start(5000)  # Should only happen when worker is enabled

		self.timerUpdateTimer = QtCore.QTimer(self)
		self.timerUpdateTimer.timeout.connect(self.updateTimers)
		self.timerUpdateTimer.start(1000)

		#self.updateRenderQueueView()
		#self.rebuildRenderQueueView()
		self.updateToolbarUI()


	def closeEvent(self, event):
		""" Event handler for when window is closed.
		"""

		# Confirmation dialog
		# if self.workerStatus == "rendering":
		# 	import pDialog

		# 	dialogTitle = 'Render in progress'
		# 	dialogMsg = ''
		# 	dialogMsg += 'There is currently a render in progress on the local worker. Closing the Render Queue window will also kill the render.\n'
		# 	dialogMsg += 'Are you sure you want to quit?'

		# 	dialog = pDialog.dialog()
		# 	if dialog.display(dialogMsg, dialogTitle):
		# 		event.accept()
		# 	else:
		# 		event.ignore()
		# 		return

		# Kill the rendering process
		self.killRenderProcess()

		# Requeue the task that's currently rendering
		#self.rq.requeueTask(jobTaskID[0], jobTaskID[1])

		# Stop timers
		self.timerUpdateView.stop()
		self.timerDequeue.stop()
		self.timerUpdateTimer.stop()

		# Store window geometry and state of certain widgets
		# self.storeWindow()
		# self.settings.setValue("splitterSizes", self.ui.splitter.saveState())
		# self.settings.setValue("renderQueueView", self.ui.renderQueue_treeWidget.header().saveState())

		QtWidgets.QMainWindow.closeEvent(self, event)

# ----------------------------------------------------------------------------
# End main application class
# ============================================================================
# Run as standalone app
# ----------------------------------------------------------------------------

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)

	# Apply application style
	styles = QtWidgets.QStyleFactory.keys()
	if 'Fusion' in styles:  # Qt5
		app.setStyle('Fusion')
	# elif 'Plastique' in styles:
	# 	app.setStyle('Plastique')  # Qt4

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
	rwApp = RenderWorkerApp()

	# Show the application UI
	rwApp.show()
	sys.exit(app.exec_())

