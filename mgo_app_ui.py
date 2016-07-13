# mGo - by Stuart Tozer and Antonio Neto

# code to launch in Maya...
"""
import mgo_maya; reload(mgo_maya)
import mgo_convert; reload(mgo_convert)
import mgo_main; reload(mgo_main)
import mgo_app_ui; reload(mgo_app_ui); mgo_app_ui.run()
"""


from PySide import QtCore, QtGui, QtUiTools
import os
import sys
import socket
import mgo_utils

MGO_PATH = os.path.expanduser("~") + '/Mari/mGo'
ASSETS_PATH = MGO_PATH + '/Assets'
PRESETS_PATH = MGO_PATH + '/Presets'
CONFIG_PATH = MGO_PATH + '/mGo_config.txt'
MAIN_UI = MGO_PATH + "/UIs/app_ui.ui"
CLEANUP_UI = MGO_PATH + "/UIs/cleanup_ui.ui"
ADD_IP_UI = MGO_PATH + "/UIs/ip_ui.ui"

cleanup_UI = None
add_ip_UI = None

def _get_app():
    exe_path = sys.executable.lower()
    if 'maya' in exe_path: 
        import mgo_maya
        return mgo_maya.MgoMaya()

    if ('2014\\3dsmax' in exe_path) or ('2015\\3dsmax' in exe_path) or ('2016\\3dsmax' in exe_path):
        pass

APP = _get_app()


