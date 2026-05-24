### Task 5 Implementation Patch: Recursive form extraction

Use this patch for Task 5 Step 3. Before editing, confirm the constructor signatures for `FormElement`, `FormField`, and `InputElement` in `backend/apps/agent/observations/page.py`; if `FormField` already includes `element_id`, set it to the same `input_id` used for the corresponding `InputElement`.

Add `FormElement` and `FormField` to the imports at the top of `builder.py`:

```python
from .page import (
    ButtonElement, CookieInfo, DiscoveredAsset, DiscoveredItems,
    DiscoveredRoute, Elements, FormElement, FormField, InputElement,
    LinkElement, NetworkEntry, ObservationMeta, PageIdentity,
    PageObservation, VisibleTextBlock,
)
```

Modify `_parse_a11y` in `builder.py` to handle `role=form` nodes while preserving the existing standalone parsing behavior:

```python
def _parse_a11y(
    self, children: list[dict]
) -> tuple[Elements, list[VisibleTextBlock]]:
    links: list[LinkElement] = []
    buttons: list[ButtonElement] = []
    inputs: list[InputElement] = []
    forms: list[FormElement] = []
    visible: list[VisibleTextBlock] = []

    for node in children:
        role = node.get("role", "")
        name = node.get("name", "")

        if role == "form":
            form_elem, form_inputs, form_buttons, form_visible = (
                self._parse_form_node(node)
            )
            forms.append(form_elem)
            inputs.extend(form_inputs)
            buttons.extend(form_buttons)
            visible.extend(form_visible)
            continue

        if role == "link":
            href = node.get("url", "") or node.get("value", "")
            links.append(LinkElement(
                element_id=self._next_id("link"),
                href=href,
                text=name,
            ))
        elif role == "button":
            buttons.append(ButtonElement(
                element_id=self._next_id("btn"),
                text=name,
                type=node.get("type", "button"),
            ))
        elif role in ("textbox", "searchbox", "combobox"):
            inputs.append(InputElement(
                element_id=self._next_id("input"),
                name=name,
                type=role,
                placeholder=node.get("placeholder", ""),
            ))
        if name:
            visible.append(VisibleTextBlock(text=name))

    return (
        Elements(links=links, buttons=buttons, forms=forms, inputs=inputs),
        visible,
    )
```

Add `_parse_form_node` with recursive descendant walking so accessible trees that wrap fields in groups, labels, or generic containers still produce form fields:

```python
def _parse_form_node(
    self, node: dict,
) -> tuple[FormElement, list[InputElement], list[ButtonElement], list[VisibleTextBlock]]:
    form_id = self._next_id("form")
    name = node.get("name", "")
    fields: list[FormField] = []
    inputs: list[InputElement] = []
    buttons: list[ButtonElement] = []
    visible: list[VisibleTextBlock] = []

    def walk(descendants: list[dict]) -> None:
        for child in descendants:
            child_role = child.get("role", "")
            child_name = child.get("name", "")

            if child_role in ("textbox", "searchbox", "combobox"):
                input_id = self._next_id("input")
                fields.append(FormField(name=child_name, type=child_role))
                inputs.append(InputElement(
                    element_id=input_id,
                    name=child_name,
                    type=child_role,
                    placeholder=child.get("placeholder", ""),
                ))
            elif child_role == "button":
                buttons.append(ButtonElement(
                    element_id=self._next_id("btn"),
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
```

Acceptance details:

- Form controls must also remain in `elements.inputs` and `elements.buttons`, because `fill_form` uses input IDs and `submit_form` uses button IDs from the element registry.
- Do not require a form to contain fields before creating `FormElement`; empty forms are still useful context for the prompt.
- Do not add form IDs to the driver element registry for submission. `submit_form` dispatch clicks a submit button ID such as `btn_0`, not a `form_0` ID.
