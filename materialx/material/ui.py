# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2022, AMD

from pathlib import Path

import traceback
import MaterialX as mx

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .. import utils
from ..utils import import_materialx_from_file, export
from ..preferences import addon_preferences

from ..utils import logging
log = logging.Log(tag='material.ui')


class MATERIAL_OP_import_file(bpy.types.Operator, ImportHelper):
    bl_idname = utils.with_prefix('nodes_import_file')
    bl_label = "Import from File"
    bl_description = "Import MaterialX node tree from .mtlx file"

    filename_ext = ".mtlx"
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="File path used for importing MaterialX node tree from .mtlx file",
        maxlen=1024, subtype="FILE_PATH"
    )
    filter_glob: bpy.props.StringProperty(default="*.mtlx", options={'HIDDEN'}, )

    def execute(self, context):
        mx_node_tree = context.space_data.edit_tree
        mtlx_file = Path(self.filepath)

        doc = mx.createDocument()
        search_path = mx.FileSearchPath(str(mtlx_file.parent))
        search_path.append(str(utils.MX_LIBS_DIR))
        try:
            mx.readFromXmlFile(doc, str(mtlx_file))
            import_materialx_from_file(mx_node_tree, doc, mtlx_file)

        except Exception as e:
            log.error(traceback.format_exc(), mtlx_file)
            return {'CANCELLED'}

        return {'FINISHED'}


class MATERIAL_OP_export_file(bpy.types.Operator, ExportHelper):
    bl_idname = utils.with_prefix('material_export_file')
    bl_label = "Export to File"
    bl_description = "Export material as MaterialX node tree to .mtlx file"

    # region properties
    filename_ext = ".mtlx"

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="File path used for exporting material as MaterialX node tree to .mtlx file",
        maxlen=1024,
        subtype="FILE_PATH"
    )
    filter_glob: bpy.props.StringProperty(
        default="*.mtlx",
        options={'HIDDEN'},
    )
    is_export_deps: bpy.props.BoolProperty(
        name="Include dependencies",
        description="Export used MaterialX dependencies",
        default=False
    )
    is_export_textures: bpy.props.BoolProperty(
        name="Export textures",
        description="Export bound textures to corresponded folder",
        default=True
    )
    is_clean_texture_folder: bpy.props.BoolProperty(
        name="Сlean texture folder",
        description="Сlean texture folder before export",
        default=False
    )
    texture_dir_name: bpy.props.StringProperty(
        name="Folder name",
        description="Texture folder name used for exporting files",
        default='textures',
        maxlen=1024,
    )
    # endregion

    def execute(self, context):
        doc = export(context.material, None)
        if not doc:
            return {'CANCELLED'}

        utils.export_mx_to_file(doc, self.filepath,
                                mx_node_tree=None,
                                # is_export_deps=self.is_export_deps,
                                is_export_textures=self.is_export_textures,
                                texture_dir_name=self.texture_dir_name)

        return {'FINISHED'}

    def draw(self, context):
        # self.layout.prop(self, 'is_export_deps')

        col = self.layout.column(align=False)
        col.prop(self, 'is_export_textures')

        row = col.row()
        row.enabled = self.is_export_textures
        row.prop(self, 'texture_dir_name', text='')


class MATERIAL_OP_export_console(bpy.types.Operator):
    bl_idname = utils.with_prefix('material_export_console')
    bl_label = "Export to Console"
    bl_description = "Export material as MaterialX node tree to console"

    def execute(self, context):
        doc = export(context.material, context.object)
        if not doc:
            return {'CANCELLED'}

        print(mx.writeToXmlString(doc))
        return {'FINISHED'}


class MATERIAL_PT_tools(bpy.types.Panel):
    bl_idname = utils.with_prefix('MATERIAL_PT_tools', '_', True)
    bl_label = "MaterialX Tools"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Tool"

    @classmethod
    def poll(cls, context):
        tree = context.space_data.edit_tree

        return tree and tree.bl_idname == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout

        layout.operator(MATERIAL_OP_import_file.bl_idname, icon='IMPORT')
        layout.operator(MATERIAL_OP_export_file.bl_idname, icon='EXPORT')


class MATERIAL_PT_dev(bpy.types.Panel):
    bl_idname = utils.with_prefix('MATERIAL_PT_dev', '_', True)
    bl_label = "Dev"
    bl_parent_id = MATERIAL_PT_tools.bl_idname
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        preferences = addon_preferences()
        return preferences.dev_tools if preferences else True

    def draw(self, context):
        layout = self.layout
        layout.operator(MATERIAL_OP_export_console.bl_idname)