class MgoAppUI(QtGui.QWidget):

    """Application agnostic class providing a toolbar styled UI for sending data to Mari.

    Methods in this class deal with reading or writing data to the app configuration file, 'mGo.cfg'
    (located in the Mari user directory), populating and updating the various UI elements, and calling application
    specific methods via the instanced 'app' module (eg. 'self.app.export_cameras').

    No application specific commands reside here (eg, 'maya.cmds').

    During initialisation, the 'mGo.cfg' file is written to the user's Mari/mGo directory if it doesn't already exist.

    """

    version = ".11"

    def __init__(self, app):
        QtGui.QWidget.__init__(self)

        print "mgo_app_ui version: " + MgoAppUI.version

        self.ui = QtUiTools.QUiLoader().load(MAIN_UI)
        self.utils = mgo_utils.MgoUtils()                  # useful class of methods shared between all mGo modules
        self.app = app                                     # all application specific methods
        self.icons_path = self.app.icons_path
        self.assets_path = ASSETS_PATH
        self.config = self.utils.get_config()              # config file for reading/writing mGo data related to ui
        self.ip = self.utils.get_ip_list()                 # local ip addresses
        self.mari_host = 'localhost'                       # mari host address
        self.mari = None                                   # socket object for talking to Mari
        self.project = 'new'                               # defaults to 'new' on ui startup
        self.send_mode = "new"

        self.setup_ui()

    def setup_ui(self):
        self.ui.addHost_btn.setIcon(QtGui.QPixmap(self.icons_path + 'mGo_add.png'))
        self.ui.browseDir_btn.setIcon(QtGui.QPixmap(self.icons_path + 'mGo_browse.png'))
        self.ui.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint )
        self.ui.setFixedSize(self.ui.size())
        self.ui.setWindowTitle("mGo - " + str(self.ip[0]))
        self.ui.exportGeo_btn.clicked.connect(self.send_geo)
        self.ui.hdriRender_btn.clicked.connect(self.send_hdri)
        self.ui.exportCameras_btn.clicked.connect(self.send_cameras)
        self.ui.ExportShaders_btn.clicked.connect(self.export_shaders)
        self.ui.browseDir_btn.clicked.connect(self.browse_assets_dir)
        self.ui.newProject_edit.editingFinished.connect(self.set_assets_dir)
        self.ui.assetsPath_edit.editingFinished.connect(self.set_assets_dir)
        self.ui.newProject_rdo.clicked.connect(self.radio_new_project)
        self.ui.addProject_rdo.clicked.connect(self.radio_add_project)
        self.ui.versionProject_rdo.clicked.connect(self.radio_version_project)
        self.ui.projects_combo.currentIndexChanged.connect(self.set_project)
        self.ui.addHost_btn.clicked.connect(self.new_ip_address)
        self.ui.hosts_combo.currentIndexChanged.connect(self.set_mari_host)
        self.ui.cleanupAssets_btn.clicked.connect(self.cleanup_assets)
        self.ui.assetsPath_edit.setText(ASSETS_PATH)

        self.get_mari_hosts()
        self.get_mari_projects()

    def get_mari_hosts(self):
        self.ui.hosts_combo.blockSignals(True)
        hosts = self.config['mari hosts']
        current_host = self.config['_current host']

        self.ui.hosts_combo.clear()
        self.ui.hosts_combo.addItems(hosts.keys())

        if current_host:
            self.ui.hosts_combo.setCurrentIndex(self.ui.hosts_combo.findText(current_host))

        self.ui.hosts_combo.blockSignals(False)
        self.set_mari_host()

    def set_mari_host(self):
        hosts = self.config['mari hosts']
        host = self.ui.hosts_combo.currentText()

        self.config['_current host'] = host
        self.utils.json_write(self.config, CONFIG_PATH)

        for key, value in hosts.iteritems():
            if host == key:
                self.mari_host = value

        self.mari_connect()

    def mari_connect(self):
        try:
            self.mari = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.mari.connect((self.mari_host, 6100))
            self.mari.send('print "Establishing connection with mGo..."\x04')

        except socket.error:
            self.mari = None

        if self.mari:
            self.ui.mGo_icon.setPixmap(self.icons_path + 'mGo_green.png')
            self.app.hover_message("Mari Connection Established")
        else:
            self.ui.mGo_icon.setPixmap(self.icons_path + 'mGo_red.png')
            self.app.hover_message("Unable to reach Mari at network address '%s'" % self.mari_host)

    def mari_disconnect(self):
        self.mari.close()

    def get_mari_projects(self):
        self.ui.projects_combo.clear()

        if self.mari:
            self.mari.send('mari.examples.mgo_mari.get_projects("%s")\x04' % CONFIG_PATH)
            self.mari_disconnect()
            import time; time.sleep(1)  # quick pause to allow writing of config file

        self.config = self.utils.get_config()
        projects = self.config['mari projects']

        if projects:
            projects.sort()
            self.ui.projects_combo.addItems(projects)
        else:
            self.ui.projects_combo.addItems(["- Projects -"])

        self.set_project()

    def set_project(self, update_assets_dir=True):
        if self.ui.newProject_rdo.isChecked():
            self.project = self.ui.newProject_edit.text()
        else:
            self.project = self.ui.projects_combo.currentText()

        if update_assets_dir:
            # check the config for the project path
            assets_paths = self.config['assets paths']

            for project, path in assets_paths.iteritems():
                if project == self.project:
                    self.ui.assetsPath_edit.setText(path)

    def browse_assets_dir(self):
        directory = str(QtGui.QFileDialog.getExistingDirectory(dir=self.ui.assetsPath_edit.text(),
                                                               caption="Choose Assets Export Directory"))
        if directory:
            self.ui.assetsPath_edit.setText(directory)
            self.set_assets_dir()

    def set_assets_dir(self):
        directory = self.ui.assetsPath_edit.text()
        if directory:
            directory = directory.replace("\\", "/")
            self.assets_path = directory
            self.ui.assetsPath_edit.setText(directory)
            self.write_project_path()

    def write_project_path(self):
        self.set_project(update_assets_dir=False)
        self.config['assets paths'][str(self.project)] = str(self.assets_path)
        self.utils.json_write(self.config, CONFIG_PATH)

    def radio_new_project(self):
        self.send_mode = "new"
        self.ui.newProject_edit.setEnabled(True)
        self.ui.projects_combo.setEnabled(False)
        self.set_project()

    def radio_add_project(self):
        self.send_mode = "add"
        self.ui.newProject_edit.setEnabled(False)
        self.ui.projects_combo.setEnabled(True)
        self.set_project()

    def radio_version_project(self):
        self.send_mode = "version"
        self.ui.newProject_edit.setEnabled(False)
        self.ui.projects_combo.setEnabled(True)
        self.set_project()

    def send_geo(self):
        is_animated = self.ui.geoAnim_chk.isChecked()
        tex_res = self.ui.chanRes_combo.currentText()
        subdivs = self.ui.subdivs_combo.currentText()
        """
        geo_object = self.app.GeoExport(self.project, self.assets_path, self.send_mode, tex_res, subdivs, is_animated)
        """

    def send_geosend_geo(self, namespace, groups, filepath,):
        pass
        """
        self.mari.connect()
        if self.mari:
            self.mari.send('mari.examples.mGo.importGEO("%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", '
                           '"%s", "%s", "%s", "%s")\x04' %
                           (self.send_mode, self.project, namespace, groups, filePath, setR, sd, isAnim, startAnim, endAnim,
                            nameSpace + currentMesh, myFileName, meshData, shadersOnly))
                            """

    def send_hdri(self):
        if self.ui.hdriView_rdo.isChecked():
            render_position = "view"
        else:
            render_position = "objects"

        if self.send_mode == "new":
            self.app.hover_message("HDRIs cannot export to 'New' project. Select 'Add' or 'Version' instead")
            return

        hdri = self.app.HDRIRender(self.assets_path, self.project, self.send_mode, render_position)
        image_path = hdri.image_path

        self.mari_connect()

        if self.mari:
            self.mari.send('mari.examples.mgo_mari.import_hdri("%s", "%s")\x04' % (self.project, image_path))
            self.mari_disconnect()
            self.app.hover_message("HDRI sent to Mari")

    def send_cameras(self):
        if self.send_mode == "new":
            self.app.hover_message("Camera's Can't be exported to New Scenes. Choose 'Add' or 'Version' instead")
            return

        # export the cameras as .fbx and return various data
        data = self.app.export_cameras(self.assets_path, self.project)

        cameras_filepath = data[0]
        start_time = data[1]
        end_time = data[2]

        self.mari_connect()

        if self.mari:
            # import the cameras
            self.mari.send('mari.examples.mgo_mari.import_cameras("%s", "%s", "%s", "%s")\x04' % (self.project,
                                                                                                  cameras_filepath,
                                                                                                  start_time,
                                                                                                  end_time))
            self.mari_disconnect()
            self.app.hover_message("Cameras sent to Mari")

    def export_shaders(self):
        self.app.export_shaders_to_presets_dir(PRESETS_PATH)

    def open_ports(self):
        self.ui.ip_label.setText(self.ip_list[0])

        if self.mari_host == "127.0.0.1":
            for ip in self.ip_list:
                self.app.close_port(ip)
        else:
            for ip in self.ip_list:
                self.app.open_port(ip)

    # create 'add IP' UI
    def new_ip_address(self):
        global add_ip_UI
        add_ip_UI = MGOAddIpUI(self)
        add_ip_UI.ui.show()

    # create 'cleanup assets' UI
    def cleanup_assets(self):
        if os.path.exists(ASSETS_PATH):
            global cleanup_UI
            cleanup_UI = MGOCleanupUI(self)
            cleanup_UI.ui.show()
        else:
            self.app.hover_message("'%s' directory doesn't exist" % ASSETS_PATH)


