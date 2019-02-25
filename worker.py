#!/usr/bin/python

# worker.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Render Worker - this module constructs the command(s) to be run by a worker
# and interfaces with the various plugins.


import os
import platform
import subprocess

from Qt import QtCore

# Import custom modules
import common
import oswrapper
import sequence


# ----------------------------------------------------------------------------
# Begin worker thread class
# ----------------------------------------------------------------------------

class WorkerThread(QtCore.QThread):
	""" Worker thread class.
	"""
	# printError = QtCore.Signal(str)
	# printMessage = QtCore.Signal(str)
	# printProgress = QtCore.Signal(str)
	# updateProgressBar = QtCore.Signal(int)
	taskCompleted = QtCore.Signal(str, int) #, float
	taskFailed = QtCore.Signal(str, int) #, float

	def __init__(self, job, task, worker, logfile, ignore_errors=True):
		QtCore.QThread.__init__(self)
		self.job = job
		self.task = task
		self.worker = worker
		self.logfile = logfile
		self.ignore_errors = ignore_errors
		self.files_processed = 0

		# Set up logging
		logger_name = '%s_logger' %os.path.splitext(os.path.basename(logfile))[0]
		self.task_logger = common.setup_logger(logger_name, logfile)


	def __del__(self):
		self.wait()


	def run(self):
		self._render_task()


	def _render_task(self):
		""" Perform the rendering operation(s).
		"""
		self.task_logger.info("Starting render on worker %s (%s)" 
			%(self.worker['name'], self.worker['id']))

		# Construct the render command...
		args = []
		#errors = 0

		if self.task['frames'] == "Unknown":
			frameList = self.task['frames']
		else:
			frameList = sequence.numList(self.task['frames'])
			startFrame = min(frameList)
			endFrame = max(frameList)

		###########
		# GENERIC #
		###########

		if self.job['jobType'] == "Generic":
			args.append(self.job['command'])
			if self.job['flags']:
				args.append(self.job['flags'])

		########
		# MAYA #
		########

		elif self.job['jobType'] == "Maya":
			# Set executable (rewrite this to use app paths / versions)
			if platform.system() == "Windows":
				args.append('C:/Program Files/Autodesk/Maya2018/bin/Render.exe')
			elif platform.system() == "Darwin":
				args.append('/Applications/Autodesk/maya2018/Maya.app/Contents/bin/Render')
			else:
				args.append('/usr/autodesk/maya2018/bin/Render')

			args.append('-proj')
			args.append(self.job['mayaProject'])

			if self.job['flags']:
				args.append(self.job['flags'])

			if self.job['renderer']:
				args.append('-r')
				args.append(self.job['renderer'])

			# Set arnold verbosity (temp)
			if self.job['renderer'] == "arnold":
				args.append('-ai:lve')
				args.append('1')

			if frameList == "Unknown":
				pass
			else:
				args.append('-s')
				args.append(str(startFrame))
				args.append('-e')
				args.append(str(endFrame))

			args.append(self.job['scene'])

		###########
		# HOUDINI #
		###########

		elif self.job['jobType'] == "Houdini":
			# Set executable (rewrite this to use app paths / versions)
			if platform.system() == "Windows":
				args.append('')
			elif platform.system() == "Darwin":
				args.append('')
			else:
				args.append('/opt/hfs/bin/hrender')

			args.append('-v')
			args.append('-d')
			args.append(self.job['outputDriver'])

			if frameList == "Unknown":
				pass
			else:
				args.append('-e')
				args.append('-f')
				args.append(str(startFrame))
				args.append(str(endFrame))

			args.append(self.job['scene'])

		########
		# NUKE #
		########

		elif self.job['jobType'] == "Nuke":
			# Set executable (rewrite this to use app paths / versions)
			if platform.system() == "Windows":
				args.append('C:/Program Files/Nuke10.0v3/Nuke10.0.exe')
			elif platform.system() == "Darwin":
				args.append('/Applications/Nuke10.0v3/Nuke10.0v3.app/Contents/MacOS/Nuke10.0v3')
			else:
				args.append('/usr/local/bin/nuke')

			if self.job['flags']:
				args.append(self.job['flags'])

			if frameList == "Unknown":
				pass
			else:
				args.append('-F')
				args.append(self.task['frames'])

			args.append('-x')
			args.append(self.job['scene'])

		# # Set rendering status
		# # Fill info fields
		# self.ui.taskInfo_label.setText("Rendering %s %s from '%s'" %(verbose.pluralise("frame", len(frameList)), frames, self.rq.getValue(jobElement, 'name')))
		# self.ui.runningTime_label.setText(startTime)  # change this to display the task running time
		# self.ui.runningTime_label.setText( str(datetime.timedelta(seconds=0)) )

		# self.setWorkerStatus("rendering")
		# self.renderProcess.start(cmdStr)
		# self.updateRenderQueueView()

		cmd_str = " ".join(args)
		self.task_logger.info("Render command:\n%s" %cmd_str)

		# Execute the command, redirect output to log, catch errors
		try:
			with open(self.logfile, 'a') as outfile:
				result = subprocess.check_call(
					args, stdout=outfile, stderr=outfile)

		except subprocess.CalledProcessError as e:
			result = e.returncode

		#result, output = oswrapper.execute(args)
		#self.task_logger.info("Result: %s", result)
		#self.task_logger.info(output)

		# Complete or fail the task depending on return code
		#print(result)
		if result == 0:  # Normal exit code
			self.task_logger.info("Render completed successfully on worker %s (%s)" 
				%(self.worker['name'], self.worker['id']))
			self.taskCompleted.emit(self.task['jobID'], self.task['taskNo']) #, taskTime=1)
		else:  # Failure
			self.task_logger.error("Render failed on worker %s (%s)" 
				%(self.worker['name'], self.worker['id']))
			self.taskFailed.emit(self.task['jobID'], self.task['taskNo']) #, taskTime=1)

		divider = "="*80
		self.task_logger.info("Log ends\n%s" %divider)

		return result

