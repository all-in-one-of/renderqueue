#!/usr/bin/python

# settings.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2015-2018
#
# Modular settings editor dialog.
# Provides a skeleton dialog which can be extended with load-in panels, each
# with their own UI file and helper module (if required).


import json
import os
import sys

from Qt import QtCompat, QtCore, QtWidgets
import ui_template as UI

# Import custom modules
#import verbose


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# Set window title and object names
WINDOW_TITLE = "Settings"
WINDOW_OBJECT = "settingsUI"

# Set the UI and the stylesheet
UI_FILE = 'settings.ui'
STYLESHEET = 'style.qss'  # Set to None to use the parent app's stylesheet

# Other options
STORE_WINDOW_GEOMETRY = False


# ----------------------------------------------------------------------------
# Main dialog class
# ----------------------------------------------------------------------------

class SettingsDialog(QtWidgets.QDialog, UI.TemplateUI):
	""" Settings editor dialog class.
	"""
	def __init__(self, parent=None):
		super(SettingsDialog, self).__init__(parent)
		self.parent = parent

		self.setupUI(window_object=WINDOW_OBJECT, 
		             window_title=WINDOW_TITLE, 
		             ui_file=UI_FILE, 
		             stylesheet=STYLESHEET, 
		             xml_data='userprefs.json', 
		             store_window_geometry=STORE_WINDOW_GEOMETRY)  # re-write as **kwargs ?

		# Set window flags
		self.setWindowFlags(QtCore.Qt.Dialog)

		# Set other Qt attributes
		self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

		# Connect signals & slots
		self.ui.categories_listWidget.currentItemChanged.connect(lambda current: self.openProperties(current.text()))
		# self.ui.categories_listWidget.itemActivated.connect(lambda item: self.openProperties(current.text()))

		self.ui.settings_buttonBox.button(QtWidgets.QDialogButtonBox.Reset).clicked.connect(self.removeOverrides)
		self.ui.settings_buttonBox.button(QtWidgets.QDialogButtonBox.Save).clicked.connect(self.saveAllAndClose)
		self.ui.settings_buttonBox.button(QtWidgets.QDialogButtonBox.Cancel).clicked.connect(self.reject)


	def display(self, settingsType="Generic", categoryLs=[], startPanel=None, 
	            datafile=None, inherit=None, autoFill=False):
		""" Display the dialog.

			'settingsType' is the name given to the settings dialog.
			'categoryLs' is a list of categories, should correspond to a page
			of properties defined by a .ui file.
			'startPanel' if set will jump straight to the named panel.
			'datafile' is the path to the data file storing the settings.
			'inherit' whether to inherit any values. This should be in the
			form of a path just like the 'datafile' argument.
			'autoFill' when true, attempt to fill some fields automatically.
		"""
		if startPanel:
			print("Start Panel: " + startPanel)
			self.currentCategory = startPanel
		else:
			self.currentCategory = ""

		self.settingsType = settingsType
		self.categoryLs = categoryLs
		self.datafile = datafile
		self.inherit = inherit
		self.autoFill = autoFill

		self.reset()

		# Set window title
		if settingsType == "Job":
			title_suffix = ": " + os.environ['JOB']
		elif settingsType == "Shot":
			title_suffix = ": " + os.environ['SHOT']
		else:
			title_suffix = ""
		self.setWindowTitle("%s %s%s" %(settingsType, WINDOW_TITLE, title_suffix))

		return self.exec_()


	def reset(self):
		""" Initialise or reset by reloading data.
		"""
		# self.ui.categories_listWidget.blockSignals(True)

		# Load data from xml file(s)
		#self.xd.loaddata(self.datafile)
		with open(self.datafile, 'r') as f:
			self.xd = json.load(f)
		if self.inherit:
			import settingsData
			self.id = settingsData.SettingsData()
			self.id.loadXML(self.inherit)
		else:
			self.id = None

		# Populate categories
		if self.categoryLs:
			self.ui.categories_listWidget.clear()

			for cat in self.categoryLs:
				self.ui.categories_listWidget.addItem(cat)

			# Set the maximum size of the list widget
			self.ui.categories_listWidget.setMaximumWidth(self.ui.categories_listWidget.sizeHintForColumn(0)*2)

			# Select the first item & show the appropriate settings panel
			if self.currentCategory == "":
				currentItem = self.ui.categories_listWidget.item(0)
			else:
				currentItem = self.ui.categories_listWidget.findItems(self.currentCategory, QtCore.Qt.MatchExactly)[0]

			currentItem.setSelected(True)
			# self.openProperties(currentItem.text())

		# self.ui.categories_listWidget.blockSignals(False)


	def openProperties(self, category, storeProperties=True):
		""" Open properties panel for selected settings category. Loads UI
			file and sets up widgets.
		"""
		self.currentCategory = category

		# Show panel & load values into form widgets
		if self.loadPanel(category):
			if (self.inherit is not None) and self.ui.settings_frame.property('inheritable'):
				# verbose.print_("Category: %s (values inheritable)" %category)
				self.setupWidgets(self.ui.settings_frame, 
				                  forceCategory=category, 
				                  inherit=self.id, 
				                  storeProperties=False)
			else:
				# verbose.print_("Category: %s" %category)
				self.setupWidgets(self.ui.settings_frame, 
				                  forceCategory=category, 
				                  storeProperties=storeProperties)


	def loadPanel(self, category):
		""" Load the panel UI (and helper module if required).
			The exec function is called here to avoid the error: 'unqualified
			exec is not allowed in function because it contains a nested
			function with free variables' with Python 2.x.
		"""
		ui_file = "settings_%s.ui" %category
		helper_module = 'settings_%s' %category
		panel_ui_loaded = False
		# helper_module_loaded = False

		# Create new frame to hold properties UI & load into frame
		self.ui.settings_frame.close()
		try:
			# uifile = os.path.join(os.environ['IC_FORMSDIR'], ui_file)
			self.ui.settings_frame = QtCompat.loadUi(ui_file)
			self.ui.settings_verticalLayout.addWidget(self.ui.settings_frame)
			self.conformFormLayoutLabels(self.ui.settings_frame)
			panel_ui_loaded = True
		except FileNotFoundError:
			message = "Could not open '%s' properties panel." %category
			# verbose.error(message)
			print(message)

		# Load helper module
		try:
			exec_str = 'import %s as sh; helper = sh.helper(self, self.ui.settings_frame)' %helper_module
			# print(exec_str)
			exec(exec_str)
			# helper_module_loaded = True
		except ImportError:
			pass

		return panel_ui_loaded


	def removeOverrides(self):
		""" Remove stored values and instead inherit defaults for widgets on
			the current panel.
		"""
		for widget in self.ui.settings_frame.findChildren(QtWidgets.QWidget):
			attr = widget.property('xmlTag')
			if attr:
				#self.xd.removeElement(self.currentCategory, attr)
				del(self.xd[attr])

		self.openProperties(self.currentCategory, storeProperties=False)


	def saveAllAndClose(self):
		""" Save settings and close the dialog.
		"""
		# Store the values from widgets on all pages
		for category in self.categoryLs:
			self.openProperties(category, storeProperties=True)

		# There's a bug where all property panel widgets become visible if a
		# save fails. As a quick dodgy workaround we exit so we don't see it
		# happen.
		if self.save():
			self.accept()
		else:
			# self.close()
			self.reject()


	def keyPressEvent(self, event):
		""" Override function to prevent Enter / Esc keypresses triggering
			OK / Cancel buttons.
		"""
		if event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
			return


	def hideEvent(self, event):
		""" Event handler for when window is hidden.
		"""
		self.storeWindow()  # Store window geometry


	# def closeEvent(self, event):
	# 	""" Event handler for when window is closed.
	# 	"""
	# 	#self.save()  # Save settings
	# 	#self.storeWindow()  # Store window geometry

