#!/usr/bin/python

# submit.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Render Submitter
# A UI for creating render jobs to send to a render queue manager.


import getpass
import os
import re
import sys
import time
import traceback

from Qt import QtCore, QtGui, QtWidgets
import ui_template as UI

# Import custom modules
import oswrapper
import common
import submit_deadline as deadline
import database
import sequence
#import settingsData
#import userPrefs
#import verbose


# ----------------------------------------------------------------------------
# Environment detection - TEMP HACK
# ----------------------------------------------------------------------------

#ENVIRONMENT = os.environ.get('IC_ENV', "STANDALONE")

try:
	import maya.cmds as mc
	#ENVIRONMENT = "MAYA"
except ImportError:
	pass

try:
	import hou
	#ENVIRONMENT = "HOUDINI"
except ImportError:
	pass

try:
	import nuke
	import nukescripts
	#ENVIRONMENT = "NUKE"
except ImportError:
	pass


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# Set window title and object names
WINDOW_TITLE = "Render Submit"
WINDOW_OBJECT = "RenderSubmitUI"

# Set the UI and the stylesheet
UI_FILE = 'submit.ui'
STYLESHEET = 'style.qss'  # Set to None to use the parent app's stylesheet

# Other options
PREFS_FILE = os.path.join(os.environ['HOME'], '.renderqueue', 'submit.json')
STORE_WINDOW_GEOMETRY = True


# ----------------------------------------------------------------------------
# Main window class
# ----------------------------------------------------------------------------