# ----------------------------------------------------------------------------
# End worker thread class
# ============================================================================
# Run as standalone app
# ----------------------------------------------------------------------------

# if __name__ == "__main__":
# 	app = QtWidgets.QApplication(sys.argv)

# 	myApp = BatchRenameApp()
# 	myApp.show()
# 	sys.exit(app.exec_())




# class RenderWorker():
# 	def __init__(self, parent=None):
# 		# Create a QProcess object to handle the rendering process
# 		# asynchronously
# 		self.renderProcess = QtCore.QProcess(self)
# 		self.renderProcess.finished.connect(self.renderComplete)
# 		self.renderProcess.readyReadStandardOutput.connect(self.updateWorkerView)

# 		# Define global variables
# 		self.timeFormatStr = "%Y/%m/%d %H:%M:%S"
# 		self.localhost = socket.gethostname()
# 		self.selection = []
# 		self.renderOutput = ""

# 		# --------------------------------------------------------------------
# 		# Connect signals & slots
# 		# --------------------------------------------------------------------

# 		# Add context menu items to worker control tool button
# 		self.ui.workerControl_toolButton.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)

# 		self.actionWorkerStart = QtWidgets.QAction("Start Worker", None)
# 		self.actionWorkerStart.triggered.connect(self.toggleWorker)
# 		self.ui.workerControl_toolButton.addAction(self.actionWorkerStart)

# 		self.actionWorkerStop = QtWidgets.QAction("Stop Worker", None)
# 		self.actionWorkerStop.triggered.connect(self.toggleWorker)
# 		self.ui.workerControl_toolButton.addAction(self.actionWorkerStop)

# 		self.actionKillTask = QtWidgets.QAction("Stop Worker Immediately and Kill Current Task", None)
# 		self.actionKillTask.triggered.connect(self.killRenderProcess)
# 		self.ui.workerControl_toolButton.addAction(self.actionKillTask)

# 		self.actionWorkerContinueAfterTask = QtWidgets.QAction("Continue After Current Task Completion", None)
# 		self.actionWorkerContinueAfterTask.setCheckable(True)
# 		self.ui.workerControl_toolButton.addAction(self.actionWorkerContinueAfterTask)

# 		self.actionWorkerStopAfterTask = QtWidgets.QAction("Stop Worker After Current Task Completion", None)
# 		self.actionWorkerStopAfterTask.setCheckable(True)
# 		self.ui.workerControl_toolButton.addAction(self.actionWorkerStopAfterTask)

# 		workerControlAfterTaskGroup = QtWidgets.QActionGroup(self)
# 		workerControlAfterTaskGroup.addAction(self.actionWorkerContinueAfterTask)
# 		workerControlAfterTaskGroup.addAction(self.actionWorkerStopAfterTask)
# 		self.actionWorkerContinueAfterTask.setChecked(True)

# 		# Set local worker as disabled initially
# 		self.setWorkerStatus("disabled")  # Store this as a preference or something


# 	def updateWorkerView(self):
# 		""" Update the information in the worker info area.
# 			This function is also called by the render process signal in order
# 			to capture its output and display in the UI widget.
# 		"""
# 		self.ui.workerControl_toolButton.setText("%s (%s)" %(self.localhost, self.workerStatus))

