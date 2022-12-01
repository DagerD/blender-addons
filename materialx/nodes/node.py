# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2022, AMD

import MaterialX as mx

import bpy

from .. import utils

from .. import logging
log = logging.Log("nodes.node")


class MxNodeInputSocket(bpy.types.NodeSocket):
    bl_idname = utils.with_prefix('MxNodeInputSocket')
    bl_label = "MX Input Socket"

    def draw(self, context, layout, node, text):
        if not is_mx_node_valid(node):
            return

        nd = node.nodedef
        nd_input = nd.getActiveInput(self.name)
        nd_type = nd_input.getType()

        uiname = utils.get_attr(nd_input, 'uiname', utils.title_str(nd_input.getName()))
        is_prop_area = context.area.type == 'PROPERTIES'
        if self.is_linked or utils.is_shader_type(nd_type) or nd_input.getValue() is None:
            uitype = utils.title_str(nd_type)
            layout.label(text=uitype if uiname.lower() == uitype.lower() or is_prop_area else f"{uiname}: {uitype}")
        else:
            if nd_type == 'boolean':
                layout.use_property_split = False
                layout.alignment = 'LEFT'
            layout.prop(node, node._input_prop_name(self.name), text='' if is_prop_area else uiname)


    def draw_color(self, context, node):
        return utils.get_socket_color(node.nodedef.getActiveInput(self.name).getType()
                                      if is_mx_node_valid(node) else 'undefined')


class MxNodeOutputSocket(bpy.types.NodeSocket):
    bl_idname = utils.with_prefix('MxNodeOutputSocket')
    bl_label = "MX Output Socket"

    def draw(self, context, layout, node, text):
        if not is_mx_node_valid(node):
            return

        nd = node.nodedef
        mx_output = nd.getActiveOutput(self.name)
        uiname = utils.get_attr(mx_output, 'uiname', utils.title_str(mx_output.getName()))
        uitype = utils.title_str(mx_output.getType())
        if uiname.lower() == uitype.lower() or len(nd.getActiveOutputs()) == 1:
            layout.label(text=uitype)
        else:
            layout.label(text=f"{uiname}: {uitype}")

    def draw_color(self, context, node):
        return utils.get_socket_color(node.nodedef.getActiveOutput(self.name).getType()
                                      if is_mx_node_valid(node) else 'undefined')


