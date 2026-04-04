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

# utils.py — Shared helpers for finding nodes

import bpy


def find_node(tree_name, node_name):
    """Locate a node by tree name and node name."""
    for mat in bpy.data.materials:
        if mat.node_tree and mat.node_tree.name == tree_name:
            if node_name in mat.node_tree.nodes:
                return mat.node_tree.nodes[node_name]
    tree = bpy.data.node_groups.get(tree_name)
    if tree and node_name in tree.nodes:
        return tree.nodes[node_name]
    return None


def get_tree_name(node):
    """Get the node tree name that contains this node."""
    for mat in bpy.data.materials:
        if mat.node_tree and node.name in mat.node_tree.nodes:
            return mat.node_tree.name
    for tree in bpy.data.node_groups:
        if node.name in tree.nodes:
            return tree.name
    return ""


def find_owner_node(prop):
    """Find the StackNode that owns a layer property."""
    ptr = prop.as_pointer()
    for mat in bpy.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if hasattr(node, "layers") and hasattr(node, "rebuild_internals"):
                    for layer in node.layers:
                        if layer.as_pointer() == ptr:
                            return node
    for tree in bpy.data.node_groups:
        for node in tree.nodes:
            if hasattr(node, "layers") and hasattr(node, "rebuild_internals"):
                for layer in node.layers:
                    if layer.as_pointer() == ptr:
                        return node
    return None
