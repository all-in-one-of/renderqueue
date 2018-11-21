#!/usr/bin/python

import sys
from renderqueue.uistyle.Qt import QtWidgets
from renderqueue import renderqueue
#renderqueue.standalone()

app = QtWidgets.QApplication(sys.argv)
rqApp = renderqueue.RenderQueueApp()
#rqApp.display()
rqApp.show()
sys.exit(app.exec_())