class RenderSubmitUI(QtWidgets.QMainWindow, UI.TemplateUI):
	""" Render submit UI.
	"""
	def __init__(self, parent=None):
		super(RenderSubmitUI, self).__init__(parent)
		self.parent = parent

		self.setupUI(
			window_object=WINDOW_OBJECT,
			window_title=WINDOW_TITLE,
			ui_file=UI_FILE,
			stylesheet=STYLESHEET,
			prefs_file=PREFS_FILE,
			store_window_geometry=STORE_WINDOW_GEOMETRY)  # re-write as **kwargs ?

		self.conformFormLayoutLabels(self.ui)

		# Set window flags
		self.setWindowFlags(QtCore.Qt.Tool)

		# Set other Qt attributes
		if parent == None:
			self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

		# Set up keyboard shortcuts
		self.shortcutExpertMode = QtWidgets.QShortcut(self)
		self.shortcutExpertMode.setKey('Ctrl+Shift+E')
		self.shortcutExpertMode.activated.connect(self.toggleExpertMode)

		# Set icons
		self.ui.commandBrowse_toolButton.setIcon(self.iconSet('folder-open-symbolic.svg'))
		self.ui.mayaSceneBrowse_toolButton.setIcon(self.iconSet('folder-open-symbolic.svg'))
		self.ui.houdiniSceneBrowse_toolButton.setIcon(self.iconSet('folder-open-symbolic.svg'))
		self.ui.nukeScriptBrowse_toolButton.setIcon(self.iconSet('folder-open-symbolic.svg'))

		self.ui.getCameras_toolButton.setIcon(self.iconSet('view-refresh.svg'))
		self.ui.getPools_toolButton.setIcon(self.iconSet('view-refresh.svg'))
		#self.ui.getPools2_toolButton.setIcon(self.iconSet('view-refresh.svg'))
		self.ui.getGroups_toolButton.setIcon(self.iconSet('view-refresh.svg'))

		self.ui.frameListOptions_toolButton.setIcon(self.iconSet('configure.svg'))
		self.ui.layerOptions_toolButton.setIcon(self.iconSet('configure.svg'))
		self.ui.writeNodeOptions_toolButton.setIcon(self.iconSet('configure.svg'))

		# Connect signals & slots
		self.ui.submitTo_comboBox.currentIndexChanged.connect(self.setQueueManagerFromComboBox)
		self.ui.jobType_comboBox.currentIndexChanged.connect(self.setJobTypeFromComboBox)

		self.ui.commandBrowse_toolButton.clicked.connect(self.commandBrowse)
		self.ui.mayaScene_comboBox.currentIndexChanged.connect(self.applySettings)
		self.ui.mayaSceneBrowse_toolButton.clicked.connect(self.sceneBrowse)
		self.ui.houdiniScene_comboBox.currentIndexChanged.connect(self.applySettings)
		self.ui.houdiniSceneBrowse_toolButton.clicked.connect(self.sceneBrowse)
		self.ui.nukeScript_comboBox.currentIndexChanged.connect(self.applySettings)
		self.ui.nukeScriptBrowse_toolButton.clicked.connect(self.sceneBrowse)

		self.ui.getCameras_toolButton.clicked.connect(self.getCameras)

		# self.ui.layers_groupBox.toggled.connect(self.getRenderLayers)
		# self.ui.layers_lineEdit.editingFinished.connect(self.checkRenderLayers)

		# self.setupWidgets(self.ui.settings_scrollAreaWidgetContents)
		# self.ui.renderer_comboBox.currentIndexChanged.connect(self.storeComboBoxValue)
		# self.ui.layers_lineEdit.textEdited.connect(self.storeLineEditValue)

		self.ui.frames_lineEdit.editingFinished.connect(self.calcFrameList)
		#self.ui.frames_lineEdit.textChanged.connect(self.calcFrameList)
		self.ui.taskSize_spinBox.valueChanged.connect(self.calcFrameList)
		self.ui.getPools_toolButton.clicked.connect(self.getPools)
		#self.ui.getPools2_toolButton.clicked.connect(self.getPools)
		self.ui.getGroups_toolButton.clicked.connect(self.getGroups)

		self.ui.submit_pushButton.clicked.connect(self.submit)
		self.ui.close_pushButton.clicked.connect(self.close)

		# Context menus
		self.addContextMenu(self.ui.frameListOptions_toolButton, "Shot default", self.getFrameRangeFromShotSettings)
		if UI.ENVIRONMENT != "STANDALONE":
			self.addContextMenu(self.ui.frameListOptions_toolButton, "Render settings", self.getFrameRangeFromRenderSettings)
		self.addContextMenu(self.ui.frameListOptions_toolButton, "Sequential", self.setFrameListPreset)
		#self.addContextMenu(self.ui.frameListOptions_toolButton, "Reverse order", self.setFrameListPreset)
		self.addContextMenu(self.ui.frameListOptions_toolButton, "Render first and last frames before others", self.setFrameListPreset)

		self.addContextMenu(self.ui.layerOptions_toolButton, "Clear (auto-detect from scene at render time)", self.ui.layers_lineEdit.clear)
		self.addContextMenu(self.ui.layerOptions_toolButton, "Current layer only", self.getCurrentRenderLayer)
		self.addContextMenu(self.ui.layerOptions_toolButton, "All renderable layers", self.getRenderLayers)

		self.addContextMenu(self.ui.writeNodeOptions_toolButton, "Clear (all)", self.ui.writeNodes_lineEdit.clear)
		self.addContextMenu(self.ui.writeNodeOptions_toolButton, "Selected write node only", self.getCurrentRenderLayer)
		self.addContextMenu(self.ui.writeNodeOptions_toolButton, "All write nodes", self.getRenderLayers)

		# Set input validators
		layer_list_validator = QtGui.QRegExpValidator(QtCore.QRegExp(r'[\w, ]+'), self.ui.layers_lineEdit)
		self.ui.layers_lineEdit.setValidator(layer_list_validator)

		frame_list_validator = QtGui.QRegExpValidator(QtCore.QRegExp(r'[\d\-x, ]+'), self.ui.frames_lineEdit)
		self.ui.frames_lineEdit.setValidator(frame_list_validator)

		self.expertMode = False


	def display(self, submitTo=None, jobtype=None, scene=None, frameRange=None, layers=None, flags=None):
		""" Display the window.
		"""
		self.returnValue = False

		#print(jobtype, scene)

		# Read user prefs config file - if it doesn't exist it will be created
		#userPrefs.read()

		# Set 'Submit to' option depending on the parent window, or user prefs
		try:
			parentWindowTitle = self.parent.windowTitle()
		except AttributeError:
			parentWindowTitle = "None"
		if parentWindowTitle.startswith("Render Queue"):
			self.submitTo = "Render Queue"
			self.ui.submitTo_label.setEnabled(False)
			self.ui.submitTo_comboBox.setEnabled(False)
		else:
			#self.submitTo = userPrefs.query('rendersubmit', 'submitto', default=self.ui.submitTo_comboBox.currentText())
			self.submitTo = "Deadline" # TEMP HACK
			self.ui.submitTo_label.setEnabled(True)
			self.ui.submitTo_comboBox.setEnabled(True)
		self.ui.submitTo_comboBox.setCurrentIndex(self.ui.submitTo_comboBox.findText(self.submitTo))
		self.ui.submit_pushButton.setText("Submit to %s" %self.submitTo)
		self.setQueueManagerFromComboBox()

		# Set job type from pipeline environment when possible
		if UI.ENVIRONMENT == "STANDALONE":
			#self.jobType = userPrefs.query('rendersubmit', 'lastrenderjobtype', default=self.ui.jobType_comboBox.currentText())
			if jobtype:
				self.jobType = jobtype
			else:
				self.jobType = self.ui.jobType_comboBox.currentText() # TEMP HACK
			self.ui.jobType_comboBox.setCurrentIndex(self.ui.jobType_comboBox.findText(self.jobType))
			if scene:  # For drag-n-drop submissions
				if self.jobType == 'Maya':
					self.ui.mayaScene_comboBox.addItem(scene)
				elif self.jobType == 'Houdini':
					self.ui.houdiniScene_comboBox.addItem(scene)
				elif self.jobType == 'Nuke':
					self.ui.nukeScript_comboBox.addItem(scene)
			self.ui.camera_label.setEnabled(False)
			self.ui.camera_comboBox.setEnabled(False)
			self.ui.getCameras_toolButton.setEnabled(False)
			self.ui.layerOptions_toolButton.setEnabled(False)
			self.ui.writeNodeOptions_toolButton.setEnabled(False)
			self.setJobType()
			#self.setSceneList()

		elif UI.ENVIRONMENT == "MAYA":
			self.jobType = "Maya"
			self.ui.jobType_comboBox.setCurrentIndex(self.ui.jobType_comboBox.findText(self.jobType))
			self.setJobType()

			self.ui.mayaScene_comboBox.clear()
			sceneName = mc.file(query=True, sceneName=True)
			#sceneName = scene
			if sceneName:  # Check we're not working in an unsaved scene
				relPath = self.makePathRelative(oswrapper.absolutePath(sceneName))
				if relPath:
					self.ui.mayaScene_comboBox.addItem(relPath)
					self.ui.submit_pushButton.setEnabled(True)
			else:
				msg = "Scene must be saved before submitting render."
				mc.warning(msg)
				#mc.confirmDialog(title="Scene not saved", message=msg, icon="warning", button="Close")
				self.ui.mayaScene_comboBox.addItem(msg)
				# self.ui.mayaScene_comboBox.lineEdit().setProperty("warning", True)
				# self.ui.mayaScene_comboBox.style().unpolish(self.ui.mayaScene_comboBox)
				# self.ui.mayaScene_comboBox.style().polish(self.ui.mayaScene_comboBox)
				self.ui.submit_pushButton.setToolTip(msg)
				self.ui.submit_pushButton.setEnabled(False)

			self.ui.jobType_label.setEnabled(False)
			self.ui.jobType_comboBox.setEnabled(False)
			#self.ui.mayaScene_label.setEnabled(False)
			self.ui.mayaScene_comboBox.setEnabled(False)
			#self.ui.mayaScene_comboBox.lineEdit().setReadOnly(True)
			#self.ui.mayaSceneBrowse_toolButton.setEnabled(False)
			self.ui.mayaSceneBrowse_toolButton.hide()
			self.ui.renderer_label.setEnabled(False)
			self.ui.renderer_comboBox.setEnabled(False)
			self.ui.useRenderSetup_checkBox.setEnabled(False)

			self.getCameras()
			#self.getRenderLayers()
			self.getRenderers()

			if layers:
				self.ui.layers_lineEdit.setText(layers)

		elif UI.ENVIRONMENT == "HOUDINI":  # Not fully implemented yet
			self.jobType = "Houdini"
			self.ui.jobType_comboBox.setCurrentIndex(self.ui.jobType_comboBox.findText(self.jobType))
			self.setJobType()

			self.ui.houdiniScene_comboBox.clear()
			if scene:
				self.ui.houdiniScene_comboBox.addItem(scene)

			self.ui.jobType_label.setEnabled(False)
			self.ui.jobType_comboBox.setEnabled(False)
			#self.ui.houdiniScene_label.setEnabled(False)
			self.ui.houdiniScene_comboBox.setEnabled(False)
			#self.ui.houdiniScene_comboBox.lineEdit().setReadOnly(True)
			#self.ui.houdiniSceneBrowse_toolButton.setEnabled(False)
			self.ui.houdiniSceneBrowse_toolButton.hide()

		elif UI.ENVIRONMENT == "NUKE":
			self.jobType = "Nuke"
			self.ui.jobType_comboBox.setCurrentIndex(self.ui.jobType_comboBox.findText(self.jobType))
			self.setJobType()

			self.ui.nukeScript_comboBox.clear()
			scriptName = nuke.value('root.name')
			#scriptName = scene
			if scriptName:  # Check we're not working in an unsaved script
				relPath = self.makePathRelative(oswrapper.absolutePath(scriptName))
				if relPath:
					self.ui.nukeScript_comboBox.addItem(relPath)
					self.ui.submit_pushButton.setEnabled(True)
			else:
				msg = "Script must be saved before submitting render."
				nuke.warning(msg)
				#nuke.message(msg)
				self.ui.nukeScript_comboBox.addItem(msg)
				self.ui.submit_pushButton.setToolTip(msg)
				self.ui.submit_pushButton.setEnabled(False)

			self.ui.jobType_label.setEnabled(False)
			self.ui.jobType_comboBox.setEnabled(False)
			#self.ui.nukeScript_label.setEnabled(False)
			self.ui.nukeScript_comboBox.setEnabled(False)
			#self.ui.nukeScript_comboBox.lineEdit().setReadOnly(True)
			#self.ui.nukeScriptBrowse_toolButton.setEnabled(False)
			self.ui.nukeScriptBrowse_toolButton.hide()

			if layers:
				self.ui.writeNodes_lineEdit.setText(layers)

		self.numList = []
		if frameRange:
			self.ui.frames_lineEdit.setText(frameRange)
		else:
			pass
			#self.getFrameRangeFromShotSettings()
		self.calcFrameList()

		if flags:
			self.ui.flags_lineEdit.setText(flags)

		self.show()
		self.raise_()

		return self.returnValue


	def toggleExpertMode(self):
		""" Toggle expert mode where all UI items are visible.
		"""
		self.expertMode = not self.expertMode
		# self.ui.render_groupBox.setEnabled(self.expertMode)
		# self.ui.render_groupBox.setVisible(self.expertMode)


	# @QtCore.Slot()
	def applySettings(self):
		""" Apply the saved submission settings for the chosen scene/script
			file.
		"""
		if self.jobType == "Maya":
			comboBox = self.ui.mayaScene_comboBox
		elif self.jobType == "Houdini":
			comboBox = self.ui.houdiniScene_comboBox
		elif self.jobType == "Nuke":
			comboBox = self.ui.nukeScript_comboBox
		scene = self.makePathAbsolute(comboBox.currentText()).replace("\\", "/")

		# self.prefs.read_new(common.settings_file(scene, suffix="_submissionData.json"))
		# if self.prefs:
		# 	#print(self.prefs)
		# 	#self.prefs.read()
		# 	self.setupWidgets(self.ui, updateOnly=True)


	# @QtCore.Slot()
	def setQueueManagerFromComboBox(self):
		""" Set queue manager to submit job to - called when the job type
			combo box value is changed.
		"""
		self.submitTo = self.ui.submitTo_comboBox.currentText()
		#userPrefs.edit('rendersubmit', 'submitto', self.submitTo) # deprecated
		self.ui.submit_pushButton.setText("Submit to %s" %self.submitTo)

		# Show/hide specific UI elements based on selected queue manager
		# rq_show_list = [self.ui.flags_label, self.ui.flags_lineEdit]
		rq_show_list = [self.ui.interactiveLicense_checkBox]
		dl_show_list = [self.ui.group_label, self.ui.group_frame,
						self.ui.pool2_comboBox, self.ui.getPools_toolButton]

		for item in rq_show_list + dl_show_list:
			item.setEnabled(False)
			#item.hide()
		if self.submitTo == "Render Queue":
			self.ui.pool2_comboBox.hide()  # TEMP
			for item in rq_show_list:
				item.setEnabled(True)
				#item.show()
		if self.submitTo == "Deadline":
			self.ui.pool2_comboBox.show()  # TEMP
			for item in dl_show_list:
				item.setEnabled(True)
				#item.show()


	# @QtCore.Slot()
	def setJobTypeFromComboBox(self):
		""" Set job type - called when the job type combo box value is
			changed.
		"""
		self.jobType = self.ui.jobType_comboBox.currentText()
		#userPrefs.edit('rendersubmit', 'lastrenderjobtype', self.jobType)
		self.setJobType()
		if UI.ENVIRONMENT == "STANDALONE":
			self.setSceneList()


	def setJobType(self):
		""" Setup some global variables and UI elements depending on the job
			type.
		"""
		self.ui.generic_groupBox.hide()
		self.ui.maya_groupBox.hide()
		self.ui.houdini_groupBox.hide()
		self.ui.nuke_groupBox.hide()

		if self.jobType == "Generic":
			self.ui.generic_groupBox.show()

		elif self.jobType == "Maya":
			self.ui.maya_groupBox.show()
			try:
				#self.relativeScenesDir = oswrapper.absolutePath(os.environ['MAYASCENESDIR'])
				self.relativeScenesDir = oswrapper.absolutePath(os.environ['UHUB_MAYA_SCENES_PATH'])
			except KeyError:
				self.relativeScenesDir = ""

		elif self.jobType == "Houdini":
			self.ui.houdini_groupBox.show()
			try:
				#self.relativeScenesDir = oswrapper.absolutePath(os.environ['HOUDINISCENESDIR'])
				self.relativeScenesDir = oswrapper.absolutePath(os.environ['UHUB_HOUDINI_HIP_PATH'])
			except KeyError:
				self.relativeScenesDir = ""

		elif self.jobType == "Nuke":
			self.ui.nuke_groupBox.show()
			try:
				#self.relativeScenesDir = oswrapper.absolutePath(os.environ['NUKESCRIPTSDIR'])
				self.relativeScenesDir = oswrapper.absolutePath(os.environ['UHUB_NUKE_SCRIPTS_PATH'])
			except KeyError:
				self.relativeScenesDir = ""

		# Representative string to replace the path specified above
		self.relativeScenesToken = "..."


	def setSceneList(self):
		""" Clear specified scene menu and populate from recent file list.
			Only used in standalone mode.
		"""
		try:
			if self.jobType == "Maya":
				comboBox = self.ui.mayaScene_comboBox
			elif self.jobType == "Nuke":
				comboBox = self.ui.nukeScript_comboBox
			comboBox.clear()

			import recentFiles
			for filePath in recentFiles.getLs(self.jobType):
				fullPath = oswrapper.absolutePath(os.environ['SHOTPATH'] + filePath)
				relPath = self.makePathRelative(fullPath)
				if relPath:
					comboBox.addItem(relPath)
		except:
			pass


	def makePathRelative(self, absPath):
		""" Convert an absolute path to a relative path.
		"""
		if self.relativeScenesDir is "":
			return absPath
		elif absPath.startswith(self.relativeScenesDir):
			return absPath.replace(self.relativeScenesDir, self.relativeScenesToken)
		else:
			return False


	def makePathAbsolute(self, relPath):
		""" Convert a relative path to an absolute path.
		"""
		return relPath.replace(self.relativeScenesToken, self.relativeScenesDir)


	def snapshot(self):
		""" Save a copy (snapshot) of the current scene, appended with the
			date and time. Return the path to the snapshot, ready to be
			submitted.
			CURRENTLY NUKE-SPECIFIC
		"""
		timestamp = time.strftime(r"%Y%m%d_%H%M%S")

		# if UI.ENVIRONMENT == "MAYA":
		# 	currentScene = mc.file(query=True, sceneName=True)
		# 	base, ext = os.path.splitext(currentScene)
		# 	snapshotScene = "%s_snapshot_%s%s" %(base, timestamp, ext)
		# 	nuke.scriptSave(snapshotScene)
		# 	nuke.root()['name'].setValue(currentScene)
		# 	return snapshotScene

		if UI.ENVIRONMENT == "NUKE":
			currentScript = nuke.root()['name'].value()
			#dirname, basename = os.path.split(currentScript)
			#snapshotScript = os.path.join(tmpdir, basename)
			base, ext = os.path.splitext(basename)
			snapshotScript = "%s_snapshot_%s%s" %(base, timestamp, ext)
			nuke.scriptSave(snapshotScript)
			nuke.root()['name'].setValue(currentScript)
			return snapshotScript


	def commandBrowse(self):
		""" Browse for a command.
		"""
		#fileDir = os.environ.get('JOBPATH', '.')  # Go to current dir if env var is not set
		fileDir = os.environ.get('UHUB_JOB_PATH', '.')  # Go to current dir if env var is not set
		fileFilter = "All files (*.*)"

		currentDir = os.path.dirname(self.ui.command_lineEdit.text())
		if os.path.exists(currentDir):
			startingDir = currentDir
		else:
			startingDir = fileDir

		# filePath = QtWidgets.QFileDialog.getOpenFileName(self, self.tr('Files'), startingDir, fileFilter)[0]
		filePath = self.fileDialog(startingDir, fileFilter)

		if filePath:
			newEntry = oswrapper.absolutePath(filePath)
			self.ui.command_lineEdit.setText(newEntry)


	def sceneBrowse(self):
		""" Browse for a scene/script file.
		"""
		if self.jobType == "Maya":
			comboBox = self.ui.mayaScene_comboBox
			fileDir = os.environ.get('UHUB_MAYA_SCENES_PATH', '.')  # Go to current dir if env var is not set
			fileFilter = "Maya files (*.ma *.mb)"
			fileTerminology = "scenes"

		elif self.jobType == "Houdini":
			comboBox = self.ui.houdiniScene_comboBox
			fileDir = os.environ.get('UHUB_HOUDINI_HIP_PATH', '.')  # Go to current dir if env var is not set
			fileFilter = "Houdini files (*.hip)"
			fileTerminology = "scenes"

		elif self.jobType == "Nuke":
			comboBox = self.ui.nukeScript_comboBox
			fileDir = os.environ.get('UHUB_NUKE_SCRIPTS_PATH', '.')  # Go to current dir if env var is not set
			fileFilter = "Nuke files (*.nk)"
			fileTerminology = "scripts"

		# else:
		# 	fileDir = os.environ.get('JOBPATH', '.')  # Go to current dir if env var is not set
		# 	fileFilter = "All files (*.*)"
		# 	fileTerminology = "commands"

		currentDir = os.path.dirname(self.makePathAbsolute(comboBox.currentText()))
		if os.path.exists(currentDir):
			startingDir = currentDir
		else:
			startingDir = fileDir

		# filePath = QtWidgets.QFileDialog.getOpenFileName(self, self.tr('Files'), startingDir, fileFilter)[0]
		filePath = self.fileDialog(startingDir, fileFilter)
		#print(filePath)

		if filePath:
			#newEntry = self.makePathRelative(oswrapper.absolutePath(filePath))
			newEntry = oswrapper.absolutePath(filePath)
			if newEntry:
				comboBox.removeItem(comboBox.findText(newEntry))  # If the entry already exists in the list, delete it
				comboBox.insertItem(0, newEntry)
				comboBox.setCurrentIndex(0)  # Always insert the new entry at the top of the list and select it
			else:
				#verbose.warning("Only %s belonging to the current shot can be submitted." %fileTerminology)
				print("Warning: Only %s belonging to the current shot can be submitted." %fileTerminology)


	def getFrameRangeFromShotSettings(self):
		""" Get frame range from shot settings.
		"""
		try:
			#frRange = "%d-%d" %(int(os.environ['STARTFRAME']), int(os.environ['ENDFRAME']))  # Icarus
			frRange = "%d-%d" %(int(os.environ['UHUB_STARTFRAME']), int(os.environ['UHUB_ENDFRAME']))  # U-HUB
			self.ui.frames_lineEdit.setText(frRange)
		except KeyError:
			self.ui.frames_lineEdit.setText("")


	def getFrameRangeFromRenderSettings(self):
		""" Get frame range from DCC app settings.
		"""
		if UI.ENVIRONMENT == "MAYA":
			start_frame = int(mc.getAttr('defaultRenderGlobals.startFrame'))
			end_frame = int(mc.getAttr('defaultRenderGlobals.endFrame'))

		elif UI.ENVIRONMENT == "HOUDINI":
			# Note this is the time slider (playbar) range, not the render
			# settings
			start_frame = hou.playbar.playbackRange()[0]
			end_frame = hou.playbar.playbackRange()[1]

		elif UI.ENVIRONMENT == "NUKE":
			start_frame = nuke.Root()['first_frame'].getValue()
			end_frame = nuke.Root()['last_frame'].getValue()

		self.ui.frames_lineEdit.setText("%d-%d" %(start_frame, end_frame))


	def getRenderableCameras(self):
		""" Returns list of renderable cameras in the scene.
			MAYA-SPECIFIC
		"""
		noSelectText = ""
		camera_list = [noSelectText, ]

		if UI.ENVIRONMENT == "MAYA":
			#cameras = mc.ls(cameras=True)
			persp_cameras = mc.listCameras(perspective=True)
			ortho_cameras = mc.listCameras(orthographic=True)
			return camera_list + persp_cameras + ortho_cameras

		else:
			return camera_list

			# for camera in cameras:
			# 	if mc.getAttr(camera+'.renderable'):
			# 		camera_list.insert(0, camera)
			# 	else:
			# 		camera_list.append(camera)

			# return camera_list


	def getCurrentRenderLayer(self):
		""" Get current Maya render layer or selected Nuke write nodes &
			populate widget.
		"""
		if UI.ENVIRONMENT == "MAYA":
			currentLayer = mc.editRenderLayerGlobals(query=True, currentRenderLayer=True)
			self.ui.layers_lineEdit.setText(currentLayer)

		elif UI.ENVIRONMENT == "NUKE":
			writeNodeStr = ", ".join(n for n in self.getWriteNodes(selected=True))
			self.ui.writeNodes_lineEdit.setText(writeNodeStr)


	def getRenderLayers(self):
		""" Get Maya render layers or Nuke write nodes & populate widget.
		"""
		if UI.ENVIRONMENT == "MAYA":
			layerStr = ", ".join(n for n in self.getRenderableLayers())
			self.ui.layers_lineEdit.setText(layerStr)

			# Set Render Setup / Legacy Render Layers option
			checkBox = self.ui.useRenderSetup_checkBox
			checkBox.setChecked(not self.getCheckBoxValue(checkBox))  # Toggle value to force update
			checkBox.setChecked(mc.optionVar(query="renderSetupEnable"))

		elif UI.ENVIRONMENT == "NUKE":
			writeNodeStr = ", ".join(n for n in self.getWriteNodes(selected=False))
			self.ui.writeNodes_lineEdit.setText(writeNodeStr)


	def getPools(self):
		""" Get Deadline pools & populate combo box.
		"""
		pools = deadline.get_pools()
		if pools:
			self.populateComboBox(self.ui.pool_comboBox, pools)
			self.populateComboBox(self.ui.pool2_comboBox, pools)


	def getGroups(self):
		""" Get Deadline groups & populate combo box.
		"""
		groups = deadline.get_groups()
		if groups:
			self.populateComboBox(self.ui.group_comboBox, groups)


	def getRenderers(self):
		""" Get Maya renderers & populate combo box.
			MAYA-SPECIFIC
		"""
		renderers = self.getRenderer()
		rendererLs = [renderers]
		# print(rendererLs)
		self.populateComboBox(self.ui.renderer_comboBox, rendererLs)


	def getCameras(self):
		""" Get Maya cameras & populate combo box.
			MAYA-SPECIFIC
		"""
		cameras = self.getRenderableCameras()
		self.populateComboBox(self.ui.camera_comboBox, cameras, addEmptyItems=True)


	# @QtCore.Slot()
	def setFrameListPreset(self):
		""" Modify frame list from preset menu.
		"""
		#print(self.sender().text())
		if self.sender().text() == "Sequential":
			num_list = sequence.numList(self.ui.frames_lineEdit.text(), sort=True, quiet=True)
			if self.numList:
				self.ui.frames_lineEdit.setText(sequence.numRange(num_list))
			else:
				pass

		elif self.sender().text() == "Reverse order":
			pass

		elif self.sender().text() == "Render first and last frames before others":
			frames_str = self.ui.frames_lineEdit.text()
			num_list = sequence.numList(frames_str, sort=True, quiet=True)
			if self.numList:
				first = min(num_list)
				last = max(num_list)
				frames_str_prefix = "%d, %d" %(first, last)
				if not frames_str.startswith(frames_str_prefix):
					self.ui.frames_lineEdit.setText("%s, %s" %(frames_str_prefix, frames_str))
			else:
				pass


	def calcFrameList(self, quiet=True):
		""" Calculate list of frames to be rendered.
			TODO: perhaps run on a separate thread to keep UI snappy?
		"""
		try:
			self.numList = sequence.numList(self.ui.frames_lineEdit.text(), sort=False, quiet=quiet)
			if self.numList is False:
				#raise RuntimeError("Invalid entry for frame range.")
				if not quiet:
					#verbose.warning("Invalid entry for frame range.")
					print("Warning: Invalid entry for frame range.")
				# self.ui.frames_lineEdit.setProperty("mandatoryField", True)
				# self.ui.frames_lineEdit.style().unpolish(self.ui.frames_lineEdit)
				# self.ui.frames_lineEdit.style().polish(self.ui.frames_lineEdit)
				self.numList = []
				self.taskList = ["Unknown", ]

				# msg = "Invalid entry for frame range."
				# #mc.warning(msg)
				# #mc.confirmDialog(title="Scene not saved", message=msg, icon="warning", button="Close")
				# self.ui.submit_pushButton.setToolTip(msg)
				# self.ui.submit_pushButton.setEnabled(False)

				return False

			elif self.numList is None:
				#raise RuntimeError("No frame range specified.")
				if not quiet:
					#verbose.warning("No frame range specified.")
					print("Warning: No frame range specified.")
				# self.ui.frames_lineEdit.setProperty("mandatoryField", True)
				# self.ui.frames_lineEdit.style().unpolish(self.ui.frames_lineEdit)
				# self.ui.frames_lineEdit.style().polish(self.ui.frames_lineEdit)
				self.numList = []
				self.taskList = ["Unknown", ]

				# msg = "No frame range specified."
				# #mc.warning(msg)
				# #mc.confirmDialog(title="Scene not saved", message=msg, icon="warning", button="Close")
				# self.ui.submit_pushButton.setToolTip(msg)
				# self.ui.submit_pushButton.setEnabled(False)

				return False

			else:
				# Update task size slider
				#self.ui.frames_lineEdit.setText(sequence.numRange(self.numList))
				taskSize = self.ui.taskSize_spinBox.value()
				nFrames = len(self.numList)
				if taskSize < nFrames:
					self.ui.taskSize_slider.setMaximum(nFrames)
					self.ui.taskSize_spinBox.setMaximum(nFrames)
					self.ui.taskSize_spinBox.setValue(taskSize)
				else:
					self.ui.taskSize_slider.setMaximum(nFrames)
					self.ui.taskSize_spinBox.setMaximum(nFrames)
					self.ui.taskSize_spinBox.setValue(nFrames)
				if nFrames == 1:
					self.ui.taskSize_slider.setEnabled(False)
					self.ui.taskSize_spinBox.setEnabled(False)
				else:
					self.ui.taskSize_slider.setEnabled(True)
					self.ui.taskSize_spinBox.setEnabled(True)

				# Generate task list for rendering
				self.taskList = []
				sequences = list(sequence.seqRange(self.numList, gen_range=True))
				for seq in sequences:
					chunks = list(sequence.chunks(seq, taskSize))
					for chunk in chunks:
						#self.taskList.append(list(sequence.seqRange(chunk))[0])
						self.taskList.append(sequence.numRange(chunk))

				return True

		except (MemoryError, OverflowError):
			#verbose.warning("Specified frame range value(s) too large to process.")
			print("Warning: Specified frame range value(s) too large to process.")
			return False

		# except RuntimeError:
		# 	if not quiet:
		# 		verbose.warning("Invalid entry for frame range.")
		# 	# self.ui.frames_lineEdit.setProperty("mandatoryField", True)
		# 	# self.ui.frames_lineEdit.style().unpolish(self.ui.frames_lineEdit)
		# 	# self.ui.frames_lineEdit.style().polish(self.ui.frames_lineEdit)
		# 	self.numList = []
		# 	self.taskList = ["Unknown", ]
		# 	return False

		# finally:
		# 	pass


	def getMayaProject(self, scene):
		""" Get the Maya project. If the environment variable is not set, try
			to guess the Maya project directory based on the scene name.
			MAYA-SPECIFIC
		"""
		try:  # Project is implicit if job is set
			#mayaProject = os.environ['MAYADIR'].replace("\\", "/")
			mayaProject = os.environ['UHUB_MAYA_SHOT_PATH'].replace("\\", "/")
		except KeyError:
			mayaProject = scene.split('/scenes')[0]

		return mayaProject


	def getRenderer(self):
		""" Get the current Maya renderer.
			MAYA-SPECIFIC
		"""
		try:
			renderer = mc.getAttr("defaultRenderGlobals.currentRenderer")
		except:
			renderer = ""

		return renderer


	def getRenderableLayers(self, allLayers=False):
		""" Get Maya render layers that are enabled (renderable).
			If 'allLayers' is True, return all (not just renderable) layers.
			MAYA-SPECIFIC
		"""
		layers = mc.ls(type='renderLayer')

		if(allLayers):
			return layers

		else:
			renderableLayers = []
			for layer in layers:
				if mc.getAttr(layer+'.renderable'):
					renderableLayers.append(layer)

			return renderableLayers


	def getWriteNodes(self, selected=True):
		""" Get Nuke write nodes.
			If 'selected' is True, only return selected nodes.
			NUKE-SPECIFIC
		"""
		writeNodes = []

		if selected:
			nodeLs = nuke.selectedNodes('Write')
		else:
			nodeLs = nuke.allNodes('Write')

		for node in nodeLs:
			writeNodes.append(node.name())

		return writeNodes


	def getMayaRenderOutput(self, layer=None):
		""" Get the path of Maya's render output.
			MAYA-SPECIFIC
		"""
		try:
			padding = "#" * mc.getAttr("defaultRenderGlobals.extensionPadding")
			if layer is None:
				path = mc.renderSettings(fullPath=True, 
				                         leaveUnmatchedTokens=True, 
				                         genericFrameImageName=padding)
			else:
				path = mc.renderSettings(fullPath=True, 
				                         layer=layer, 
				                         leaveUnmatchedTokens=True, 
				                         genericFrameImageName=padding)
		except:
			path = [""]

		return path[0]


	def getNukeRenderOutput(self, writeNode):
		""" Get the output path from a Nuke write node.
			NUKE-SPECIFIC
		"""
		node = nuke.toNode(writeNode)

		try:
			#path = node.knob('file').value()  # Gets the unprocessed output file path string
			path = node.knob('file').evaluate()  # Evaluates the path as a Nuke TCL expression
			#path = oswrapper.absolutePath(node.knob('file'))  # Preserves padding but doesn't expand environment variables
		except:
			path = ""

		return path


	def getOutputFilePath(self):
		""" Get Maya's render output file path from the Maya project.
			MAYA-SPECIFIC
		"""
		try:
			path = mc.workspace(expandName=mc.workspace(fileRuleEntry="images"))
		except:  # Make a guess
			#path = ""
			path = oswrapper.absolutePath("$MAYADIR/renders")

		return path


	def getOutputFilePrefix(self):
		""" Get Maya's output file prefix from the render settings.
			MAYA-SPECIFIC
		"""
		try:
			prefix = mc.getAttr("defaultRenderGlobals.imageFilePrefix")
		except:  # Make a guess
			#prefix = ""
			# General default
			#prefix = "<Scene>/<RenderLayer>/<Scene>_<RenderLayer>"
			# Icarus default
			#prefix = "%s/<Scene>/<RenderLayer>/%s_<RenderLayer>" %(os.environ.get('IC_USERNAME', getpass.getuser()), os.environ.['SHOT'])
			# Uhub default
			prefix = "<Scene>/<RenderLayer>/<RenderLayer>_<RenderPass>"

		return prefix


	def guessOutputs(self, path, prefix, scene=None, camera=None, layers=[], 
		             useRenderSetup=False):
		""" Parse Maya's output file prefix and return a full path.
			This is a bit nasty tbh.
		"""
		outputs = {}

		for layer in layers:
			prefix2 = prefix

			if useRenderSetup:
				if layer.startswith('rs_'):
					layer2 = layer.replace('rs_', '', 1)
			else:
				layer2 = layer

			# Replace tokens...
			if scene:
				prefix2 = prefix2.replace('<Scene>', scene)
			if layer2:
				prefix2 = prefix2.replace('<RenderLayer>', layer2)
			if camera:
				prefix2 = prefix2.replace('<Camera>', camera)

			filepath = oswrapper.absolutePath("%s/%s.####.exr" %(path, prefix2))
			outputs[layer] = os.path.split(filepath)

		return outputs


	def getOutputs(self):
		""" Get the file output(s) from a render. Return as a dictionary with
			the render layer / write node name as the key, and the value as a
			tuple containing the dirname and basename.
		"""
		outputs = {}

		if UI.ENVIRONMENT == "MAYA":
			for entry in self.getRenderableLayers(allLayers=True):
				outputs[entry] = os.path.split(self.getMayaRenderOutput(entry))

		elif UI.ENVIRONMENT == "NUKE":
			for entry in self.getWriteNodes(selected=False):
				outputs[entry] = os.path.split(self.getNukeRenderOutput(entry))

		return outputs


	def submit(self):
		""" Submit job.
		"""
		self.save()  # Save settings

		submit_args = self.getSubmissionOptions()
		if submit_args:

			# Generate confirmation message(s)
			if self.submitTo == "Render Queue":
				if submit_args['frames']:
					submit_args['taskSize'] = self.ui.taskSize_spinBox.value()
					frames_msg = "%d frame(s) to be rendered; %d task(s) to be submitted.\n" %(len(self.numList), len(self.taskList))
				else:
					submit_args['frames'] = "Unknown"
					submit_args['taskSize'] = "Unknown"
					self.numList = []
					self.taskList = [submit_args['frames'], ]
					frames_msg = "The frame range was not specified so the job cannot be distributed into tasks. The job will be submitted as a single task and the frame range will be read from the scene at render time.\n"
			else:
				if submit_args['frames']:
					frames_msg = ""
				else:
					submit_args['frames'] = "Unknown"
					frames_msg = "Warning: No frame range specified.\n"

			job_info_msg = "Name:\t%s\nType:\t%s\nFrames:\t%s\nTask size:\t%s\nPriority:\t%s\n" %(submit_args['jobName'], self.jobType, submit_args['frames'], submit_args['taskSize'], submit_args['priority'])

			# Show confirmation dialog
			dialog_title = "Submit to %s - %s" %(self.submitTo, submit_args['jobName'])
			dialog_msg = job_info_msg + "\n" + frames_msg + "Do you want to continue?"

			# Actually submit the job
			if self.promptDialog(dialog_msg, dialog_title):
				if self.submitTo == "Render Queue":
					result, result_msg = self.submitToRenderQueue(**submit_args)
				elif self.submitTo == "Deadline":
					result, result_msg = deadline.submit_job(**submit_args)

				# Show post-confirmation dialog
				dialog_title = "Submission Results - %s" %submit_args['jobName']
				dialog_msg = job_info_msg + "\n" + result_msg
				self.promptDialog(dialog_msg, dialog_title, conf=True)


	def getSubmissionOptions(self):
		""" Get all values from UI widgets and return them as a dictionary.
		"""
		submit_args = {}

		if self.submitTo == "Render Queue":
			self.calcFrameList(quiet=False)
			# if not self.calcFrameList(quiet=False):
			# 	return None

		##################
		# Common options #
		##################

		submit_args['frames'] = self.ui.frames_lineEdit.text()
		submit_args['taskSize'] = self.ui.taskSize_spinBox.value()
		submit_args['pool'] = self.ui.pool_comboBox.currentText()
		submit_args['secondaryPool'] = self.ui.pool2_comboBox.currentText()  # Deadline only
		submit_args['group'] = self.ui.group_comboBox.currentText()  # Deadline only
		submit_args['priority'] = self.ui.priority_spinBox.value()
		submit_args['comment'] = self.ui.comment_lineEdit.text()
		submit_args['username'] = os.environ.get('IC_USERNAME', getpass.getuser())

		# Environment variables...
		# submit_args['envVars'] = ['JOB', 'SHOT', 'JOBPATH', 'SHOTPATH']  # Icarus
		# submit_args['envVars'] = ['UHUB_BASE_PATH', 'UHUB_JOB_PATH']  # Uhub
		envVarKeys = []