# 		if int(sys.version[0]) <= 2:  # Python 2.x compatibility
# 			line = str(self.renderProcess.readAllStandardOutput())
# 		else:
# 			line = str(self.renderProcess.readAllStandardOutput(), 'utf-8')

# 		# task_log_path = oswrapper.absolutePath('$IC_CONFIGDIR/renderqueue/%s.log' %self.localhost)
# 		# with open(task_log_path, 'a') as fh:
# 		# 	fh.write(line)
# 		# 	#print(line, file=fh)
# 		# #logging.info(line)

# 		# Parse output
# 		if outputparser.parse(line, 'Maya'):
# 			#verbose.error(line)
# 			self.renderTaskErrors += 1

# 		self.renderOutput += line
# 		self.ui.output_textEdit.setPlainText(self.renderOutput)
# 		self.ui.output_textEdit.moveCursor(QtGui.QTextCursor.End)

# 		# Get the render job item or create it if it doesn't exist
# 		#workerListItem = self.getQueueItem(self.ui.workers_treeWidget.invisibleRootItem(), jobID)
# 		workerListItem = QtWidgets.QTreeWidgetItem(self.ui.workers_treeWidget.invisibleRootItem())

# 		# Fill columns with data
# 		workerListItem.setText(0, self.localhost)
# 		workerListItem.setText(1, self.workerStatus)
# 		# workerListItem.setText(2, workerRunningTime)
# 		# workerListItem.setText(3, workerPool)
# 		# workerListItem.setText(4, workerPriority)


# 	def toggleWorker(self):
# 		""" Enable or disable the local worker.
# 		"""
# 		if self.workerStatus == "disabled":
# 			self.setWorkerStatus("idle")
# 		else:
# 			self.setWorkerStatus("disabled")

# 		#self.updateWorkerView()


# 	def setWorkerStatus(self, status):
# 		""" Set the local worker status, and update the tool button and menu.
# 		"""
# 		statusIcon = QtGui.QIcon()
# 		self.workerStatus = status

# 		if status == "disabled":
# 			self.ui.workerControl_toolButton.setChecked(False)
# 			statusIcon.addPixmap(QtGui.QPixmap(":/rsc/rsc/status_icon_stopped.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
# 			self.actionWorkerStart.setVisible(True)
# 			self.actionWorkerStop.setVisible(False)
# 			self.actionKillTask.setVisible(False)
# 			self.actionWorkerContinueAfterTask.setVisible(False)
# 			self.actionWorkerStopAfterTask.setVisible(False)
# 			self.actionWorkerContinueAfterTask.setChecked(True)  # Reset this option for the next time the worker is enabled

# 			self.ui.taskInfo_label.setText("")
# 			self.ui.runningTime_label.setText("")

# 		elif status == "idle":
# 			self.ui.workerControl_toolButton.setChecked(True)
# 			statusIcon.addPixmap(QtGui.QPixmap(":/rsc/rsc/status_icon_null.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
# 			self.actionWorkerStart.setVisible(False)
# 			self.actionWorkerStop.setVisible(True)
# 			self.actionKillTask.setVisible(False)
# 			self.actionWorkerContinueAfterTask.setVisible(False)
# 			self.actionWorkerStopAfterTask.setVisible(False)

# 			self.ui.taskInfo_label.setText("")
# 			self.ui.runningTime_label.setText("")

# 		elif status == "rendering":
# 			self.ui.workerControl_toolButton.setChecked(True)
# 			statusIcon.addPixmap(QtGui.QPixmap(":/rsc/rsc/status_icon_ok.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
# 			self.actionWorkerStart.setVisible(False)
# 			self.actionWorkerStop.setVisible(False)
# 			self.actionKillTask.setVisible(True)
# 			self.actionWorkerContinueAfterTask.setVisible(True)
# 			self.actionWorkerStopAfterTask.setVisible(True)

# 			# self.ui.taskInfo_label.setText("Rendering %s %s from '%s'" %(verbose.pluralise("frame", len(frameList)), frames, self.rq.getValue(jobElement, 'name')))
# 			# self.ui.runningTime_label.setText(startTime)  # change this to display the task running time

# 		#verbose.message("[%s] Local worker %s." %(self.localhost, self.workerStatus))
# 		self.ui.workerControl_toolButton.setText("%s (%s)" %(self.localhost, self.workerStatus))
# 		self.ui.workerControl_toolButton.setIcon(statusIcon)

# 		#self.updateWorkerView()


