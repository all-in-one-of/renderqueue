#!/usr/bin/python

# about.py
#
# Mike Bonnington <mjbonnington@gmail.com>
# (c) 2015-2019
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

		self.photocredit_label = QtWidgets.QLabel(self)
		self.photocredit_label.setGeometry(QtCore.QRect(8, 8, 624, 304))
		self.photocredit_label.setStyleSheet("background: transparent; color: #FFF;")
		self.photocredit_label.setAlignment(QtCore.Qt.AlignTop|QtCore.Qt.AlignRight)

		# Add dropshadow to text
		effect = QtWidgets.QGraphicsDropShadowEffect()
		effect.setColor(QtGui.QColor(0, 0, 0))
		effect.setOffset(1, 1)
		effect.setBlurRadius(2)
		self.message_label.setGraphicsEffect(effect)


	def display(self, image=None, message=""):
		""" Display message in about dialog.
		"""
		if image:
			pixmap = QtGui.QPixmap(image)
			self.bg_label.setPixmap(pixmap.scaled(
				self.bg_label.size(), QtCore.Qt.KeepAspectRatioByExpanding,
				QtCore.Qt.SmoothTransformation))
			self.bg_label.setAlignment(QtCore.Qt.AlignCenter)
			# self.bg_label.setScaledContents(True)
			# self.bg_label.setMinimumSize(1, 1)
			# self.bg_label.show()

			creditfile = os.path.join(os.path.dirname(image), 'photocredit.txt')
			if os.path.isfile(creditfile):
				with open(creditfile, 'r') as fh:
					credittext = fh.readlines()
					self.photocredit_label.setText(credittext[0])

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

