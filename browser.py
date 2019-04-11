#!/usr/bin/python

# browser.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2016-2019
#
# Render Browser
# A UI to browse render folders and provide at-a-glance review of layers,
# passes/AOVs, sequences, etc.


import os
import re
import sys

from Qt import QtCore, QtGui, QtWidgets
import ui_template as UI

# Import custom modules
#import djvOps
import oswrapper
import sequence


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# Set window title and object names
WINDOW_TITLE = "Render Browser"
WINDOW_OBJECT = "RenderBrowserUI"

# Set the UI and the stylesheet
UI_FILE = "browser.ui"
STYLESHEET = 'style.qss'  # Set to None to use the parent app's stylesheet

# Other options
STORE_WINDOW_GEOMETRY = True


# ----------------------------------------------------------------------------
# Main window class
# ----------------------------------------------------------------------------

class RenderBrowserUI(QtWidgets.QMainWindow, UI.TemplateUI):
	""" Render Browser UI.
	"""
	def __init__(self, parent=None):
		super(RenderBrowserUI, self).__init__(parent)
		self.parent = parent

		self.setupUI(window_object=WINDOW_OBJECT, 
		             window_title=WINDOW_TITLE, 
		             ui_file=UI_FILE, 
		             stylesheet=STYLESHEET, 
		             store_window_geometry=STORE_WINDOW_GEOMETRY)  # re-write as **kwargs ?

		# Set window flags
		self.setWindowFlags(QtCore.Qt.Window)

		# Set icons (temp)
		self.ui.refresh_toolButton.setIcon(self.iconSet('view-refresh.svg'))
		self.ui.browse_toolButton.setIcon(self.iconSet('folder-open-symbolic.svg'))
		self.ui.frameRangeOptions_toolButton.setIcon(self.iconSet('configure.svg'))

		# Connect signals & slots
		self.ui.refresh_toolButton.clicked.connect(self.renderTableUpdate)
		self.ui.path_lineEdit.textChanged.connect(self.renderTableUpdate)
		self.ui.browse_toolButton.clicked.connect(self.browsePath)
		self.ui.renderBrowser_treeWidget.itemDoubleClicked.connect(self.renderPreview)
		self.ui.frame_spinBox.valueChanged.connect(self.updateTimeline)


	def display(self, directory=None, frameRange=None):
		""" Display the window.
		"""
		self.returnValue = False

		# Get current dir for renders and update render layer tree view widget
		#self.renderPath = os.getcwd()
		if directory is not None:
			self.ui.path_lineEdit.setText(directory)
		if frameRange is not None:
			self.ui.frameRange_lineEdit.setText(frameRange)
		self.renderTableUpdate()

		self.show()
		self.raise_()

		return self.returnValue


	def generateThumbnail(self, imagePath, imagePrefix, extension, posterFrame=1001): #, posterFrame=os.environ['STARTFRAME']):
		""" Generates a low-res JPEG thumbnail from the image path provided.
		"""
		inPrefix = os.path.join(imagePath, imagePrefix)
		outPrefix = os.path.join(imagePath, '.icThumbs', imagePrefix)
		outFile = '%s.%s.jpg' % (outPrefix, posterFrame)
		# if not os.path.isfile(outFile):
		# 	print("Generating thumbnails...")
		# 	oswrapper.createDir(os.path.join(imagePath, '.icThumbs'))
		# 	djvOps.prcImg(inPrefix, outPrefix, posterFrame, posterFrame, extension.split('.', 1)[1], outExt='jpg', resize=(512,288))
		return outFile


	def renderPreview(self, item, column):
		""" Launches sequence viewer when entry is double-clicked.
		"""
		#print item.text(column), column
		#path = sequence.getFirst(oswrapper.absolutePath(item.text(4)))
		path = oswrapper.absolutePath(item.text(4))
		path = path.replace("#", self.ui.frame_spinBox.text())
		#print path
		#djvOps.viewer(path)
		# from u_vfx.core import Launch
		# Launch.djvView(path)
		os.system('/usr/local/djv-1.1.0-Linux-64/bin/djv_view.sh %s' %path)


	def browsePath(self, dialogHome):
		""" Opens a file dialog to choose which directory to browse.
		"""
		startingDir = self.ui.path_lineEdit.text()
		selectedDir = self.folderDialog(startingDir)
		if os.path.isdir(selectedDir):
			#self.renderPath = selectedDir
			self.ui.path_lineEdit.setText(selectedDir)
			#self.renderTableUpdate()


	def updateTimeline(self):
		""" Update the timeline range based on the given frame range.
		"""
		frameRange = self.ui.frameRange_lineEdit.text().split('-')
		startframe = int(frameRange[0])
		endframe = int(frameRange[1])
		self.ui.frame_horizontalSlider.setMinimum(startframe)
		self.ui.frame_horizontalSlider.setMaximum(endframe)
		self.ui.frame_spinBox.setMinimum(startframe)
		self.ui.frame_spinBox.setMaximum(endframe)


	def renderTableUpdate(self):
		""" Populates the render layer tree view widget with entries.
		"""
		#renderPath = self.renderPath
		self.ui.renderBrowser_treeWidget.clear()
		renderPath = self.ui.path_lineEdit.text()
		# if renderPath:
		if os.path.isdir(renderPath):
			renderLayerDirs = []

			# Get subdirectories
			subdirs = next(os.walk(renderPath))[1]
			if subdirs:
				for subdir in subdirs:
					if not subdir.startswith('.'): # ignore directories that start with a dot
						renderLayerDirs.append(subdir)
			if renderLayerDirs:
				renderLayerDirs.sort()
			else: # use parent dir
				renderLayerDirs = [os.path.basename(renderPath)]
				renderPath = os.path.dirname(renderPath)
			#print renderPath, renderLayerDirs

			self.ui.renderBrowser_treeWidget.setIconSize(QtCore.QSize(128, 72))

			# Add render layers
			for renderLayerDir in renderLayerDirs:
				renderPasses = sequence.getBases(os.path.join(renderPath, renderLayerDir))

				# Only continue if render pass sequences exist in this directory, and ignore directories that start with a dot
				if renderPasses and not renderLayerDir.startswith('.'):
					renderLayerItem = QtWidgets.QTreeWidgetItem(self.ui.renderBrowser_treeWidget)
					renderLayerItem.setText(0, '%s (%d)' % (renderLayerDir, len(renderPasses)))
					renderLayerItem.setText(1, 'layer')
					#renderLayerItem.setText(4, os.path.join(renderPath, renderLayerDir))
					renderLayerItem.setText(4, oswrapper.relativePath(os.path.join(renderPath, renderLayerDir), 'SHOTPATH'))
					self.ui.renderBrowser_treeWidget.addTopLevelItem(renderLayerItem)
					renderLayerItem.setExpanded(True)

					# Add render passes
					for renderPass in renderPasses:
						renderPassItem = QtWidgets.QTreeWidgetItem(renderLayerItem)
						path, prefix, fr_range, ext, num_frames = sequence.getSequence( os.path.join(renderPath, renderLayerDir), renderPass )
						renderPassItem.setText(0, prefix)
						iconPath = self.generateThumbnail(os.path.join(renderPath, renderLayerDir), prefix, ext)
						#print iconPath
						renderPassItem.setIcon(0, QtGui.QIcon(iconPath))
						renderPassItem.setText(1, ext.split('.', 1)[1])
						renderPassItem.setText(2, fr_range)
						# if not sequence.check(fr_range):  # Set red text for sequence mismatch
						# 	renderPassItem.setForeground(2, QtGui.QBrush(QtGui.QColor("#f92672")))
						#renderPassItem.setText(4, path)
						renderPassItem.setText(4, oswrapper.relativePath(os.path.join(renderPath, renderLayerDir, renderPass), 'SHOTPATH'))
						self.ui.renderBrowser_treeWidget.addTopLevelItem(renderPassItem)

			# Resize columns
			self.ui.renderBrowser_treeWidget.resizeColumnToContents(0)
			self.ui.renderBrowser_treeWidget.resizeColumnToContents(1)
			self.ui.renderBrowser_treeWidget.resizeColumnToContents(2)


	def renderTableAdd(self):
		""" Adds entries to the render layer tree view widget.
		"""
		if os.environ.get('MAYARENDERSDIR') is None:
			renderBrowseDir = os.getcwd()
		else:
			renderBrowseDir = os.environ['MAYARENDERSDIR']

		#self.renderPath = self.folderDialog(renderBrowseDir)
		self.renderTableUpdate()


	def renderTableRemove(self):
		""" Removes the selected entry from the render layer tree view widget.
			TODO: allow passes to be removed as well as layers.
		"""
		for item in self.ui.renderBrowser_treeWidget.selectedItems():
			self.ui.renderBrowser_treeWidget.takeTopLevelItem( self.ui.renderBrowser_treeWidget.indexOfTopLevelItem(item) )


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

			#self.fname = fname
			#verbose.print_("Dropped '%s' on to window." %fname)
			print("Dropped '%s' on to window." %fname)
			if os.path.isdir(fname):
				#self.renderPath = fname
				self.ui.path_lineEdit.setText(fname)
				#self.renderTableUpdate()
				#self.updateTaskListDir(fname)
			elif os.path.isfile(fname):
				print("File")
				#self.updateTaskListFile(fname)
		else:
			e.ignore()


	def closeEvent(self, event):
		""" Event handler for when window is closed.
		"""
		self.save()  # Save settings
		self.storeWindow()  # Store window geometry

		#QtWidgets.QMainWindow.closeEvent(self, event)

# ----------------------------------------------------------------------------
# End main application class
# ============================================================================
# Run as standalone app
# ----------------------------------------------------------------------------

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)

	# Apply 'Fusion' application style for Qt5
	styles = QtWidgets.QStyleFactory.keys()
	if 'Fusion' in styles:
		app.setStyle('Fusion')

	# Instantiate main application class
	rbApp = RenderBrowserUI()

	# Show the application UI
	rbApp.show()
	rbApp.display(directory=os.getcwd())
	sys.exit(app.exec_())