# 	def dequeue(self):
# 		""" Dequeue a render task from the queue and start rendering.
# 			THIS IS ALL A BIT ROPEY ATM
# 		"""
# 		if self.workerStatus != "idle":
# 			return False
# 		#elif self.workerStatus != "rendering":

# 		self.renderTaskInterrupted = False
# 		self.renderTaskErrors = 0
# 		self.renderOutput = ""
# 		self.startTimeSec = time.time()  # Used for measuring the time spent rendering
# 		startTime = time.strftime(self.timeFormatStr)

# 		#self.rq.loadXML(quiet=True)  # Reload XML data - this is being done by the dequeuing function

# 		# Look for a suitable job to render - perhaps check here for a few
# 		# easy-to-detect errors, i.e. existence of scene, render command, etc.
# 		jobElement = self.rq.dequeueJob()
# 		if jobElement is None:
# 			#verbose.message("[%s] No jobs to render." %self.localhost)
# 			return False
# 		self.renderJobID = jobElement.get('id')

# 		# Look for tasks to start rendering
# 		self.renderTaskID, frames = self.rq.dequeueTask(self.renderJobID, self.localhost)
# 		if not self.renderTaskID:
# 			#verbose.message("[%s] Job ID %s: No tasks to render." %(self.localhost, self.renderJobID))
# 			return False

# 		#verbose.message("[%s] Job ID %s, Task ID %s: Starting render..." %(self.localhost, self.renderJobID, self.renderTaskID))
# 		if frames == 'Unknown':
# 			frameList = frames
# 		else:
# 			frameList = sequence.numList(frames)
# 			startFrame = min(frameList)
# 			endFrame = max(frameList)


# 		jobType = self.rq.getValue(jobElement, 'type')
# 		if jobType == 'Maya':
# 			# try:
# 			# 	renderCmd = '"%s"' %os.environ['MAYARENDERVERSION'] # store this in XML as maya version may vary with project
# 			# except KeyError:
# 			# 	print "ERROR: Path to Maya Render command executable not found. This can be set with the environment variable 'MAYARENDERVERSION'."
# 			#renderCmd = '"%s"' %os.path.normpath(self.rq.getValue(jobElement, 'mayaRenderCmd'))
# 			renderCmd = self.rq.getValue(jobElement, 'mayaRenderCmd')
# 			# if not os.path.isfile(renderCmd): # disabled this check 
# 			# 	print "ERROR: Maya render command not found: %s" %renderCmd
# 			# 	return False

# 			sceneName = self.rq.getValue(jobElement, 'mayaScene')
# 			# if not os.path.isfile(sceneName): # check scene exists - disabled for now as could cause worker to get stuck in a loop
# 			# 	print "ERROR: Scene not found: %s" %sceneName
# 			# 	self.rq.requeueTask(self.renderJobID, self.renderTaskID)
# 			# 	#self.rq.setStatus(self.renderJobID, "Failed")
# 			# 	return False

# 			cmdStr = ''
# 			args = '-proj "%s"' %self.rq.getValue(jobElement, 'mayaProject')

# 			mayaFlags = self.rq.getValue(jobElement, 'mayaFlags')
# 			if mayaFlags is not None:
# 				args += ' %s' %mayaFlags

# 			# Construct command(s)
# 			if frames == 'Unknown':
# 				cmdStr = '"%s" %s "%s"' %(renderCmd, args, sceneName)
# 			else:
# 				cmdStr += '"%s" %s -s %d -e %d "%s"' %(renderCmd, args, int(startFrame), int(endFrame), sceneName)

# 		elif jobType == 'Nuke':
# 			renderCmd = self.rq.getValue(jobElement, 'nukeRenderCmd')
# 			scriptName = self.rq.getValue(jobElement, 'nukeScript')

# 			cmdStr = ''
# 			args = ''

# 			nukeFlags = self.rq.getValue(jobElement, 'nukeFlags')
# 			if nukeFlags is not None:
# 				args += ' %s' %nukeFlags

# 			# Construct command(s)
# 			if frames == 'Unknown':
# 				cmdStr = '"%s" %s -x "%s"' %(renderCmd, args, scriptName)
# 			else:
# 				cmdStr += '"%s" %s -F %s -x "%s"' %(renderCmd, args, frames, scriptName)


# 		# Set rendering status
# 		# verbose.print_(cmdStr, 4)

# 		# Fill info fields
# 		#self.ui.taskInfo_label.setText("Rendering %s %s from '%s'" %(verbose.pluralise("frame", len(frameList)), frames, self.rq.getValue(jobElement, 'name')))
# 		#self.ui.runningTime_label.setText(startTime)  # change this to display the task running time
# 		self.ui.runningTime_label.setText( str(datetime.timedelta(seconds=0)) )

