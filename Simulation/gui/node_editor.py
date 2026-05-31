from __future__ import annotations
from typing import Callable
import dearpygui.dearpygui as dpg

from blocks.base import Block, Port
from graph.node_graph import NodeGraph
from graph.connection import Connection


# Colour palette for port types
_PORT_COLORS = {
    "rf":      (100, 180, 255),
    "lo":      (255, 200,  80),
    "if":      (100, 255, 180),
    "coupled": (255, 130, 100),
}


class NodeEditor:
    """
    Wraps a DPG node editor.  Translates DPG link/delink callbacks into
    NodeGraph connect/disconnect calls, and draws block nodes.
    """

    def __init__(self,
                 graph: NodeGraph,
                 on_block_selected: Callable[[Block | None], None],
                 on_graph_changed: Callable[[], None]):
        self._graph = graph
        self._on_selected = on_block_selected
        self._on_changed = on_graph_changed
        self._editor_tag: int | str = 0
        self._handler_reg_tag: int | str = 0
        # Maps DPG node_id → block_id
        self._node_to_block: dict[int, str] = {}
        # Maps (block_id, port_name) → DPG attribute id
        self._port_to_attr: dict[tuple[str, str], int] = {}
        # Reverse: DPG attribute id → (block_id, port_name)
        self._attr_to_port: dict[int, tuple[str, str]] = {}
        self._selected_block_id: str | None = None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, parent: int | str):
        self._editor_tag = dpg.add_node_editor(
            parent=parent,
            callback=self._link_callback,
            delink_callback=self._delink_callback,
            minimap=True,
            minimap_location=dpg.mvNodeMiniMap_Location_BottomRight,
        )

        # Global handlers — mvClickedHandler is NOT supported on mvNode items.
        # Instead, we poll get_selected_nodes() on every mouse click.
        with dpg.handler_registry() as self._handler_reg_tag:
            dpg.add_mouse_click_handler(button=0, callback=self._on_mouse_click)
            dpg.add_key_release_handler(key=dpg.mvKey_Delete,
                                        callback=self._on_delete_key)

    # ------------------------------------------------------------------
    # Drawing blocks
    # ------------------------------------------------------------------

    def draw_block(self, block: Block):
        pos = list(block._dpg_pos)
        with dpg.node(label=block.display_name, parent=self._editor_tag,
                      pos=pos) as node_id:
            block.node_id = node_id
            self._node_to_block[node_id] = block.block_id

            for port in block.ports:
                # Honour block.mirrored: flip which side each pin appears on.
                # Logical direction stays the same for connection validation.
                logical_input = (port.direction == "input")
                if block.mirrored:
                    logical_input = not logical_input
                attr_type = (dpg.mvNode_Attr_Input if logical_input
                             else dpg.mvNode_Attr_Output)
                color = _PORT_COLORS.get(port.port_type, (200, 200, 200))
                with dpg.node_attribute(
                    attribute_type=attr_type,
                    shape=dpg.mvNode_PinShape_CircleFilled,
                ) as attr_id:
                    dpg.add_text(port.name, color=color)
                    port.dpg_attr_id = attr_id
                    key = (block.block_id, port.name)
                    self._port_to_attr[key] = attr_id
                    self._attr_to_port[attr_id] = key

    def draw_all_blocks(self):
        for block in self._graph.blocks.values():
            self.draw_block(block)

    def draw_connection(self, conn: Connection):
        src_key = (conn.src_block_id, conn.src_port_name)
        dst_key = (conn.dst_block_id, conn.dst_port_name)
        src_attr = self._port_to_attr.get(src_key)
        dst_attr = self._port_to_attr.get(dst_key)
        if src_attr is None or dst_attr is None:
            return
        link_id = dpg.add_node_link(src_attr, dst_attr, parent=self._editor_tag)
        conn.dpg_link_id = link_id

    def draw_all_connections(self):
        for conn in self._graph.connections:
            self.draw_connection(conn)

    def refresh_all(self):
        """Clear and redraw everything from the graph (used after load)."""
        dpg.delete_item(self._editor_tag, children_only=True)
        self._node_to_block.clear()
        self._port_to_attr.clear()
        self._attr_to_port.clear()
        self._selected_block_id = None
        self.draw_all_blocks()
        self.draw_all_connections()

    # ------------------------------------------------------------------
    # Adding / removing blocks interactively
    # ------------------------------------------------------------------

    def add_block(self, block: Block, pos: tuple[int, int] | None = None):
        if pos is None:
            existing = len(self._graph.blocks)
            pos = (80 + (existing % 5) * 180, 80 + (existing // 5) * 160)
        block._dpg_pos = pos
        self._graph.add_block(block)
        self.draw_block(block)

    def _delete_node_links(self, block_id: str):
        """Delete all DPG link items connected to a block before removing its node."""
        for conn in self._graph.connections:
            if (conn.src_block_id == block_id or conn.dst_block_id == block_id):
                if conn.dpg_link_id and dpg.does_item_exist(conn.dpg_link_id):
                    dpg.delete_item(conn.dpg_link_id)
                    conn.dpg_link_id = 0

    def remove_selected_block(self):
        if self._selected_block_id is None:
            return
        bid = self._selected_block_id
        block = self._graph.blocks.get(bid)
        self._delete_node_links(bid)
        if block and dpg.does_item_exist(block.node_id):
            dpg.delete_item(block.node_id)
        self._graph.remove_block(bid)
        self._node_to_block = {k: v for k, v in self._node_to_block.items()
                                if v != bid}
        dead_attrs = [k for k, v in self._attr_to_port.items() if v[0] == bid]
        for k in dead_attrs:
            pk = self._attr_to_port.pop(k)
            self._port_to_attr.pop(pk, None)
        self._selected_block_id = None
        self._on_selected(None)
        self._on_changed()

    def redraw_block(self, block_id: str):
        """Toggle-mirror helper: delete node, redraw with flipped pins, reconnect."""
        block = self._graph.blocks.get(block_id)
        if block is None:
            return
        related = [c for c in self._graph.connections
                   if c.src_block_id == block_id or c.dst_block_id == block_id]
        # Must delete links before the node — DPG does not auto-clean dangling links
        self._delete_node_links(block_id)
        if dpg.does_item_exist(block.node_id):
            dpg.delete_item(block.node_id)
        self._node_to_block = {k: v for k, v in self._node_to_block.items()
                                if v != block_id}
        dead = [k for k, v in self._attr_to_port.items() if v[0] == block_id]
        for k in dead:
            pk = self._attr_to_port.pop(k)
            self._port_to_attr.pop(pk, None)
        self.draw_block(block)
        for conn in related:
            self.draw_connection(conn)

    # ------------------------------------------------------------------
    # DPG callbacks
    # ------------------------------------------------------------------

    def _on_mouse_click(self, sender, app_data):
        """Fires on every left-click; check which node is selected in the editor."""
        if not dpg.does_item_exist(self._editor_tag):
            return
        selected = dpg.get_selected_nodes(self._editor_tag)
        if selected:
            node_id = selected[-1]
            block_id = self._node_to_block.get(node_id)
            if block_id and block_id != self._selected_block_id:
                self._selected_block_id = block_id
                self._on_selected(self._graph.blocks.get(block_id))
        # Don't deselect on clicking elsewhere — the property panel stays open

    def _on_delete_key(self, sender, app_data):
        self.remove_selected_block()

    def _link_callback(self, sender, app_data):
        """Called when user drags a wire between two pins.

        DPG passes the two connected attribute IDs in drag order, but for
        mirrored blocks the DPG attribute type is flipped (logical output
        becomes DPG Input so the pin appears on the left side).  We therefore
        normalise to (logical-output → logical-input) using the Port.direction
        field, regardless of which end the user started dragging from.
        """
        attr_a_id, attr_b_id = app_data
        info_a = self._attr_to_port.get(attr_a_id)
        info_b = self._attr_to_port.get(attr_b_id)
        if info_a is None or info_b is None:
            return

        block_a_id, port_a_name = info_a
        block_b_id, port_b_name = info_b

        block_a = self._graph.blocks.get(block_a_id)
        block_b = self._graph.blocks.get(block_b_id)
        if block_a is None or block_b is None:
            return
        port_a_obj = block_a.get_port(port_a_name)
        port_b_obj = block_b.get_port(port_b_name)
        if port_a_obj is None or port_b_obj is None:
            return

        # Normalise to (src=logical-output, dst=logical-input), swapping if
        # the user dragged from the input end (common with mirrored blocks).
        if port_a_obj.direction == "output" and port_b_obj.direction == "input":
            src_block_id, src_port, src_attr = block_a_id, port_a_name, attr_a_id
            dst_block_id, dst_port, dst_attr = block_b_id, port_b_name, attr_b_id
        elif port_a_obj.direction == "input" and port_b_obj.direction == "output":
            src_block_id, src_port, src_attr = block_b_id, port_b_name, attr_b_id
            dst_block_id, dst_port, dst_attr = block_a_id, port_a_name, attr_a_id
        else:
            return  # input↔input or output↔output — invalid

        conn = self._graph.connect(src_block_id, src_port, dst_block_id, dst_port)
        link_id = dpg.add_node_link(src_attr, dst_attr, parent=self._editor_tag)
        conn.dpg_link_id = link_id
        self._on_changed()

    def _delink_callback(self, sender, app_data):
        """Called when user deletes a wire (right-click on link → Delete)."""
        link_id = app_data
        self._graph.disconnect_by_dpg_link(link_id)
        dpg.delete_item(link_id)
        self._on_changed()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_selected_block(self) -> Block | None:
        if self._selected_block_id:
            return self._graph.blocks.get(self._selected_block_id)
        return None

    def update_node_positions(self):
        """Sync DPG node positions back to block._dpg_pos (call before save)."""
        for node_id, block_id in self._node_to_block.items():
            block = self._graph.blocks.get(block_id)
            if block and dpg.does_item_exist(node_id):
                try:
                    pos = dpg.get_item_pos(node_id)
                    if pos:
                        block._dpg_pos = tuple(pos)
                except Exception:
                    pass
