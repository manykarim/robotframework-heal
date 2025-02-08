locator_info_dict = {
     'css=h5 + a:text("Source")': {
            "locator": 'css=h5 + a:text("Source")',
            "tagName": "A",
            "innerText": "Source",
            "parentElement.tagName": "SPAN",
            "parentElement.innerText": "React\nSource\nTypeScript + React\nDemo, Source",
            "clickable": True
        },

'css=a:text("Demo")': {
            "locator": 'css=a:text("Demo")',
            "class": "demo-link",
            "tagName": "A",
            "innerText": "Demo",
            "parentElement.tagName": "SPAN",
            "parentElement.innerText": "React\nSource\nTypeScript + React\nDemo, Source",
            "clickable": True
        },

'css=a:text("Demo") + a': {
            "locator": 'css=a:text("Demo") + a',
            "tagName": "A",
            "innerText": "Source",
            "parentElement.tagName": "SPAN",
            "parentElement.innerText": "React\nSource\nTypeScript + React\nDemo, Source",
            "clickable": True
        },

'css=li:has-text("Quick Start")': {
            "locator": 'css=li:has-text("Quick Start")',
            "tagName": "LI",
            "innerText": "Quick Start",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "Quick Start\nAPI Reference\nPhilosophy\nReact Community",
            "clickable": False
        },

'css=a:text("Quick Start")': {
            "locator": 'css=a:text("Quick Start")',
            "tagName": "A",
            "innerText": "Quick Start",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "Quick Start",
            "clickable": True
        },

'css=li:has-text("API Reference")': {
            "locator": 'css=li:has-text("API Reference")',
            "tagName": "LI",
            "innerText": "API Reference",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "Quick Start\nAPI Reference\nPhilosophy\nReact Community",
            "clickable": False
        },

'css=a:text("API Reference")': {
            "locator": 'css=a:text("API Reference")',
            "tagName": "A",
            "innerText": "API Reference",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "API Reference",
            "clickable": True
        },

'css=li:has-text("Philosophy")': {
            "locator": 'css=li:has-text("Philosophy")',
            "tagName": "LI",
            "innerText": "Philosophy",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "Quick Start\nAPI Reference\nPhilosophy\nReact Community",
            "clickable": False
        },

'css=a:text("Philosophy")': {
            "locator": 'css=a:text("Philosophy")',
            "tagName": "A",
            "innerText": "Philosophy",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "Philosophy",
            "clickable": True
        },

'css=li:has-text("React Community")': {
            "locator": 'css=li:has-text("React Community")',
            "tagName": "LI",
            "innerText": "React Community",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "Quick Start\nAPI Reference\nPhilosophy\nReact Community",
            "clickable": False
        },

'css=a:text("React Community")': {
            "locator": 'css=a:text("React Community")',
            "tagName": "A",
            "innerText": "React Community",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "React Community",
            "clickable": True
        },

'css=li:has-text("ReactJS on Stack Overflow")': {
            "locator": 'css=li:has-text("ReactJS on Stack Overflow")',
            "tagName": "LI",
            "innerText": "ReactJS on Stack Overflow",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "ReactJS on Stack Overflow",
            "clickable": True
        },

'css=a:text("ReactJS on Stack Overflow")': {
            "locator": 'css=a:text("ReactJS on Stack Overflow")',
            "tagName": "A",
            "innerText": "ReactJS on Stack Overflow",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "ReactJS on Stack Overflow",
            "clickable": True
        },

"css=input#todo-input": {
            "locator": "css=input#todo-input",
            "id": "todo-input",
            "class": "new-todo",
            "type": "text",
            "placeholder": "What needs to be done?",
            "tagName": "INPUT",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "New Todo Input",
            "nextSibling.tagName": "LABEL",
            "nextSibling.innerText": "New Todo Input",
            "clickable": False
        },

'css=label:text("New Todo Input")': {
            "locator": 'css=label:text("New Todo Input")',
            "class": "visually-hidden",
            "tagName": "LABEL",
            "innerText": "New Todo Input",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "New Todo Input",
            "previousSibling.tagName": "INPUT",
            "clickable": False
        },

"css=input#toggle-all": {
            "locator": "css=input#toggle-all",
            "id": "toggle-all",
            "class": "toggle-all",
            "type": "checkbox",
            "tagName": "INPUT",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Toggle All Input",
            "nextSibling.tagName": "LABEL",
            "nextSibling.innerText": "Toggle All Input",
            "clickable": True
        },

"css=label.toggle-all-label": {
            "locator": "css=label.toggle-all-label",
            "class": "toggle-all-label",
            "tagName": "LABEL",
            "innerText": "Toggle All Input",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Toggle All Input",
            "previousSibling.tagName": "INPUT",
            "clickable": False
        },

'css=li:has-text("Learn Robot Framework")': {
            "locator": 'css=li:has-text("Learn Robot Framework")',
            "tagName": "LI",
            "innerText": "Learn Robot Framework",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "Learn Robot Framework\nWrite Tests",
            "nextSibling.tagName": "LI",
            "nextSibling.innerText": "Write Tests",
            "clickable": False
        },

'css=input[type="checkbox"].toggle:has(+ label:text("Learn Robot Framework"))': {
            "locator": 'css=input[type="checkbox"].toggle:has(+ label:text("Learn Robot Framework"))',
            "class": "toggle",
            "type": "checkbox",
            "tagName": "INPUT",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Learn Robot Framework",
            "nextSibling.tagName": "LABEL",
            "nextSibling.innerText": "Learn Robot Framework",
            "clickable": True
        },

'css=label:text("Learn Robot Framework")': {
            "locator": 'css=label:text("Learn Robot Framework")',
            "tagName": "LABEL",
            "innerText": "Learn Robot Framework",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Learn Robot Framework",
            "previousSibling.tagName": "INPUT",
            "nextSibling.tagName": "BUTTON",
            "clickable": False
        },

'css=li:has-text("Write Tests")': {
            "locator": 'css=li:has-text("Write Tests")',
            "tagName": "LI",
            "innerText": "Write Tests",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": "Learn Robot Framework\nWrite Tests",
            "previousSibling.tagName": "LI",
            "previousSibling.innerText": "Learn Robot Framework",
            "clickable": False
        },

'css=input[type="checkbox"].toggle:has(+ label:text("Write Tests"))': {
            "locator": 'css=input[type="checkbox"].toggle:has(+ label:text("Write Tests"))',
            "class": "toggle",
            "type": "checkbox",
            "tagName": "INPUT",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Write Tests",
            "nextSibling.tagName": "LABEL",
            "nextSibling.innerText": "Write Tests",
            "clickable": True
        },

'css=label:text("Write Tests")': {
            "locator": 'css=label:text("Write Tests")',
            "tagName": "LABEL",
            "innerText": "Write Tests",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Write Tests",
            "previousSibling.tagName": "INPUT",
            "nextSibling.tagName": "BUTTON",
            "clickable": False
        }
    }



