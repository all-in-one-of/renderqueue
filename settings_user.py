#!/usr/bin/python

# settings_user.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2018
#
# User settings handler.


import os

from Qt import QtCore, QtWidgets

# Import custom modules


class helper():

	def __init__(self, parent, frame):
		""" Setup user properties panel.
		"""
		self.frame = frame
		self.parent = parent

		# Connect signals & slots
		self.bdl = lambda: self.browseDatabaseLocation()
		self.ssc = lambda: self.setSystemColors()

		frame.locationBrowse_toolButton.clicked.connect(self.bdl)
		frame.useSystemColors_checkBox.toggled.connect(self.ssc)
		frame.uiBrightness_slider.valueChanged.connect(parent.setUIBrightness)
		frame.uiAccentColor_button.clicked.connect(parent.setAccentColor)

		frame.uiBrightness_slider.setValue(parent.col['window'].lightness())
		frame.uiAccentColor_button.setStyleSheet("QWidget { background-color: %s }" %parent.col['highlight'].name())


	# @QtCore.Slot()
	def browseDatabaseLocation(self):
		""" Toggle option to use system UI colours.
		"""
		#print("A")
		newLocation = self.parent.folderDialog(self.frame.location_lineEdit.text())
		if newLocation:
			self.frame.location_lineEdit.setText(newLocation)


	# @QtCore.Slot()
	def setSystemColors(self):
		""" Toggle option to use system UI colours.
		"""
		#print("B")
		self.frame.uiBrightness_slider.setValue(self.parent.col['sys-window'].lightness())
		self.frame.uiAccentColor_button.setStyleSheet("QWidget { background-color: %s }" %self.parent.col['sys-highlight'].name())
