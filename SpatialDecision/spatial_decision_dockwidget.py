# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SpatialDecisionDockWidget
                                 A QGIS plugin
 This is a SDSS template for the GEO1005 course
                             -------------------
        begin                : 2015-11-02
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Jorge Gil, TU Delft
        email                : j.a.lopesgil@tudelft.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt4 import QtGui, QtCore, uic
from qgis.core import *
from qgis.networkanalysis import *
# Initialize Qt resources from file resources.py
import resources

import os
import os.path
import random

from . import utility_functions as uf


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'spatial_decision_dockwidget_base.ui'))


class SpatialDecisionDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = QtCore.pyqtSignal()
    #custom signals
    updateAttribute = QtCore.pyqtSignal(str)

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(SpatialDecisionDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # define globals
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        # set up GUI operation signals
        # data
        self.iface.projectRead.connect(self.updateLayers)
        self.iface.newProjectCreated.connect(self.updateLayers)
        self.openScenarioButton.clicked.connect(self.openScenario)
        self.saveScenarioButton.clicked.connect(self.saveScenario)
        self.selectLayerCombo.activated.connect(self.setSelectedLayer)
        self.selectAttributeCombo.hide() # activated.connect(self.setSelectedAttribute)
        self.SelectUserGroupCombo.activated.connect(self.setSelectedUserGroup)

        # analysis
        self.bufferButton.clicked.connect(self.calculateBuffer)
        #click the button and create non service area
        self.nonserviceButton.clicked.connect(self.symmmetricdifference)

        # visualisation

        # reporting
        self.featureCounterUpdateButton.clicked.connect(self.updateNumberFeatures)
        self.saveMapButton.clicked.connect(self.saveMap)
        self.saveMapPathButton.clicked.connect(self.selectFile)
        self.updateAttribute.connect(self.extractAttributeSummary)

        # set current UI restrictions

        # initialisation
        self.updateLayers()
        #self.SelectUserGroupCombo.currentIndexChanged(const QString&)
        print "Plugin loaded!"

        #run simple tests

    def closeEvent(self, event):
        # disconnect interface signals
        self.iface.projectRead.disconnect(self.updateLayers)
        self.iface.newProjectCreated.disconnect(self.updateLayers)

        self.closingPlugin.emit()
        event.accept()

#######
#   Data functions
#######
    def openScenario(self,filename=""):
        scenario_open = False
        scenario_file = os.path.join('/Users/jorge/github/GEO1005','sample_data','time_test.qgs')
        # check if file exists
        if os.path.isfile(scenario_file):
            self.iface.addProject(scenario_file)
            scenario_open = True
        else:
            last_dir = uf.getLastDir("SDSS")
            new_file = QtGui.QFileDialog.getOpenFileName(self, "", last_dir, "(*.qgs)")
            if new_file:
                self.iface.addProject(new_file)
                scenario_open = True
        if scenario_open:
            self.updateLayers()

    def saveScenario(self):
        self.iface.actionSaveProject()

    def updateLayers(self):
        layers = uf.getLegendLayers(self.iface, 'all', 'all')
        self.selectLayerCombo.clear()
        if layers:
            layer_names = uf.getLayersListNames(layers)
            self.selectLayerCombo.addItems(layer_names)
            self.setSelectedLayer()

    def setSelectedLayer(self):
        layer_name = self.selectLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        self.updateAttributes(layer)

    def getSelectedLayer(self):
        layer_name = self.selectLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        return layer

    def updateAttributes(self, layer):
        self.selectAttributeCombo.clear()
        if layer:
            fields = uf.getFieldNames(layer)
            self.selectAttributeCombo.addItems(fields)
            # send list to the report list window
            self.clearReport()
            self.updateReport(fields)

    def setSelectedAttribute(self):
        field_name = self.selectAttributeCombo.currentText()
        self.updateAttribute.emit(field_name)

    def getSelectedAttribute(self):
        field_name = self.selectAttributeCombo.currentText()
        return field_name

    def setSelectedUserGroup(self):
        proj = QgsProject.instance()
        if self.SelectUserGroupCombo.currentText() == 'Students':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 800)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','metro')")
            myint = proj.readNumEntry("SpatialDecisionDockWidget", "radius")[0]
        elif self.SelectUserGroupCombo.currentText() == 'Elderly':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 400)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','tram','ferry')")

        elif self.SelectUserGroupCombo.currentText() == 'Adults':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 600)[0]
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','metro','ferry')")
            myint = proj.readNumEntry("SpatialDecisionDockWidget", "radius")[0]