#		for key in os.environ.keys():
#			if 'UHUB' in key.upper():
#				envVarKeys.append(key)

		################################
		# Application-specific options #
		################################

		if self.jobType == "Generic":
			submit_args['plugin'] = "CommandLine"  # Deadline only
			command = self.ui.command_lineEdit.text()
			submit_args['jobName'] = os.path.splitext(os.path.basename(command))[0]
			submit_args['command'] = command
			submit_args['flags'] = self.ui.flags_lineEdit.text()
			submit_args['renderLayers'] = None

		elif self.jobType == "Maya":
			submit_args['plugin'] = "MayaBatch"  # Deadline only
			#submit_args['flags'] = ""  # RQ only
			submit_args['version'] = os.environ.get('MAYA_VER', "2018")  #jobData.getAppVersion('Maya')
			submit_args['renderer'] = self.ui.renderer_comboBox.currentText()  # Maya submit only
			submit_args['camera'] = self.ui.camera_comboBox.currentText()

			scene = self.makePathAbsolute(self.ui.mayaScene_comboBox.currentText()).replace("\\", "/")
			submit_args['scene'] = scene
			# if UI.ENVIRONMENT == "STANDALONE":
			# 	submit_args['scene'] = scene
			# else:
			# 	submit_args['scene'] = self.snapshot()

			submit_args['mayaProject'] = self.getMayaProject(scene)
			submit_args['outputFilePath'] = self.getOutputFilePath()  # Maya submit only
			submit_args['outputFilePrefix'] = self.getOutputFilePrefix()  # Maya submit only
			submit_args['jobName'] = os.path.splitext(os.path.basename(scene))[0]
			submit_args['useRenderSetup'] = self.getCheckBoxValue(self.ui.useRenderSetup_checkBox)
			submit_args['renderLayers'] = self.ui.layers_lineEdit.text()

			# File output location(s)... (Maya submit only)
			if UI.ENVIRONMENT == "STANDALONE":
				submit_args['output'] = self.guessOutputs(
					submit_args['outputFilePath'], 
					submit_args['outputFilePrefix'], 
					submit_args['jobName'], 
					submit_args['camera'], 
					submit_args['renderLayers'].split(", "), 
					submit_args['useRenderSetup'])
			else:
				submit_args['output'] = self.getOutputs()

			# Environment variables...
			# submit_args['envVars'] += ['MAYADIR', 'MAYASCENESDIR', 'MAYARENDERSDIR']
