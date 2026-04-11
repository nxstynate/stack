# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 NXSTYNATE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# node.py — StackNode (ShaderNodeCustomGroup)
#
# Persistence strategy:
#   All layer state is stored as individual ID properties on the
#   node_tree datablock (e.g. node_tree["_sl_count"],
#   node_tree["_sl_0_blend"]).  Blender natively serializes ID
#   properties to .blend files — no serialization code needed.
#
#   The CollectionProperty 'layers' is a runtime-only cache rebuilt
#   on demand from the ID properties.
#
#   A lightweight load_post handler restores the runtime cache and
#   rebuilds the internal node chain after file load.  It does NOT
#   serialize or write any data — it only reads the already-persisted
#   ID properties back into the transient CollectionProperty.

import bpy
from bpy.props import CollectionProperty
from bpy.types import ShaderNodeCustomGroup

from .properties import StackLayerProperties
from .utils import get_node_id

DEBUG = True

# Guard flag: suppresses property-update callbacks during bulk operations
# (copy, rebuild_group, _restore_layers) to prevent cascading rebuilds.
_suppress_updates = False


def _dbg(*args):
    if DEBUG:
        print("[Stack]", *args)


# ------------------------------------------------------------------
# ID-property helpers
# ------------------------------------------------------------------

_PREFIX = "_sl_"


def _write_layer_props(nt, idx, name="", blend="MIX", opacity=1.0,
                       enabled=True, collapsed=False):
    """Write a single layer's properties as ID props on *nt*."""
    nt[f"{_PREFIX}{idx}_name"]      = name
    nt[f"{_PREFIX}{idx}_blend"]     = blend
    nt[f"{_PREFIX}{idx}_opacity"]   = opacity
    nt[f"{_PREFIX}{idx}_enabled"]   = int(enabled)
    nt[f"{_PREFIX}{idx}_collapsed"] = int(collapsed)


def _read_layer_props(nt, idx):
    """Read a single layer's properties from ID props on *nt*.
    Returns a dict, or None if the key is missing."""
    key = f"{_PREFIX}{idx}_blend"
    if key not in nt:
        return None
    return {
        "layer_name":  nt.get(f"{_PREFIX}{idx}_name", ""),
        "blend_mode":  nt.get(f"{_PREFIX}{idx}_blend", "MIX"),
        "opacity":     nt.get(f"{_PREFIX}{idx}_opacity", 1.0),
        "enabled":     bool(nt.get(f"{_PREFIX}{idx}_enabled", 1)),
        "collapsed":   bool(nt.get(f"{_PREFIX}{idx}_collapsed", 0)),
    }


def _get_layer_count(nt):
    """Return the persisted layer count."""
    return nt.get(f"{_PREFIX}count", 0)


def _set_layer_count(nt, count):
    """Set the persisted layer count."""
    nt[f"{_PREFIX}count"] = count


def _clear_layer_props(nt, idx):
    """Remove all ID props for layer *idx*."""
    for suffix in ("_name", "_blend", "_opacity", "_enabled", "_collapsed"):
        key = f"{_PREFIX}{idx}{suffix}"
        if key in nt:
            del nt[key]