#######
#    Analysis functions
#######
    # buffer functions

    def calculateBuffer(self):

        proj = QgsProject.instance()
        cur_user = self.SelectUserGroupCombo.currentText()
        print cur_user
        radius = proj.readNumEntry("SpatialDecisionDockWidget", "radius")[0]
        transittypes = proj.readEntry("SpatialDecisionDockWidget", "transittypes")[0]
        network = 1

        uf.selectFeaturesByExpression(self.getSelectedLayer(),"network in {}".format(transittypes))
        origins = self.getSelectedLayer().selectedFeatures()
        layer = self.getSelectedLayer()

        #getFieldValues(layer, network)

        if origins > 0:
            cutoff_distance = radius
            buffers = {}
            for point in origins:
                geom = point.geometry()
                buffers[point.id()] = geom.buffer(cutoff_distance,12)
            # store the buffer results in temporary layer called "Buffers_[cur_user]"
            print 'Buffers_{}'.format(cur_user)
            buffer_layer = uf.getLegendLayerByName(self.iface, 'Buffers_{}'.format(cur_user))
            # create one if it doesn't exist
            if not buffer_layer:
                attribs = ['id', 'distance', 'network']
                types = [QtCore.QVariant.String, QtCore.QVariant.Double, QtCore.QVariant.String]
                buffer_layer = uf.createTempLayer('Buffers_{}'.format(cur_user),'POLYGON',layer.crs().postgisSrid(), attribs, types)
                uf.loadTempLayer(buffer_layer)
            # insert buffer polygons
            geoms = [] # geometries in a list
            values = [] #list of lists, consisting of 3 items. E.g. [[0L, 1200, 1],[...

            fld_values = uf.getFieldValues(layer, 'network', True,"network in {}".format(transittypes))[0]
            cnt = 0

            for buffer in buffers.iteritems():
                # each buffer has an id and a geometry
                geoms.append(buffer[1])
                # in the case of values, it expects a list of multiple values in each item - list of lists
                values.append([buffer[0],cutoff_distance, fld_values[cnt]])
                cnt += 1
            uf.insertTempFeatures(buffer_layer, geoms, values)
            self.refreshCanvas(buffer_layer)

    # SymmDiff function
    def symmmetricdifference (self):
        layer = uf.getLegendLayerByName(self.iface, 'panden')
        symmdiff_layer = uf.getLegendLayerByName(self.iface, 'Symmmetric Difference')
        # create templayer if does not exist
        if not symmdiff_layer:
            attribs = ['id']
            types = [QtCore.QVariant.String]
            symmdiff_layer = uf.createTempLayer('Symmetric Difference', 'POLYGON', layer.crs().postgisSrid(), attribs, types)
            uf.loadTempLayer(symmdiff_layer)

        # calculate symmetric difference
        inputlayer = uf.getLegendLayerByName(self.iface, 'buurten')
        differencelayer =  uf.getLegendLayerByName(self.iface, 'Symmetric Difference')
        features1 = uf.getAllFeatures(inputlayer)
        features2 = uf.getAllFeatures(differencelayer)

        geom1 = []
        geom2 = []
        for feature in features1.iteritems():
            geom1.append(feature[1].geometry())

        for feature in features2.iteritems():
            geom2.append(feature[1].geometry())

    # after adding features to layers needs a refresh (sometimes)
    def refreshCanvas(self, layer):
        if self.canvas.isCachingEnabled():
            layer.setCacheImage(None)
        else:
            self.canvas.refresh()



#######
#    Visualisation functions
#######

#######
#    Reporting functions
#######
    # update a text edit field
    def updateNumberFeatures(self):
        layer = self.getSelectedLayer()
        if layer:
            count = layer.featureCount()
            self.featureCounterEdit.setText(str(count))

    # selecting a file for saving
    def selectFile(self):
        last_dir = uf.getLastDir("SDSS")
        path = QtGui.QFileDialog.getSaveFileName(self, "Save map file", last_dir, "PNG (*.png)")
        if path.strip()!="":
            path = unicode(path)
            uf.setLastDir(path,"SDSS")
            self.saveMapPathEdit.setText(path)

    # saving the current screen
    def saveMap(self):
        filename = self.saveMapPathEdit.text()
        if filename != '':
            self.canvas.saveAsImage(filename,None,"PNG")

    def extractAttributeSummary(self, attribute):
        # get summary of the attribute
        summary = []
        layer = self.getSelectedLayer()

        # send this to the table
        self.clearTable()
        self.updateTable(summary)

    # report window functions
    def updateReport(self,report):
        self.reportList.clear()
        self.reportList.addItems(report)

    def insertReport(self,item):
        self.reportList.insertItem(0, item)

    def clearReport(self):
        self.reportList.clear()

    # table window functions
    def updateTable(self, values):
        # takes a list of label / value pairs, can be tuples or lists. not dictionaries to control order
        self.statisticsTable.setHorizontalHeaderLabels(["Item","Value"])
        self.statisticsTable.setRowCount(len(values))
        for i, item in enumerate(values):
            self.statisticsTable.setItem(i,0,QtGui.QTableWidgetItem(str(item[0])))
            self.statisticsTable.setItem(i,1,QtGui.QTableWidgetItem(str(item[1])))
        self.statisticsTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.statisticsTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.statisticsTable.resizeRowsToContents()

    def clearTable(self):
        self.statisticsTable.clear()


#TEST