class MxNode(bpy.types.ShaderNode):
    """Base node from which all MaterialX nodes will be made"""
    _file_path: str
    # bl_compatibility = {'USDHydra'}
    # bl_icon = 'MATERIAL'

    bl_label = ""
    bl_description = ""
    bl_width_default = 200

    _data_types = {}    # available types and nodedefs
    _ui_folders = ()    # list of ui folders mentioned in nodedef
    category = ""

    @classmethod
    def get_nodedef(cls, data_type):
        if not cls._data_types[data_type]['nd']:
            # loading nodedefs
            doc = utils.get_doc(cls._file_path)

            for val in cls._data_types.values():
                val['nd'] = doc.getNodeDef(val['nd_name'])

        return cls._data_types[data_type]['nd']

    @classmethod
    def get_nodedefs(cls):
        for data_type in cls._data_types.keys():
            yield cls.get_nodedef(data_type), data_type

    @property
    def nodedef(self):
        return self.get_nodedef(self.data_type)

    @property
    def mx_node_path(self):
        nd = self.nodedef
        if '/' in self.name or utils.is_shader_type(nd.getActiveOutputs()[0].getType()):
            return self.name

        return f"NG/{self.name}"

    def _folder_prop_name(self, name):
        return f"f_{utils.code_str(name.lower())}"

    def _input_prop_name(self, name):
        return f"nd_{self.data_type}_in_{name}"

    def update(self):
        bpy.app.timers.register(self.mark_invalid_links)

    def mark_invalid_links(self):
        if not is_mx_node_valid(self):
            return

        nodetree = self.id_data

        if not (hasattr(nodetree, 'links')):
            return

        for link in nodetree.links:
            if hasattr(link.from_socket.node, 'nodedef') and hasattr(link.to_socket.node, 'nodedef'):

                socket_from_type = link.from_socket.node.nodedef.getActiveOutput(link.from_socket.name).getType()
                socket_to_type = link.to_socket.node.nodedef.getActiveInput(link.to_socket.name).getType()

                if socket_to_type != socket_from_type:
                    link.is_valid = False
                    continue

                link.is_valid = True

    def update_data_type(self, context):
        # updating names for inputs and outputs
        nodedef = self.nodedef
        for i, nd_input in enumerate(utils.get_nodedef_inputs(nodedef, False)):
            self.inputs[i].name = nd_input.getName()
        for i, nd_output in enumerate(nodedef.getActiveOutputs()):
            self.outputs[i].name = nd_output.getName()

    def init(self, context):
        nodedef = self.nodedef

        for nd_input in utils.get_nodedef_inputs(nodedef, False):
            self.create_input(nd_input)

        for nd_output in nodedef.getActiveOutputs():
            self.create_output(nd_output)

        if self._ui_folders:
            self.update_ui_folders(context)

    def draw_buttons(self, context, layout):
        is_prop_area = context.area.type == 'PROPERTIES'

        if len(self._data_types) > 1:
            layout1 = layout
            if is_prop_area:
                layout1 = layout1.split(factor=0.012, align=True)
                col = layout1.column()
                layout1 = layout1.column()
            layout1.prop(self, 'data_type')

        nodedef = self.nodedef

        if self._ui_folders:
            col = layout.column(align=True)
            r = None
            for i, f in enumerate(self._ui_folders):
                if i % 3 == 0:  # putting 3 buttons per row
                    col.use_property_split = False
                    col.use_property_decorate = False
                    r = col.row(align=True)
                r.prop(self, self._folder_prop_name(f), toggle=True)

        for nd_input in utils.get_nodedef_inputs(nodedef, True):
            f = nd_input.getAttribute('uifolder')

            if f and not getattr(self, self._folder_prop_name(f)):
                continue

            name = nd_input.getName()
            if self.category in ("texture2d", "texture3d") and nd_input.getType() == 'filename':
                split = layout.row(align=True).split(factor=0.4 if is_prop_area else 0.25, align=True)
                col = split.column()
                col.alignment='RIGHT' if is_prop_area else 'EXPAND'
                col.label(text=nd_input.getAttribute('uiname') if nd_input.hasAttribute('uiname')
                          else utils.title_str(name))
                col = split.column()
                col.template_ID(self, self._input_prop_name(name),
                                open="image.open", new="image.new")

            else:
                layout1 = layout
                if is_prop_area:
                    layout1 = layout1.split(factor=0.012, align=True)
                    col = layout1.column()
                    layout1 = layout1.column()
                layout1.prop(self, self._input_prop_name(name))

    # COMPUTE FUNCTION
    def compute(self, out_key, **kwargs):
        from ..bl_nodes.node_parser import NodeItem

        log("compute", self, out_key)

        doc = kwargs['doc']
        nodedef = self.nodedef
        nd_output = self.get_nodedef_output(out_key)
        node_path = self.mx_node_path

        values = []
        for in_key in range(len(self.inputs)):
            nd_input = self.get_nodedef_input(in_key)
            f = nd_input.getAttribute('uifolder')
            if f and not getattr(self, self._folder_prop_name(f)):
                continue

            values.append((in_key, self.get_input_value(in_key, **kwargs)))

        mx_nodegraph = utils.get_nodegraph_by_node_path(doc, node_path, True)
        node_name = utils.get_node_name_by_node_path(node_path)
        mx_node = mx_nodegraph.addNode(nodedef.getNodeString(), node_name, nd_output.getType())

        for in_key, val in values:
            nd_input = self.get_nodedef_input(in_key)
            nd_type = nd_input.getType()

            if isinstance(val, (mx.Node, NodeItem)):
                mx_input = mx_node.addInput(nd_input.getName(), nd_type)
                utils.set_param_value(mx_input, val, nd_type)
                continue

            if isinstance(val, tuple) and isinstance(val[0], mx.Node):
                # node with multioutput type
                in_node, in_nd_output = val
                mx_input = mx_node.addInput(nd_input.getName(), nd_type)
                utils.set_param_value(mx_input, in_node, nd_type, in_nd_output)
                continue

            if utils.is_shader_type(nd_type):
                continue

            nd_val = nd_input.getValue()
            if nd_val is None:
                continue

            mx_input = mx_node.addInput(nd_input.getName(), nd_type)
            utils.set_param_value(mx_input, val, nd_type)

        for nd_input in utils.get_nodedef_inputs(nodedef, True):
            f = nd_input.getAttribute('uifolder')
            if f and not getattr(self, self._folder_prop_name(f)):
                continue

            val = self.get_param_value(nd_input.getName())
            nd_type = nd_input.getType()

            mx_param = mx_node.addInput(nd_input.getName(), nd_type)
            utils.set_param_value(mx_param, val, nd_type)

        if len(nodedef.getActiveOutputs()) > 1:
            mx_node.setType('multioutput')
            return mx_node, nd_output

        return mx_node

    def _compute_node(self, node, out_key, **kwargs):
        # checking if node is already in nodegraph

        doc = kwargs['doc']
        node_path = node.mx_node_path
        mx_nodegraph = utils.get_nodegraph_by_node_path(doc, node_path)
        if mx_nodegraph:
            node_name = utils.get_node_name_by_node_path(node_path)
            mx_node = mx_nodegraph.getNode(node_name)
            if mx_node:
                if mx_node.getType() == 'multioutput':
                    nd_output = node.get_nodedef_output(out_key)
                    return mx_node, nd_output

                return mx_node

        return node.compute(out_key, **kwargs)

    def get_input_link(self, in_key: [str, int], **kwargs):
        """Returns linked parsed node or None if nothing is linked or not link is not valid"""
        from ..bl_nodes import node_parser

        socket_in = self.inputs[in_key]
        if not socket_in.links:
            return None

        link = socket_in.links[0]
        if not link.is_valid:
            log.warn("Invalid link found", link, socket_in, self)
            return None

        link = utils.pass_node_reroute(link)
        if not link:
            return None

        if isinstance(link.from_node, MxNode):
            if not is_mx_node_valid(link.from_node):
                log.warn(f"Ignoring unsupported node {link.from_node.bl_idname}", link.from_node,
                         link.from_node.id_data)
                return None

            return self._compute_node(link.from_node, link.from_socket.name, **kwargs)

        NodeParser_cls = node_parser.NodeParser.get_node_parser_cls(link.from_node.bl_idname)
        if not NodeParser_cls:
            log.warn(f"Ignoring unsupported node {link.from_node.bl_idname}", link.from_node, self.material)
            return None

        output_type = NodeParser_cls.get_output_type(link.to_socket)

        node_parser_cls = NodeParser_cls(node_parser.Id(), kwargs['doc'], None, link.from_node, None,
                                         link.from_socket.name, output_type, {})
        node_item = node_parser_cls.export()

        return node_item

    def get_input_value(self, in_key: [str, int], **kwargs):
        node = self.get_input_link(in_key, **kwargs)
        if node:
            return node

        return self.get_input_default(in_key)

    def get_input_default(self, in_key: [str, int]):
        return getattr(self, self._input_prop_name(self.inputs[in_key].name))

    def get_param_value(self, name):
        return getattr(self, self._input_prop_name(name))

    def get_nodedef_input(self, in_key: [str, int]):
        return self.nodedef.getActiveInput(self.inputs[in_key].name)

    def get_nodedef_output(self, out_key: [str, int]):
        return self.nodedef.getActiveOutput(self.outputs[out_key].name)

    def set_input_value(self, in_key, value):
        setattr(self, self._input_prop_name(self.inputs[in_key].name), value)

    def set_param_value(self, name, value):
        setattr(self, self._input_prop_name(name), value)

    @classmethod
    def poll(cls, tree):
        return tree.bl_idname == 'ShaderNodeTree'

    def update_ui_folders(self, context):
        for i, nd_input in enumerate(utils.get_nodedef_inputs(self.nodedef, False)):
            f = nd_input.getAttribute('uifolder')
            if f:
                self.inputs[i].hide = not getattr(self, self._folder_prop_name(f))

    def check_ui_folders(self):
        if not self._ui_folders:
            return

        for f in self._ui_folders:
            setattr(self, self._folder_prop_name(f), False)

        for in_key, nd_input in enumerate(utils.get_nodedef_inputs(self.nodedef, False)):
            f = nd_input.getAttribute('uifolder')
            if not f:
                continue

            if self.inputs[in_key].links:
                setattr(self, self._folder_prop_name(f), True)
                continue

            nd_input = self.get_nodedef_input(in_key)
            val = self.get_input_default(in_key)
            nd_val = nd_input.getValue()
            if nd_val is None or utils.is_value_equal(nd_val, val, nd_input.getType()):
                continue

            setattr(self, self._folder_prop_name(f), True)

        self.update_ui_folders(None)

    def create_input(self, nd_input):
        input = self.inputs.new(MxNodeInputSocket.bl_idname, f'in_{len(self.inputs)}')
        input.name = nd_input.getName()
        return input

    def create_output(self, mx_output):
        output = self.outputs.new(MxNodeOutputSocket.bl_idname, f'out_{len(self.outputs)}')
        output.name = mx_output.getName()
        return output


def is_mx_node_valid(node):
    # handle MaterialX 1.37 nodes
    return hasattr(node, 'nodedef')