class StackNode(ShaderNodeCustomGroup):
    """Layer blending node with blend modes, opacity, and masking."""
    bl_idname = "StackNodeType"
    bl_label = "Stack"
    bl_icon = 'NODE_COMPOSITING'
    bl_width_default = 240

    # Runtime-only cache — NOT serialized by Blender.
    # Rebuilt on demand from ID properties on node_tree.
    layers: CollectionProperty(type=StackLayerProperties)

    # ------------------------------------------------------------------
    # Runtime cache management
    # ------------------------------------------------------------------

    def _restore_layers(self):
        """Rebuild the runtime CollectionProperty from ID properties.
        Returns True if layers were restored, False if nothing to do."""
        global _suppress_updates
        nt = self.node_tree
        if nt is None:
            return False

        count = _get_layer_count(nt)
        if count == 0:
            return False

        # Already in sync?
        if len(self.layers) == count:
            d = _read_layer_props(nt, 0)
            if d and self.layers[0].blend_mode == d["blend_mode"]:
                return False

        _suppress_updates = True
        try:
            self.layers.clear()
            for i in range(count):
                d = _read_layer_props(nt, i)
                if d is None:
                    d = {"layer_name": f"Layer {i}", "blend_mode": "MIX",
                         "opacity": 1.0, "enabled": True, "collapsed": False}
                    _write_layer_props(nt, i, **d)
                layer = self.layers.add()
                layer.layer_name  = d["layer_name"]
                layer.blend_mode  = d["blend_mode"]
                layer.opacity     = d["opacity"]
                layer.enabled     = d["enabled"]
                layer.collapsed   = d["collapsed"]
                layer.layer_index = i
            _dbg(f"_restore_layers: rebuilt {count} layers from ID props "
                 f"on {nt.name}")
            return True
        finally:
            _suppress_updates = False

    def ensure_layers(self):
        """Public accessor — guarantees layers are populated."""
        if len(self.layers) == 0 and self.node_tree:
            if _get_layer_count(self.node_tree) > 0:
                self._restore_layers()
                self.rebuild_internals()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self, context):
        _dbg(f"init() called -- id(self)={id(self)}")
        self.node_tree = bpy.data.node_groups.new(
            f".stack_{id(self)}", 'ShaderNodeTree',
        )

        self.node_tree.interface.new_socket(
            name="Color", in_out='OUTPUT', socket_type='NodeSocketColor',
        )

        global _suppress_updates
        _suppress_updates = True
        try:
            layer = self.layers.add()
            layer.layer_index = 0
            layer.layer_name = "Layer 0"
            layer.blend_mode = "MIX"
            layer.opacity = 1.0
            layer.enabled = True
        finally:
            _suppress_updates = False

        _write_layer_props(self.node_tree, 0,
                           name="Layer 0", blend="MIX", opacity=1.0,
                           enabled=True, collapsed=False)
        _set_layer_count(self.node_tree, 1)

        self.add_layer_to_group(0)
        self.rebuild_internals()

    def free(self):
        if self.node_tree:
            bpy.data.node_groups.remove(self.node_tree)

    def copy(self, original):
        """Called when this node is duplicated (Shift+D).

        The node_tree is shared at this point.  We copy it to get an
        independent datablock — the ID properties come along for free.
        Then we rebuild the runtime CollectionProperty from those props.
        """
        global _suppress_updates
        _suppress_updates = True
        try:
            _dbg(f"copy() called -- original.node_tree={original.node_tree}")

            new_tree = original.node_tree.copy()
            self.node_tree = new_tree

            self._restore_layers()

            _dbg(f"copy() done -- layers: {len(self.layers)}, "
                 f"inputs: {len(self.inputs)}")
        finally:
            _suppress_updates = False

    # ------------------------------------------------------------------
    # Socket management (non-destructive)
    # ------------------------------------------------------------------

    def add_layer_to_group(self, index):
        """Append Color + Mask sockets for a new layer at the top."""
        nt = self.node_tree
        prefix = f"Index {index}"

        color_item = nt.interface.new_socket(
            name=f"{prefix} Color", in_out='INPUT',
            socket_type='NodeSocketColor',
        )
        color_item.hide_value = True
        mask_item = nt.interface.new_socket(
            name=f"{prefix} Mask", in_out='INPUT',
            socket_type='NodeSocketFloat',
        )
        mask_item.hide_value = True

        nt.interface.move(color_item, 0)
        nt.interface.move(mask_item, 1)

        for inp in self.inputs:
            if inp.name == f"{prefix} Color":
                inp.default_value = (1.0, 1.0, 1.0, 1.0)
            elif inp.name == f"{prefix} Mask":
                inp.default_value = 1.0

    # ------------------------------------------------------------------
    # Full rebuild (remove / reorder)
    # ------------------------------------------------------------------

    def rebuild_group(self, old_to_new=None):
        """Rebuild the group interface and internals.

        old_to_new: dict or list mapping old layer index -> new index.
                    Use None for deleted layers."""
        nt = self.node_tree
        parent_tree = self.id_data

        # Save socket data
        saved = {}
        for inp in self.inputs:
            link_from = None
            if parent_tree and hasattr(parent_tree, 'links'):
                for link in parent_tree.links:
                    if link.to_node == self and link.to_socket == inp:
                        link_from = link.from_socket
                        break
            try:
                default = tuple(inp.default_value)
            except TypeError:
                default = inp.default_value
            saved[inp.name] = {
                'link_from': link_from,
                'default': default,
            }

        # Build name mapping
        name_map = {}
        if old_to_new is not None:
            if isinstance(old_to_new, list):
                old_to_new = {i: v for i, v in enumerate(old_to_new)}
            for old_i, new_i in old_to_new.items():
                if new_i is None:
                    continue
                name_map[f"Index {old_i} Color"] = f"Index {new_i} Color"
                name_map[f"Index {old_i} Mask"] = f"Index {new_i} Mask"

        # Remove all input sockets
        items_to_remove = []
        for item in nt.interface.items_tree:
            if hasattr(item, 'in_out') and item.in_out == 'INPUT':
                items_to_remove.append(item)
        for item in items_to_remove:
            nt.interface.remove(item)

        # Re-add in reversed order (highest layer first)
        for i in range(len(self.layers) - 1, -1, -1):
            prefix = f"Index {i}"
            color_item = nt.interface.new_socket(
                name=f"{prefix} Color", in_out='INPUT',
                socket_type='NodeSocketColor',
            )
            color_item.hide_value = True
            mask_item = nt.interface.new_socket(
                name=f"{prefix} Mask", in_out='INPUT',
                socket_type='NodeSocketFloat',
            )
            mask_item.hide_value = True

        # Restore defaults and links
        for inp in self.inputs:
            old_name = None
            if name_map:
                for oname, nname in name_map.items():
                    if nname == inp.name:
                        old_name = oname
                        break
            else:
                old_name = inp.name

            if old_name and old_name in saved:
                data = saved[old_name]
                inp.default_value = data['default']
                if data['link_from'] and parent_tree:
                    try:
                        parent_tree.links.new(data['link_from'], inp)
                    except Exception:
                        pass
            elif inp.name.endswith(" Color"):
                inp.default_value = (1.0, 1.0, 1.0, 1.0)
            elif inp.name.endswith(" Mask"):
                inp.default_value = 1.0

        self.rebuild_internals()

    # ------------------------------------------------------------------
    # Rebuild internal blend chain (non-destructive to sockets)
    # ------------------------------------------------------------------

    def rebuild_internals(self):
        """Rebuild the internal mix-node chain without touching sockets."""
        nt = self.node_tree

        g_in = None
        g_out = None
        nodes_to_remove = []
        for n in nt.nodes:
            if n.type == 'GROUP_INPUT':
                g_in = n
            elif n.type == 'GROUP_OUTPUT':
                g_out = n
            else:
                nodes_to_remove.append(n)

        for n in nodes_to_remove:
            nt.nodes.remove(n)
        for link in list(nt.links):
            nt.links.remove(link)

        if g_in is None:
            g_in = nt.nodes.new('NodeGroupInput')
        g_in.location = (-800, 0)

        if g_out is None:
            g_out = nt.nodes.new('NodeGroupOutput')
        g_out.location = (800, 0)

        prev_output = None

        socket_map = {}
        for idx, out in enumerate(g_in.outputs):
            socket_map[out.name] = idx

        for i, layer in enumerate(self.layers):
            color_name = f"Index {i} Color"
            mask_name = f"Index {i} Mask"

            if color_name not in socket_map or mask_name not in socket_map:
                continue

            color_out_idx = socket_map[color_name]
            mask_out_idx = socket_map[mask_name]

            factor_node = nt.nodes.new('ShaderNodeMath')
            factor_node.operation = 'MULTIPLY'
            factor_node.location = (-400 + i * 300, -i * 200 - 100)
            factor_node.label = f"Index {i} Factor"
            factor_node.inputs[0].default_value = (
                layer.opacity if layer.enabled else 0.0
            )
            nt.links.new(g_in.outputs[mask_out_idx], factor_node.inputs[1])

            mix_node = nt.nodes.new('ShaderNodeMix')
            mix_node.data_type = 'RGBA'
            mix_node.clamp_result = True
            mix_node.location = (-200 + i * 300, -i * 200)

            if prev_output is None:
                mix_node.blend_type = 'MIX'
                mix_node.label = f"Index {i} Base"
                nt.links.new(factor_node.outputs[0], mix_node.inputs[0])
                mix_node.inputs[6].default_value = (0, 0, 0, 1)
                nt.links.new(
                    g_in.outputs[color_out_idx], mix_node.inputs[7],
                )
            else:
                mix_node.blend_type = (
                    layer.blend_mode if layer.enabled else 'MIX'
                )
                mix_node.label = f"Index {i} {layer.blend_mode}"
                nt.links.new(factor_node.outputs[0], mix_node.inputs[0])
                nt.links.new(prev_output, mix_node.inputs[6])
                nt.links.new(
                    g_in.outputs[color_out_idx], mix_node.inputs[7],
                )

            prev_output = mix_node.outputs[2]

        if prev_output:
            nt.links.new(prev_output, g_out.inputs[0])
        else:
            rgb_node = nt.nodes.new('ShaderNodeRGB')
            rgb_node.outputs[0].default_value = (0, 0, 0, 1)
            rgb_node.location = (600, 0)
            rgb_node.label = "Black (all disabled)"
            nt.links.new(rgb_node.outputs[0], g_out.inputs[0])

        nt.update_tag()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def draw_buttons(self, context, layout):
        # Lazy restore: if the runtime cache is empty but ID props exist,
        # rebuild the cache and internal nodes now.
        if len(self.layers) == 0 and self.node_tree:
            if _get_layer_count(self.node_tree) > 0:
                _dbg("draw_buttons: lazy restore triggered")
                self._restore_layers()
                self.rebuild_internals()

        nid = get_node_id(self)

        op = layout.operator(
            "stack_node.add_layer", text="Add Layer", icon='ADD',
        )
        op.group_name = nid

        layout.separator()

        num_layers = len(self.layers)
        for draw_i in range(num_layers):
            i = num_layers - 1 - draw_i
            layer = self.layers[i]

            box = layout.box()

            header = box.row(align=True)
            header.prop(
                layer, "collapsed", text="",
                icon='TRIA_RIGHT' if layer.collapsed else 'TRIA_DOWN',
                emboss=False,
            )
            header.prop(
                layer, "enabled", text="",
                icon='CHECKBOX_HLT' if layer.enabled else 'CHECKBOX_DEHLT',
            )
            header.label(text=f"Index {i}")
            header.prop(layer, "layer_name", text="")

            op = header.operator(
                "stack_node.move_layer", text="", icon='TRIA_UP',
            )
            op.group_name = nid
            op.layer_index = i
            op.direction = 'DOWN'

            op = header.operator(
                "stack_node.move_layer", text="", icon='TRIA_DOWN',
            )
            op.group_name = nid
            op.layer_index = i
            op.direction = 'UP'

            if num_layers > 1:
                op = header.operator(
                    "stack_node.remove_layer", text="", icon='X',
                )
                op.group_name = nid
                op.layer_index = i

            if layer.collapsed:
                continue

            if layer.enabled:
                row = box.row(align=True)
                row.prop(layer, "blend_mode", text="")

                row = box.row(align=True)
                row.prop(layer, "opacity", text="Opacity", slider=True)

                color_socket_name = f"Index {i} Color"
                mask_socket_name = f"Index {i} Mask"
                for inp in self.inputs:
                    if inp.name == color_socket_name:
                        box.template_node_socket(
                            color=inp.draw_color(context, self),
                        )
                        row = box.row(align=True)
                        if inp.is_linked:
                            row.label(text=f"  {inp.name} (linked)")
                        else:
                            row.prop(inp, "default_value", text="Color")
                    elif inp.name == mask_socket_name:
                        if inp.is_linked:
                            row = box.row(align=True)
                            row.label(text=f"  {inp.name} (linked)")

    def draw_buttons_ext(self, context, layout):
        self.draw_buttons(context, layout)