# 		self.setWorkerStatus("rendering")
# 		self.renderProcess.start(cmdStr)
# 		self.updateRenderQueueView()


# 	def updateTimers(self):
# 		""" Calculate elapsed time and update relevant UI fields.
# 		"""
# 		if self.workerStatus == "rendering":
# 			elapsedTimeSec = time.time() - self.startTimeSec
# 			self.ui.runningTime_label.setText( str(datetime.timedelta(seconds=int(elapsedTimeSec))) )
# 			# this could also update the appropriate render queue tree widget item, if I can figure out how to do that


# 	def renderComplete(self):
# 		""" This code should only be executed after successful task
# 			completion.
# 		"""
# 		totalTimeSec = time.time() - self.startTimeSec  # Calculate time spent rendering task

# 		# self.ui.taskInfo_label.setText("")
# 		# self.ui.runningTime_label.setText("")
# 		if self.renderTaskInterrupted:
# 			self.rq.requeueTask(self.renderJobID, self.renderTaskID)  # perhaps set a special status to indicate render was killed, allowing the user to requeue manually?
# 		elif self.renderTaskErrors:
# 			self.rq.failTask(self.renderJobID, self.renderTaskID, self.localhost, taskTime=totalTimeSec)
# 		else:
# 			self.rq.completeTask(self.renderJobID, self.renderTaskID, self.localhost, taskTime=totalTimeSec)

# 		# Set worker status based on user option
# 		if self.actionWorkerStopAfterTask.isChecked():
# 			self.setWorkerStatus("disabled")
# 		else:
# 			self.setWorkerStatus("idle")
# 			self.dequeue()  # Dequeue next task immediately to prevent wait for next polling interval

# 		self.updateRenderQueueView()


# 	def killRenderProcess(self):
# 		""" Kill the rendering process. This will also stop the local worker.
# 		"""
# 		#verbose.message("Attempting to kill process %s" %self.renderProcess)

# 		self.actionWorkerStopAfterTask.setChecked(True)  # This is a fudge to prevent the renderComplete function from re-enabling the worker after rendering task was killed by user
# 		self.renderTaskInterrupted = True

# 		if self.workerStatus == "rendering":
# 			#self.renderProcess.terminate()
# 			self.renderProcess.kill()
# 		#else:
# 		#	verbose.message("No render in progress.")

# 		#totalTimeSec = time.time() - self.startTimeSec  # Calculate time spent rendering task

# 		# self.ui.taskInfo_label.setText("")
# 		# self.ui.runningTime_label.setText("")
# 		#self.rq.completeTask(self.renderJobID, self.renderTaskID)
# 		#self.rq.requeueTask(self.renderJobID, self.renderTaskID)  # perhaps set a special status to indicate render was killed, allowing the user to requeue manually?

# 		#self.setWorkerStatus("disabled")

# 		#self.updateRenderQueueView()


# 	def closeEvent(self, event):
# 		""" Event handler for when window is closed.
# 		"""

# 		# Confirmation dialog
# 		# if self.workerStatus == "rendering":
# 		# 	import pDialog

# 		# 	dialogTitle = 'Render in progress'
# 		# 	dialogMsg = ''
# 		# 	dialogMsg += 'There is currently a render in progress on the local worker. Closing the Render Queue window will also kill the render.\n'
# 		# 	dialogMsg += 'Are you sure you want to quit?'

# 		# 	dialog = pDialog.dialog()
# 		# 	if dialog.display(dialogMsg, dialogTitle):
# 		# 		event.accept()
# 		# 	else:
# 		# 		event.ignore()
# 		# 		return

# 		# Kill the rendering process
# 		self.killRenderProcess()

# 		# Requeue the task that's currently rendering
# 		#self.rq.requeueTask(jobTaskID[0], jobTaskID[1])

# 		# Stop timers
# 		self.timerUpdateView.stop()
# 		self.timerDequeue.stop()
# 		self.timerUpdateTimer.stop()

# 		# Store window geometry and state of certain widgets
# 		# self.storeWindow()
# 		# self.settings.setValue("splitterSizes", self.ui.splitter.saveState())
# 		# self.settings.setValue("renderQueueView", self.ui.renderQueue_treeWidget.header().saveState())

# 		QtWidgets.QMainWindow.closeEvent(self, event)

# # ----------------------------------------------------------------------------
# # End main application class
# # ----------------------------------------------------------------------------
