from __future__ import annotations

from typing import Callable

from .page import ButtonElement, FormElement, FormField, InputElement, VisibleTextBlock

_INPUT_ROLES = ("textbox", "searchbox", "combobox")


def parse_form_node(
    node: dict,
    next_id: Callable[[str], str],
) -> tuple[FormElement, list[InputElement], list[ButtonElement], list[VisibleTextBlock]]:
    """Recursively extract fields, inputs, and buttons from a role=form node.

    Args:
        node: Accessibility snapshot node with role=form.
        next_id: Callable that returns the next unique element ID for a prefix.

    Returns:
        A tuple of (FormElement, flat InputElement list, flat ButtonElement list,
        VisibleTextBlock list).  Inputs and buttons are returned flat so the
        caller can merge them into the page-level element registries.
    """
    form_id = next_id("form")
    name = node.get("name", "")
    fields: list[FormField] = []
    inputs: list[InputElement] = []
    buttons: list[ButtonElement] = []
    visible: list[VisibleTextBlock] = []

    def walk(descendants: list[dict]) -> None:
        for child in descendants:
            child_role = child.get("role", "")
            child_name = child.get("name", "")
            if child_role in _INPUT_ROLES:
                input_id = next_id("input")
                fields.append(FormField(name=child_name, type=child_role))
                inputs.append(InputElement(
                    element_id=input_id,
                    name=child_name,
                    type=child_role,
                    placeholder=child.get("placeholder", ""),
                ))
            elif child_role == "button":
                buttons.append(ButtonElement(
                    element_id=next_id("btn"),
                    text=child_name,
                    type=child.get("type", "button"),
                ))
            if child_name:
                visible.append(VisibleTextBlock(text=child_name))
            walk(child.get("children", []))

    walk(node.get("children", []))
    form_elem = FormElement(
        element_id=form_id,
        action=node.get("url", "") or node.get("value", ""),
        method=node.get("method", "POST"),
        fields=fields,
    )
    if name:
        visible.insert(0, VisibleTextBlock(text=name))
    return form_elem, inputs, buttons, visible