#			for key in os.environ.keys():
#				if 'MAYA' in key.upper():
#					envVarKeys.append(key)
			if submit_args['renderer'] == "redshift":
				submit_args['envVars'] += ['REDSHIFT_COREDATAPATH']

		elif self.jobType == "Houdini":
			submit_args['plugin'] = "Houdini"  # Deadline only
			#submit_args['flags'] = ""  # RQ only
			submit_args['version'] = "16"  # Temp
			scene = self.makePathAbsolute(self.ui.houdiniScene_comboBox.currentText()).replace("\\", "/")
			submit_args['scene'] = scene
			submit_args['jobName'] = os.path.splitext(os.path.basename(scene))[0]
			submit_args['outputDriver'] = self.ui.houdiniOutputDriver_comboBox.currentText()
			submit_args['renderLayers'] = None  # Use renderLayers for takes

		elif self.jobType == "Nuke":
			submit_args['plugin'] = "Nuke"  # Deadline only
			#submit_args['flags'] = ""  # RQ only
			submit_args['version'] = os.environ.get('NUKE_VER', "10.0v3").split('v')[0]  #jobData.getAppVersion('Nuke')
			submit_args['isMovie'] = self.getCheckBoxValue(self.ui.isMovie_checkBox)
			if submit_args['isMovie']:  # Override task size if output is movie
				submit_args['taskSize'] = len(self.numList)
			submit_args['nukeX'] = self.getCheckBoxValue(self.ui.useNukeX_checkBox)
			submit_args['interactiveLicense'] = self.getCheckBoxValue(self.ui.interactiveLicense_checkBox)

			scene = self.makePathAbsolute(self.ui.nukeScript_comboBox.currentText()).replace("\\", "/")
			if UI.ENVIRONMENT == "STANDALONE":
				submit_args['scene'] = scene
			else:
				submit_args['scene'] = self.snapshot()

			submit_args['jobName'] = os.path.splitext(os.path.basename(scene))[0]
			submit_args['renderLayers'] = self.ui.writeNodes_lineEdit.text()  # Use renderLayers for writeNodes

			# File output location(s)... (Nuke submit only)
			submit_args['output'] = self.getOutputs()

			# Environment variables...
			#submit_args['envVars'] += ['NUKEDIR', 'NUKESCRIPTSDIR', 'NUKERENDERSDIR']
			for key in os.environ.keys():
				if 'NUKE' in key.upper():
					envVarKeys.append(key)

		# Remove duplicate env var keys
		submit_args['envVars'] = list(set(envVarKeys))

		return submit_args


	def submitToRenderQueue(self, **kwargs):
		""" Submit job to render queue.
		"""
		time_format_str = "%Y/%m/%d %H:%M:%S"
		result_msg = ""

		# if kwargs is not None:
		# 	for key, value in kwargs.items():
		# 		print("%24s = %s" %(key, value))

		# Instantiate Render Queue class, load data, and create new job
		try:  # If running from Render Queue main client UI
			rq = self.parent.rq
		except:  # Otherwise instatiate new Render Queue class
			databaseLocation = '/mnt/anubis/PersonalJobs/999925_Mike_Bonnington/dev/renderqueue/rq_database'  # temp assignment - should read from prefs file
			rq = database.RenderQueue(databaseLocation)

		try:
			jobNameBase = kwargs['jobName']
			kwargs['jobType'] = self.jobType
			kwargs['tasks'] = self.taskList
			kwargs['submitTime'] = time.strftime(time_format_str)

			if kwargs['renderLayers']:  # Batch submission -------------------
				num_jobs = 0
				for renderLayer in re.split(r',\s*', kwargs['renderLayers']): # use re for more versatility, or even better pass as list
					kwargs['renderLayer'] = renderLayer
					kwargs['jobName'] = "%s - %s" %(jobNameBase, renderLayer)
					rq.newJob(**kwargs)  # Create job
					num_jobs += 1

				result = True
				result_msg = "Successfully submitted %d job(s)." %num_jobs

			else:  # Single job submission -----------------------------------
				rq.newJob(**kwargs)  # Create job

				result = True
				result_msg = "Successfully submitted job."

		except:  # Submission failed -----------------------------------------
			result = False
			exc_type, exc_value, exc_traceback = sys.exc_info()
			traceback.print_exception(exc_type, exc_value, exc_traceback)
			result_msg = "Failed to submit job."
			print(result_msg)
			result_msg += "\nCheck console output for details."

		return result, result_msg


	def closeEvent(self, event):
		""" Event handler for when window is closed.
		"""
		self.save()  # Save settings
		self.storeWindow()  # Store window geometry

		#QtWidgets.QMainWindow.closeEvent(self, event)