class MGOAddIpUI(QtGui.QWidget):
    def __init__(self, parent):
        QtGui.QWidget.__init__(self)
        self.parent = parent
        self.ui = QtUiTools.QUiLoader().load(ADD_IP_UI)
        self.ui.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.ui.ok_btn.clicked.connect(self.new_ip_address)

    def new_ip_address(self):
        new_address = self.ui.ip_edit.text()
        new_name = self.ui.hostname_edit.text()

        self.parent.config['mari hosts'][str(new_name)] = str(new_address)
        self.parent.config['_current host'] = str(new_name)

        self.parent.main.json_write(self.parent.config, CONFIG_PATH)
        self.ui.close()
        self.parent.app.hover_message("Attempting to Connect to Mari")
        self.parent.get_mari_hosts()


class MGOCleanupUI(QtGui.QWidget):
    def __init__(self, parent):
        QtGui.QWidget.__init__(self)
        self.parent = parent
        self.directory = self.parent.ui.assetsPath_edit.text()

        self.ui = QtUiTools.QUiLoader().load(CLEANUP_UI)
        self.ui.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        self.ui.delSelected_btn.clicked.connect(self.delete_selected)
        self.ui.delAll_btn.clicked.connect(self.delete_all)

        self.list_folders()

    def list_folders(self):
        self.ui.cleanup_list.clear()
        folders = os.listdir(self.directory)
        self.ui.cleanup_list.addItems(folders)

    def delete_selected(self):
        folders = []

        for item in self.ui.cleanup_list.selectedItems():
            self.ui.cleanup_list.setCurrentItem(item)
            folder = self.ui.cleanup_list.currentItem().text()
            folders.append(folder)

        for f in folders:
            self.delete(f)

        self.list_folders()

    def delete_all(self):
        self.ui.cleanup_list.selectAll()
        self.delete_selected()

    def delete(self, folder):
        import shutil
        try:
            full_path = self.directory + "/" + folder
            shutil.rmtree(full_path)
        except:
            self.parent.app.hover_message("Couldn't delete '%s' folder. Possibly in use" % folder)


def run():
    global UI
    UI = MgoAppUI(APP)
    UI.ui.show()
