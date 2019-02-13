#!/usr/bin/python

# about.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2015-2018
#
# Pop-up 'About' dialog / splash screen.


import os
from Qt import QtCore, QtGui, QtWidgets


class AboutDialog(QtWidgets.QDialog):
	""" Main dialog class.
	"""
	def __init__(self, parent=None):
		super(AboutDialog, self).__init__(parent)

		# Setup window and UI widgets
		self.setWindowFlags(QtCore.Qt.Popup)

		self.resize(640, 320)
		self.setMinimumSize(QtCore.QSize(640, 320))
		self.setMaximumSize(QtCore.QSize(640, 320))
		self.setSizeGripEnabled(False)

		self.bg_label = QtWidgets.QLabel(self)
		self.bg_label.setGeometry(QtCore.QRect(0, 0, 640, 320))

		self.message_label = QtWidgets.QLabel(self)
		self.message_label.setGeometry(QtCore.QRect(16, 16, 608, 288))
		self.message_label.setStyleSheet("background: transparent; color: #FFF;")


	def display(self, image=None, message=""):
		""" Display message in about dialog.
		"""
		if image:
			self.bg_label.setPixmap(QtGui.QPixmap(image))

		if message:
			self.message_label.setText(message)

		# Move to centre of active screen
		desktop = QtWidgets.QApplication.desktop()
		screen = desktop.screenNumber(desktop.cursor().pos())
		self.move(desktop.screenGeometry(screen).center() - self.frameGeometry().center())

		#self.show()
		self.exec_()  # Make the dialog modal


	def mousePressEvent(self, QMouseEvent):
		""" Close about dialog if mouse is clicked.
		"""
		self.accept()