# ----------------------------------------------------------------------------
# End of main window class
# ============================================================================
# Run functions
# ----------------------------------------------------------------------------

def run_maya(session, **kwargs):
	""" Run in Maya.
	"""
	try:  # Show the UI
		session.renderSubmitUI.display()
	except:  # Create the UI
		UI._maya_delete_ui(WINDOW_OBJECT, WINDOW_TITLE)  # Delete any existing UI
		session.renderSubmitUI = RenderSubmitUI(parent=UI._maya_main_window())
		session.renderSubmitUI.display(**kwargs)


def run_houdini(session, **kwargs):
	""" Run in Houdini.
	"""
	try:  # Show the UI
		session.renderSubmitUI.display()
	except:  # Create the UI
		#UI._houdini_delete_ui(WINDOW_OBJECT, WINDOW_TITLE)  # Delete any existing UI
		#session = UI._houdini_get_session()
		session.renderSubmitUI = RenderSubmitUI(parent=UI._houdini_main_window())
		session.renderSubmitUI.display(**kwargs)


def run_nuke(session, **kwargs):
	""" Run in Nuke.
	"""
	try:  # Show the UI
		session.renderSubmitUI.display()
	except:  # Create the UI
		UI._nuke_delete_ui(WINDOW_OBJECT, WINDOW_TITLE)  # Delete any existing UI
		session.renderSubmitUI = RenderSubmitUI(parent=UI._nuke_main_window())
		session.renderSubmitUI.display(**kwargs)


# Run as standalone app
if __name__ == "__main__":
	print("%s (standalone)" %WINDOW_TITLE)
	app = QtWidgets.QApplication(sys.argv)

	# Instantiate main application class
	rsApp = RenderSubmitUI()
	#rsApp.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

	# Show the application UI
	#rsApp.show()
	rsApp.display()
	sys.exit(app.exec_())

