import maya.cmds as cmds
import os
import maya.mel
from PySide import QtCore, QtGui
import json

import mgo_convert
reload(mgo_convert)


class MgoMaya(object):
    """All Maya specific functionality"""

    version = ".13"

    def __init__(self):
        print "mgo_maya version: " + MgoMaya.version
        self.accepted_shaders = ['aiStandard', 'VRayMtl', 'RedshiftArchitectural']
        self.accepted_renderers = ['vray', 'redshift', 'arnold']
        self.icons_path = cmds.internalVar(upd=True) + "icons/"

        if not cmds.pluginInfo('fbxmaya', q=True, l=True):
            cmds.loadPlugin('fbxmaya')

    def hover_message(self, message):
        cmds.inViewMessage(amg='%s' % message, pos='botCenter', fade=True, fadeOutTime=500)


    class Import(object):
        def __init__(self, mgo_description):

            self.geo = None
            self.geo_name = None
            self.shader_type = None
            self.shader_name = None
            self.previous_shader_name = None
            self.previous_shading_group = None
            self.shader = None
            self.shading_group = None
            self.sd = None  # shader data
            self.udim_format = None

            if os.path.isfile(mgo_description):
                with open(mgo_description, 'r') as fp:
                    description_data = json.load(fp)

                if description_data:
                    # Load each description
                    for mgo_filepath in description_data:
                        self.import_data(mgo_description, mgo_filepath)

        def import_data(self, mgo_description, mgo_filepath):
            if not os.path.isfile(mgo_filepath):
                return

            with open(mgo_filepath, 'r') as fp:
                self.sd = json.load(fp)      # shader data

            self.shader_type = self.sd['shader type']
            self.shader_name = self.sd['shader name']
            self.geo_name = self.sd['geo name']
            self.previous_shader_name = "mGo_" + self.shader_name + "_mat"
            self.previous_shading_group = "mGo_" + self.shader_name + "_SG"

            if self.sd['geo import']:
                self.import_geo()

            # create shader  / textures only if attributes or channels checkboxes were checked in mari
            if self.sd['channels import'] or self.sd['attributes import']:
                self.get_udim_format()
                #self.delete_old_shader_connections()

                if self.shader_type == 'VRayMtl':
                    self.prepare_vray_shader()

                elif self.shader_type == 'Ai Standard':
                    self.prepare_arnold_shader()

                elif self.shader_type == 'Redshift Architectural':
                    self.prepare_redshift_shader()

            # keep old shader if it exists, otherwise create new one
            if cmds.objExists(self.previous_shader_name):
                self.shader = self.previous_shader_name
                print "updating previous %s mat" % self.shader_type
            else:
                self.shader = cmds.shadingNode("%s" % self.shader_type, asShader=True, n=self.previous_shader_name)
                print "created new %s mat" % self.shader_type

            # keep old shading group if exists, otherwise create new one
            if cmds.objExists(self.previous_shading_group):
                self.shading_group = self.previous_shading_group
            else:
                self.shading_group = cmds.sets(n=self.previous_shading_group, r=True, nss=True, em=True)
                cmds.connectAttr('%s.outColor' % self.shader, '%s.surfaceShader' % self.shading_group)

            # create filenode for each channel
            for channel, value in self.sd['channels'].iteritems():
                texture_path = value[1].replace('$UDIM', self.udim_format)
                filenode_name = self.geo_name + "_" + channel
                if not cmds.objExists(filenode_name):
                    filenode = cmds.shadingNode("file", asTexture=True, n=filenode_name)

                # set other filenode attrs
                cmds.setAttr('%s.fileTextureName' % filenode, texture_path, type="string")
                cmds.setAttr(filenode + '.alphaIsLuminance', 1)
                cmds.setAttr(filenode + '.uvTilingMode', 3)
                if self.sd['filter type'] == "None":
                    cmds.setAttr(filenode + '.filterType', 0)
                elif self.sd['filter type'] == "Mipmap":
                    cmds.setAttr(filenode + '.filterType', 1)

                # connect filenode to shader
                try:
                    cmds.connectAttr('%s.outColor' % filenode, '%s.%s' % (self.shader, channel))
                except:
                    cmds.connectAttr('%s.outAlpha' % filenode, '%s.%s' % (self.shader, channel))

        def delete_old_shader_connections(self):
            pass
            """
            try:
                # get downnodes
                downNodes = cmds.listHistory(matName)
                check = cmds.ls(downNodes, type='file')
                check += cmds.ls(downNodes, type='gammaCorrect')
                check += cmds.ls(downNodes, tex=True)
                # delete them
                try:
                    cmds.delete(check)
                    print "deleted old file, utility nodes"
                except TypeError:
                    pass

            except ValueError:
                print "Trying to delete old shader nodes."
                # print a msg in case the shader exists but the delete process failed.
                if cmds.objExists(matName) == True:
                    print "Could not find any node connected to the shader: '" + matName + "' make sure the shader exists."

            # try to delete any possible remain shader network left just one time for each obj.
            global shaderNetworkDel
            if shaderNetworkDel != True:
                shaderNetworkDel = True
                try:
                    cmds.delete(nameSpace + str(geoName) + "_samplerInfo")
                    cmds.delete(nameSpace + str(geoName) + "_samplerInfo_reverse")
                except:
                    pass
                # delete displacement node and texture
                try:
                    dispNode = nameSpace + "mGo_" + curShaderStr + "_dispNode"
                    downNodes = cmds.listHistory(dispNode)
                    check = cmds.ls(downNodes)
                    cmds.delete(check)
                except:
                    pass
                    """

        def get_udim_format(self):
            udim = self.sd['udim']
            if udim == 'multi':
                if self.sd['shader type'] == "Ai Standard":
                    self.udim_format = "<udim>"
                elif self.sd['shader type'] == "VRayMtl":
                    self.udim_format = "<UDIM>"
                elif self.sd['shader type'] == "Redshift Architectural":
                    self.udim_format = "<UDIM>"
            else:
                self.udim_format = udim

        def import_geo(self):
            print "importing geo"
            mari_geo_path = self.sd['geo path']
            geo_list = cmds.ls(tr=True)
            for geo in geo_list:
                if self.geo_name == geo:
                    self.geo = geo

            if not self.geo:
                try:
                    # self.geo = cmds.file(mari_geo_path, i=True, f=True, options='mo=0')
                    self.geo = cmds.file(mari_geo_path, i=True, f=True, rnn=True, namespace="", options='mo=0')
                    # self.geo = cmds.rename(file_name + "_obj:polySurface1", geoName)
                    print "geo imported"
                    cmds.inViewMessage(amg='Object imported', pos='botCenter', fade=True, fadeOutTime=500)
                except:
                    self.geo = None
                    print "GEO IMPORT FAILED - (geo has likely been moved from the original mari import location)"
                    print "Mari Geo path: " + mari_geo_path

        def replace_converted_attr_and_channel_names(self, converted_attrs, converted_channels):
            self.sd['attributes'] = {}
            for key, value in converted_attrs.iteritems():
                self.sd['attributes'][key] = value

            self.sd['channels'] = {}
            for key, value in converted_channels.iteritems():
                self.sd['channels'][key] = value

        def prepare_vray_shader(self):
            # load plugin
            if not cmds.pluginInfo('vrayformaya', q=True, l=True):
                cmds.loadPlugin('vrayformaya')
            if cmds.getAttr("defaultRenderGlobals.ren") != 'vray':
                cmds.setAttr('defaultRenderGlobals.ren', 'vray', type='string')

            # convert mari attr names to maya vray attr names
            converted_attrs = mgo_convert.VRayMtl(self.sd['attributes'], reverse=True)
            converted_channels = mgo_convert.VRayMtl(self.sd['channels'], reverse=True)
            self.replace_converted_attr_and_channel_names(converted_attrs, converted_channels)

        def prepare_arnold_shader(self):
            # load plugin
            if not cmds.pluginInfo('mtoa', q=True, l=True):
                cmds.loadPlugin('mtoa')
            if cmds.getAttr("defaultRenderGlobals.ren") != 'arnold':
                cmds.setAttr('defaultRenderGlobals.ren', 'arnold', type='string')
            cmds.callbacks(executeCallbacks=True, hook='updateMayaRenderingPreferences')

            # convert mari attr names to arnold attr names
            converted_attrs = mgo_convert.AiStandard(self.sd['attributes'], reverse=True)
            for attr in converted_attrs:
                self.sd['attributes'][attr[0]] = attr[1]

        def prepare_redshift_shader(self):
            # load plugin
            if not cmds.pluginInfo('redshift4maya', q=True, l=True):
                cmds.loadPlugin('redshift4maya')
            if cmds.getAttr("defaultRenderGlobals.ren") != 'redshift':
                cmds.setAttr('defaultRenderGlobals.ren', 'redshift', type='string')

            # convert mari attr names to redshift attr names
            converted_attrs = mgo_convert.RedshiftArchitectural(self.sd['attributes'], reverse=True)
            for attr in converted_attrs:
                self.sd['attributes'][attr[0]] = attr[1]


    class GeoExport(object):
        def __init__(self, project, assets_path, send_mode, tex_res, subdivs, is_animated):
            self.project = project
            self.assets_path = assets_path
            self.send_mode = send_mode
            self.tex_res = tex_res
            self.subdivs = subdivs
            self.is_animated = is_animated
            #self.send_shader = send_shader
            self.selected_geo = []

            self.export_geo_main()

        def export_geo_main(self):
            """
            print "self.send_mode"
            self.selected_geo = cmds.ls(selection=True, typ='mesh', dag=True)

            if not self.selected_geo:
                cmds.inViewMessage(amg='Please select geometry for export', pos='botCenter', fade=True,
                                   fadeOutTime=500)
                return

            if self.send_mode == "new":
                if not os.path.exists(self.assets_path + "/" + self.project):
                    os.makedirs(self.assets_path + "/" + self.project)



            #connect to Mari!?

            # Initial the creation project in Mari.
            if sendMode == 1:
                mari.send(
                    'mari.examples.mGo.importGEO("%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s")\x04' % (
                        sendMode, projectName, "initialCreation", "initialCreation", setR, sd, isAnim, startAnim,
                        endAnim,
                        "initialCreation", "initialCreation", "initialCreation", "initialCreation", False))
                mari.close()
                sendMode = 2
                mari = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                mari.connect((mariHost, 6100))

            # update just the Shaders?
            #work out if we just want to send the shaders... 'shadersOnly'


            for geo in self.selected_geo:
                geo_transform = cmds.listRelatives(geo, parent=True)[0]  # will also serve as the geo name
                namespace = geo.rsplit(":", 1)[0]
                groups = ''
                group_names = cmds.listRelatives(geo_transform, fullPath=True)[0].split("|")[0:-2]
                if len(group_names) > 1:
                    for group_name in group_names:
                        groups += group_name.rsplit(":")[-1] + "|"

                    # strip unnecessary '|' chars from the beginning and the end of the string
                    groups = groups.strip("|")

                if namespace == geo:
                    namespace = None

                filename = ""
                if namespace:
                    filename = filename + namespace + "_"
                if groups:
                    filename = filename + groups.replace("|", "_") + "_"

                filename = filename + geo_transform + "_v0"
                version = 1
                filepath = self.assets_path + "/" + self.project + "/" + filename + str(version) + ".fbx"

                if self.send_mode == "version":
                    while os.path.exists(filepath):
                        version += 1
                        filepath = self.assets_path + "/" + self.project + "/" + filename + str(version) + ".fbx"

                # get final obj version Name without namespaces and group names
                filename = geo_transform + "_v0" + str(version)

                # write out the file
                cmds.select(geo)

                maya.mel.eval('FBXExportFileVersion "FBX201200"')
                maya.mel.eval('FBXExportInAscii -v true')
                maya.mel.eval('FBXExportSmoothingGroups -v true')
                maya.mel.eval('FBXExportQuickSelectSetAsCache -v "setName"')
                maya.mel.eval('FBXExportAnimationOnly -v false')

                maya.mel.eval(('FBXExport -f \"{}\" -s').format(filepath))

                # other data gets written out here
                geo_data = self.create_geo_data(geo, namespace, groups, filepath, filename, start_frame, end_frame)
                """

        def create_geo_data(self, geo, namespace, groups, filepath, filename, start_frame, end_frame):
            """
            data = {'geo': geo,
                    'sd level': self.subdivs,
                    'sd method': "Catmull Clark",
                    'sd boundary': "Always Sharp",
                    'send mode': self.send_mode,
                    'project': self.project,
                    'namespace': namespace,
                    'groups': groups,
                    'filepath': filepath,
                    'tex resolution': self.tex_res,
                    'is animated': self.is_animated,
                    'start frame': start_frame,
                    'end frame': end_frame,
                    'filename': filename,
                    'shaders only': False}

            if self.subdivs is 'auto':
                # see if 'smooth mesh preview' is checked, if not subdivs will be 0
                if cmds.getAttr('%s.displaySmoothMesh' % geo) == 2:
                    # Get the value from SmoothPreviewForRender ?
                    if cmds.getAttr('%s.useSmoothPreviewForRender' % geo) == 1:
                        data['sd_level'] = str(cmds.getAttr('%s.smoothLevel' % geo))
                    else:
                        data['sd_level'] = str(cmds.getAttr('%s.renderSmoothLevel' % geo))

                if cmds.getAttr('%s.smoothDrawType' % geo) != 0:
                    # 0 - (No Interpolation), 1 - (Sharp Edges and Corners), 2 - (Sharp Edges), 3 - (All sharp)
                    if cmds.getAttr('%s.osdFvarBoundary' % geo) == 0:
                        data['sd_boundary'] = None

                    if cmds.getAttr('%s.osdFvarBoundary' % geo) == 1:
                        if cmds.getAttr('%s.osdFvarPropagateCorners' % geo) == 0:
                            data['sd_boundary'] = 'Edge And Corner'
                        else:
                            data['sd_boundary'] = 'Always Sharp'

                    if cmds.getAttr('%s.osdFvarBoundary' % geo) == 2:
                        data['sd_boundary'] = 'Edge Only'
                    else:
                        data['sd_boundary'] = 'Always Sharp'
                else:
                    # Maya's default subdivision method
                    if cmds.getAttr('%s.smoothUVs' % geo) == 1:
                        # 0 - Smooth all, 1 - Smooth Internal, 2 - Do not Smooth
                        if (cmds.getAttr('%s.keepMapBorders' % geo) == 0) \
                                or (cmds.getAttr('%s.keepMapBorders' % geo) == 1):
                            data['sd_boundary'] = 'Edge Only'
                        else:
                            data['sd_boundary'] = 'Always Sharp'
                    else:
                        data['sd_boundary'] = None
            return data
            """

    def export_cameras(self, assets_path, project):
        valid_cameras = None
        selected_cameras = cmds.ls(sl=True, dag=True, ca=True)

        for cam in selected_cameras:
            if cam != "perspShape" and cam != "topShape" and cam != "frontShape" and cam != "sideShape":
                valid_cameras = True

        if not valid_cameras:
            cmds.inViewMessage(
                amg="No valid cameras selected (default 'persp' camera not supported in FBX export)",
                pos='botCenter', fade=True, fadeOutTime=500)
            return

        start_frame = str(cmds.playbackOptions(query=True, minTime=True))
        end_frame = str(cmds.playbackOptions(query=True, maxTime=True))

        if not os.path.exists(assets_path + "/" + project):
            os.makedirs(assets_path + "/" + project)

        output_file = assets_path + "/" + project + "/" + project + "_cameras.fbx"

        print "Camera file name: " + output_file

        # save the cameras to assets folder
        maya.mel.eval('FBXExportFileVersion "FBX201200"')
        maya.mel.eval('FBXExportInAscii -v true')
        maya.mel.eval("FBXExportCameras -v true")
        cmds.file(output_file, force=True, options='v=0', type='FBX export', pr=True, es=True)

        return [output_file, start_frame, end_frame]

    def export_shaders_to_presets_dir(self, presets_path):
        shaders = cmds.selectedNodes()
        if not shaders:
            cmds.inViewMessage(amg='Please select Shaders for Export', pos='midCenter', fade=True, fadeOutTime=500)
            return

        for shader in shaders:
            shader_type = cmds.nodeType(shader)
            if shader_type not in self.accepted_shaders:
                cmds.inViewMessage(amg='Please select from the following shader types: %s ' % self.accepted_shaders,
                                   pos='midCenter', fade=True, fadeOutTime=500)
                return

        directory = str(QtGui.QFileDialog.getExistingDirectory(dir=presets_path,
                                                               caption="Choose Shader Preset Directory"))
        if directory:
            directory = directory.replace('\\', '/')

            for shader in shaders:
                data = self.get_shader_data(shader)
                output_path = directory + "/" + data['shader name'] + ".pre"

                with open(output_path, 'w') as outfile:
                    json.dump(data, outfile, sort_keys=True, indent=4, separators=(',', ': '))

        cmds.inViewMessage(amg='Export finished', pos='midCenter', fade=True, fadeOutTime=500)

    def get_shader_data(self, shader):
        data = {}

        data['shader name'] = shader.replace("mGo_", "")
        data['shader type'] = cmds.nodeType(shader)
        data['renderer'] = cmds.getAttr('defaultRenderGlobals.currentRenderer')
        data['pre_converted_attributes'] = {}
        data['attributes'] = {}

        shader_attrs = cmds.listAttr(shader)

        for attr in shader_attrs:
            attr_type = cmds.getAttr(shader + "." + attr, type=True)
            if attr_type != "message":  # message attributes have no values
                attr_value = cmds.getAttr(shader + "." + attr, sl=True)

                if type(attr_value) == list:
                    attr_value = attr_value[0]

                attr_list = [attr_value, attr_type]
                data['pre_converted_attributes'][attr] = attr_list

        data['attributes'] = mgo_convert.VRayMtl(data['pre_converted_attributes'])
        data.pop('pre_converted_attributes', None)
        return data

    class HDRIRender(object):
        def __init__(self, assets_path, project, send_mode, render_position):

            self.assets_path = assets_path
            self.project = project
            self.send_mode = send_mode
            self.render_position = render_position

            self.accepted_renderers = ['vray', 'redshift', 'arnold']
            self.image_path = cmds.renderSettings(firstImageName=True,  fpt=True)[0].rsplit('.', 1)[0] + '.exr'
            self.render_geo = cmds.ls(sl=True, typ="transform")
            self.current_renderer = cmds.getAttr('defaultRenderGlobals.currentRenderer')
            self.render_camera = cmds.modelPanel("modelPanel4", query=True, camera=True)
            self.render_camera_xforms = cmds.xform(self.render_camera, q=True, ws=True, m=True)

            self.hdri_render_main()
            self.finalise_render()
            self.image_path = self.prepare_image_path()

        def hdri_render_main(self):
            if self.current_renderer not in self.accepted_renderers:
                cmds.inViewMessage(amg="This feature currently supports Vray, Arnold or Redshift renderers only",
                                   pos="botCenter", fade=True)
                return

            if self.render_position == "object":
                if not self.render_geo:
                    cmds.inViewMessage(amg="Please Select an Object from which to render HDRI View",
                                       pos="botCenter", fade=True)
                    return

                else:
                    # get averaged centre of selected objects
                    x, y, z = 0, 0, 0
                    for geo in self.render_geo:
                        xyz = cmds.objectCenter(geo)
                        x += xyz[0]
                        y += xyz[1]
                        z += xyz[2]

                    objs_centre = x / len(self.render_geo), y / len(self.render_geo), z / len(self.render_geo)
                    cmds.hide(self.render_geo)  # hide objects while rendering

            # zero out any camera rotations and reposition to objects centre if needed
            cmds.setAttr("%s.rotate" % self.render_camera, 0, 0, 0)

            if self.render_position == "object":
                cmds.setAttr("%s.translate" % self.render_camera, objs_centre[0], objs_centre[1], objs_centre[2])

            if self.current_renderer == "vray":
                self.vray_render()
            if self.current_renderer == "redshift":
                self.redshift_render()
            if self.current_renderer == "arnold":
                self.arnold_render()

        def vray_render(self):
            background_invisible = None  # Vray's dome light attr for toggling background visibility
            render_layer = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)

            # store original render settings
            prev_width = cmds.getAttr('vraySettings.width')
            prev_height = cmds.getAttr('vraySettings.height')
            prev_aspect_ratio = cmds.getAttr('vraySettings.aspectRatio')
            prev_image_format = cmds.getAttr('vraySettings.imageFormatStr')
            prev_cam_type = cmds.getAttr('vraySettings.cam_type')
            prev_cam_override_fov = cmds.getAttr('vraySettings.cam_overrideFov')
            prev_cam_fov = cmds.getAttr('vraySettings.cam_fov')
            prev_no_alpha = cmds.getAttr('vraySettings.noAlpha')

            # apply new settings
            cmds.setAttr('vraySettings.width', 2000)
            cmds.setAttr('vraySettings.height', 1000)
            cmds.setAttr('vraySettings.aspectRatio', 2000/1000)
            cmds.setAttr('vraySettings.imageFormatStr', 'exr', type='string')
            cmds.setAttr('vraySettings.cam_type', 1)
            cmds.setAttr('vraySettings.cam_overrideFov', 1)
            cmds.setAttr('vraySettings.cam_fov', 360)
            cmds.setAttr('vraySettings.noAlpha', 1)

            dome_light = cmds.ls(type="VRayLightDomeShape")[0]
            sky = cmds.ls(type="VRaySky")

            if dome_light:
                background_invisible = cmds.getAttr(dome_light + '.invisible')
                if not sky:
                    if background_invisible is True:
                        cmds.setAttr("%s.invisible" % dome_light, 0)

            # render...
            args = ('-camera', self.render_camera, '-layer', render_layer, '-w', 2000, '-h', 1000)
            cmds.vrend(*args)

            # restore settings
            if background_invisible:
                cmds.setAttr(dome_light[0] + '.invisible', background_invisible)

            cmds.setAttr('vraySettings.width', prev_width)
            cmds.setAttr('vraySettings.height', prev_height)
            cmds.setAttr('vraySettings.aspectRatio', prev_aspect_ratio)
            cmds.setAttr('vraySettings.imageFormatStr', prev_image_format, type='string')
            cmds.setAttr('vraySettings.cam_type', prev_cam_type)
            cmds.setAttr('vraySettings.cam_overrideFov', prev_cam_override_fov)
            cmds.setAttr('vraySettings.cam_fov', prev_cam_fov)
            cmds.setAttr('vraySettings.noAlpha', prev_no_alpha)

        def redshift_render(self):
            background_enabled = None  # redshift's dome light attr for toggling background visibility

            # store original settings
            prev_width = cmds.getAttr('defaultResolution.width')
            prev_height = cmds.getAttr('defaultResolution.height')
            prev_device_aspect_ratio = cmds.getAttr('defaultResolution.deviceAspectRatio')
            prev_format = cmds.getAttr('redshiftOptions.imageFormat')

            # apply new settings
            cmds.setAttr('defaultResolution.width', 2000)
            cmds.setAttr('defaultResolution.height', 1000)
            cmds.setAttr('defaultResolution.deviceAspectRatio', 2000 / 1000)
            cmds.setAttr("redshiftOptions.imageFormat", 1)
            cmds.setAttr("%s.rsCameraType" % self.render_camera, 3)

            dome_light = cmds.ls(type="RedshiftDomeLight")
            sky = cmds.ls(type="RedshiftEnvironment")

            if dome_light:
                background_enabled = cmds.getAttr(dome_light[0] + '.background_enable')
                if not sky:
                    if background_enabled is False:
                        cmds.setAttr('redshiftDomeLightShape1.background_enable', 1)

            # render...
            cmds.rsRender(render=True, camera=self.render_camera)

            # restore settings
            cmds.setAttr('defaultResolution.width', prev_width)
            cmds.setAttr('defaultResolution.height', prev_height)
            cmds.setAttr('defaultResolution.deviceAspectRatio', prev_device_aspect_ratio)
            cmds.setAttr('redshiftOptions.imageFormat', prev_format)

            if background_enabled is not None:
                cmds.setAttr('redshiftDomeLightShape1.background_enable', background_enabled)

        def arnold_render(self):
            sky_transform = None

            # store original settings
            prev_width = cmds.getAttr('defaultResolution.width')
            prev_height = cmds.getAttr('defaultResolution.height')
            prev_device_aspect_ratio = cmds.getAttr('defaultResolution.deviceAspectRatio')
            driver = cmds.ls('defaultArnoldDriver')
            prev_format = cmds.getAttr(driver[0] + '.aiTranslator')
            prev_cam_type = cmds.getAttr(self.render_camera + '.aiTranslator')

            # apply new settings
            cmds.setAttr('defaultResolution.width', 2000)
            cmds.setAttr('defaultResolution.height', 1000)
            cmds.setAttr('defaultResolution.deviceAspectRatio', 2000 / 1000)
            cmds.setAttr(driver[0] + '.aiTranslator', 'exr', type='string')
            cmds.setAttr("%s.aiTranslator" % self.render_camera, "spherical", type="string")

            dome_light = cmds.ls(type="aiSkyDomeLight")
            sky = cmds.ls(type="aiSky")

            if dome_light:
                dome_transform = cmds.listRelatives(dome_light, parent=True, fullPath=True)
                if not sky:
                    '''if domelight exists but no sky (background), create one (making the HDRI visible in render)
                    and set dome texture, rotation and intensity values'''

                    dome_texture = cmds.listConnections(dome_light[0] + '.color')[0]

                    if dome_texture is not None:
                        # create new aiSky and plug in dome texture
                        ai_sky = cmds.shadingNode("aiSky", asUtility=True)
                        sky_transform = cmds.listRelatives(ai_sky, allParents=True)
                        cmds.connectAttr("%s.message" % ai_sky, "defaultArnoldRenderOptions.background", f=True)
                        cmds.connectAttr("%s.outColor" % dome_texture, "%s.color" % ai_sky, f=True)

                        # query dome light attrs
                        dome_intensity = cmds.getAttr(dome_light[0] + '.intensity')
                        dome_format = cmds.getAttr(dome_light[0] + '.format')
                        dome_rotation = cmds.getAttr(dome_transform[0] + '.rotateY')

                        # set as aiSky attrs
                        cmds.setAttr('aiSky1.format', dome_format)
                        cmds.setAttr('aiSky1.intensity', dome_intensity)
                        cmds.setAttr(sky_transform[0] + '.rotateY', dome_rotation)

            # render...
            cmds.arnoldRender(cam=self.render_camera)

            if sky_transform is not None:
                cmds.delete(sky_transform)

            cmds.setAttr('defaultResolution.width', prev_width)
            cmds.setAttr('defaultResolution.height', prev_height)
            cmds.setAttr('defaultResolution.deviceAspectRatio', prev_device_aspect_ratio)
            cmds.setAttr(driver[0] + '.aiTranslator', prev_format, type='string')
            cmds.setAttr(self.render_camera + '.aiTranslator', prev_cam_type, type='string')

        def finalise_render(self):
            # unhide geo, reposition camera
            if self.render_geo:
                cmds.showHidden(self.render_geo)

            cmds.setAttr("%s.xformMatrix" % self.render_camera, self.render_camera_xforms, type="matrix")

        def prepare_image_path(self):
            if not os.path.exists(self.assets_path + "/" + self.project):
                os.makedirs(self.assets_path + "/" + self.project)

            render_view = "camera_view"

            if self.render_geo:
                if len(self.render_geo) > 1:
                    render_view = "geo_group"
                else:
                    render_view = self.render_geo[0]

            return self.assets_path + "/" + self.project + "/" + render_view + "_" + "hdri" + ".exr"