from unittest.mock import Mock
from unittest.mock import patch
from SelfHealing.browser_healing import BrowserHealer
from pathlib import Path

testdata_directory = Path(__file__).parent.resolve() / "testdata"
f = open(f"{testdata_directory}/todo_page_with_2_items.html", "r")
source = f.read()

mock_browser = Mock()
mock_browser.get_page_source.return_value = source
mock_browser.evaluate_javascript.return_value = source
mock_browser.get_element_count.return_value = 1
mock_browser.get_element_states.return_value = ["enabled", "visible", "clickable"]

mock_data = Mock()
mock_result = Mock()


def get_variable_value_side_effect(arg):
    if arg == "${OUTPUT_DIR}":
        return "/mock/output/dir"
    return arg


def get_locator_info_side_effect(arg, read_clickable_info=True):
    return locator_info_dict[arg]


@patch('robot.libraries.BuiltIn.BuiltIn.get_variable_value', side_effect=get_variable_value_side_effect)
@patch('robot.libraries.BuiltIn.BuiltIn.replace_variables')
@patch('SelfHealing.browser_healing.BrowserHealer.get_locator_info', side_effect=get_locator_info_side_effect)
def test_get_write_tests_checkbox(mock_get_variable_value, mock_replace_variables, mock_get_locator_info):

	keyword = "Click"
	args = ['input.toggle >> "Write Tests"']
	output_dir = "/mock/output/dir"
	mock_result.args = args
	mock_result.name = keyword
	mock_data.args = args
	mock_data.name = keyword
	mock_result.message = f"waiting for element {args[0]}' to be visible"


	mock_get_variable_value.return_value = output_dir
	mock_replace_variables.return_value = args[0]
	mock_get_locator_info.return_value = None


	healer = BrowserHealer(instance=mock_browser, use_llm_for_locator_proposals=False)
	fixed_locator = healer.get_fixed_locator(data=mock_data, result=mock_result)
	assert fixed_locator == 'css=input[type="checkbox"].toggle:has(+ label:text("Write Tests"))'
     


@patch('robot.libraries.BuiltIn.BuiltIn.get_variable_value', side_effect=get_variable_value_side_effect)
@patch('robot.libraries.BuiltIn.BuiltIn.replace_variables')
@patch('SelfHealing.browser_healing.BrowserHealer.get_locator_info', side_effect=get_locator_info_side_effect)
def test_get_learn_robotframework_checkbox(mock_get_variable_value, mock_replace_variables, mock_get_locator_info):

	keyword = "Click"
	args = ['input.toggle >> "Learn Robot Framework"']
	output_dir = "/mock/output/dir"
	mock_result.args = args
	mock_result.name = keyword
	mock_data.args = args
	mock_data.name = keyword
	mock_result.message = f"waiting for element {args[0]}' to be visible"


	mock_get_variable_value.return_value = output_dir
	mock_replace_variables.return_value = args[0]
	mock_get_locator_info.return_value = None


	healer = BrowserHealer(instance=mock_browser, use_llm_for_locator_proposals=False)
	fixed_locator = healer.get_fixed_locator(data=mock_data, result=mock_result)
	assert fixed_locator == 'css=input[type="checkbox"].toggle:has(+ label:text("Learn Robot Framework"))'