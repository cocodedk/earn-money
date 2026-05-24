# File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/apps/agent/actions/schemas.py` | Modify | Add `FillFormAction`, `SubmitFormAction` dataclasses + register in `_ACTION_MAP` |
| `backend/apps/agent/actions/matrix.py` | Modify | Allow `fill_form` and `submit_form` in the phases that can use form actions |
| `backend/apps/agent/browser/driver.py` | Modify | Add `fill(element_id, value)` method |
| `backend/apps/agent/controller_dispatch.py` | Modify | Add dispatch branches for `fill_form`/`submit_form` and the verify-phase entry gate |
| `backend/apps/agent/budget.py` | Modify if present | Register `form_fills` and `form_submits` if the budget implementation declares allowed counters |
| `backend/apps/agent/mission_profiles.py` | Modify | Add `form_fills` and `form_submits` budget keys; add `juice_shop_login` profile with a verify phase budget |
| `backend/apps/agent/observations/builder.py` | Modify | Add form grouping from a11y snapshot |
| `backend/apps/agent/observations/page.py` | No change | `FormElement`, `FormField`, `InputElement` already exist |
| `backend/apps/agent/llm/prompts.py` | Modify | Ensure the `submit_form` schema example uses a button element ID such as `btn_0` |
| `backend/apps/agent/tests/test_actions.py` | Modify | Add tests for FillFormAction, SubmitFormAction |
| `backend/apps/agent/tests/test_driver.py` | Modify | Add tests for driver.fill() |
| `backend/apps/agent/tests/test_controller.py` | Modify | Add tests for fill_form/submit_form dispatch + verify phase |
| `backend/apps/agent/tests/test_builder.py` | Modify | Add tests for form grouping |
| `backend/apps/agent/tests/test_mission_profiles.py` | Modify | Add tests for new profile + budget keys |
| `backend/apps/agent/tests/test_prompts.py` | Modify | Add tests for action matrix prompt inclusion and the submit button-ID example |
