"""
A Listener Library for Self Healing Browser.
Connects to the instance of the Browser Library.
Starts interaction with end_keyword and end_test listeners.
"""

from robot.api import logger
import re
from .browser_healing import BrowserHealer
from .appium_healing import AppiumHealer
from .visual_healing import VisualHealer
from robot.libraries.BuiltIn import BuiltIn
from .utils import extract_json_objects
from .locator_db import LocatorDetailsDB

try:
    from Browser.utils.data_types import ScreenshotReturnType
except ImportError:
    _has_browser = False
else:
    _has_browser = True


duplicate_test_pattern = re.compile(
    r"Multiple .*? with name '(?P<test>.*?)' executed in.*? suite '(?P<suite>.*?)'."
)

class SelfHealing:
    ROBOT_LIBRARY_SCOPE = 'SUITE'
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, fix="realtime", collect_locator_info = False, use_locator_db = False, use_llm_for_locator_proposals = True, heal_assertions = False, locator_db_file = "locator_db.json"):
        self.ROBOT_LIBRARY_LISTENER = self
        self.fixed_locators = {}
        self.updated_locators = {}
        self.greedy_fix = True
        self.collect_locator_info = collect_locator_info
        self.use_locator_db = use_locator_db
        self.use_llm_for_locator_proposals = use_llm_for_locator_proposals
        self.heal_assertions = heal_assertions
        if fix == "realtime":
            self.fix_realtime = True
            self.fix_retry = False
        else:
            self.fix_realtime = False
            self.fix_retry = True
        self.locator_info = {}
        try:
            self.locator_db = LocatorDetailsDB(locator_db_file).db
        except:
            pass



    def _start_library_keyword(self, data, implementation, result):
        if self.greedy_fix and data.args:
            data.args = list(data.args)
            if result.owner == 'Browser':
                if self.fixed_locators.get(data.args[0]):
                    healer = BrowserHealer(implementation.owner.instance, use_llm_for_locator_proposals = self.use_llm_for_locator_proposals)            
                    if healer.get_element_count_for_locator(data.args[0]) == 0:
                        broken_locator = data.args[0]
                        fixed_locator = self.fixed_locators.get(data.args[0])
                        if healer.get_element_count_for_locator(fixed_locator) != 0:
                            data.args[0] = fixed_locator
                            result.args = data.args
                            logger.info(f"Updated Keyword Argument with new selector {data.args[0]}", also_console=True)
                            self.updated_locators[f"{result.id}"] = {"keyword_name": result.name, "lineno": data.lineno, "source": data.source, "fixed_locator": fixed_locator, "test_name": BuiltIn().replace_variables("${TEST NAME}"), "suite_name": BuiltIn().replace_variables("${SUITE NAME}"), "broken_locator": broken_locator} 
        if result.owner == 'Browser' and self.collect_locator_info:
            self.locator_info = {}
            healer = BrowserHealer(implementation.owner.instance, use_llm_for_locator_proposals = self.use_llm_for_locator_proposals)
            if healer.has_locator(result):
                locator = BuiltIn().replace_variables(str(data.args[0]))
                self.locator_info = healer.get_locator_info(locator)

    def _end_library_keyword(self, data, implementation, result):
        # Check if Keyword belongs to Browser Library
        if result.owner == 'Browser' and result.failed and data.parent.name != "Run Keyword And Return Status":
            browser = implementation.owner.instance
            logger.info(f"Keyword '{result.full_name}' with arguments '{BuiltIn().replace_variables(data.args)}' used on line {data.lineno} failed.", also_console=True)
            healer = BrowserHealer(implementation.owner.instance, use_llm_for_locator_proposals = self.use_llm_for_locator_proposals)
            if healer.is_locator_broken(result.message):
                broken_locator = BuiltIn().replace_variables(data.args[0])
                fixed_locator = healer.get_fixed_locator(data, result)
                if self.fix_realtime:
                    if fixed_locator:
                        try:
                            return_value = healer.rerun_keyword(data, fixed_locator)
                            if return_value and result.assign:
                                BuiltIn().set_local_variable(result.assign[0], return_value)
                            self.fixed_locators[broken_locator] = fixed_locator
                            self.updated_locators[f"{result.id}"] = {"keyword_name": result.name, "lineno": data.lineno, "source": data.source, "fixed_locator": fixed_locator, "test_name": BuiltIn().replace_variables("${TEST NAME}"), "suite_name": BuiltIn().replace_variables("${SUITE NAME}"), "broken_locator": broken_locator} 
                            result.status = "PASS"
                            return return_value
                        except:
                            raise
            elif healer.is_element_not_ready(result.message):
                logger.info(f"SelfHealing: Element was not ready")
                if healer.is_modal_dialog_open():
                    healer.close_modal_dialog()
                    try:
                        # Rerun original step again
                        return_value = healer.rerun_keyword(data)
                        if return_value and result.assign:
                            BuiltIn().set_local_variable(result.assign[0], return_value)
                        result.status = "PASS"
                        return return_value
                    except:
                        raise
                elif healer.is_page_loading:
                    logger.info(f"Element was not ready as Page was readyState was not Complete.")
                    healer.wait_until_page_is_ready()
                    try:
                        # Rerun original step again
                        return_value = healer.rerun_keyword(data)
                        if return_value and result.assign:
                            BuiltIn().set_local_variable(result.assign[0], return_value)
                        result.status = "PASS"
                        return return_value
                    except:
                        raise
                else:
                    try:
                        import pyautogui
                        pyautogui.press('esc')
                        try:
                            # Rerun original step again
                            return_value = healer.rerun_keyword(data)
                            if return_value and result.assign:
                                BuiltIn().set_local_variable(result.assign[0], return_value)
                            result.status = "PASS"
                            return return_value
                        except:
                            raise
                    except:
                        logger.error("Cannot use pyautogui in HEADLESS mode")
            elif self.heal_assertions:
                screenshot_base64 = browser.take_screenshot(fullPage=True, log_screenshot=False, return_as=ScreenshotReturnType.base64)
                visual_healer = VisualHealer(instance=implementation.owner.instance)
                explanation = visual_healer.get_error_explanation(data, result, screenshot_base64)
                logger.info(explanation,  also_console=True)
                if "*Adjustment*" in explanation:
                    kw_list =  list(extract_json_objects(explanation))
                    if len(kw_list) > 0:
                        new_kw = kw_list[0]["keyword_name"]
                        if "args" in kw_list[0]:
                            new_args = list(kw_list[0]["args"])
                        elif "arguments" in kw_list[0]:
                            new_args = list(kw_list[0]["arguments"])
                        else:
                            new_args = []
                        new_args = [x.strip() for x in new_args]
                        try:
                            value = BuiltIn().run_keyword(new_kw, *new_args)                    
                            result.status = "PASS"
                            return value
                        except Exception as e:
                            logger.info(e)
                            result.status = "FAIL"                            
        if result.owner == 'Browser' and result.passed and self.collect_locator_info and self.locator_info:
                self._store_successful_locator_info(self.locator_info)
        if result.owner == 'AppiumLibrary' and result.failed:
            appium = implementation.owner.instance
            logger.info(f"Keyword '{result.full_name}' with arguments '{BuiltIn().replace_variables(data.args)}' used on line {data.lineno} failed.", also_console=True)
            healer = AppiumHealer(implementation.owner.instance, use_llm_for_locator_proposals = self.use_llm_for_locator_proposals)
            if healer.is_modal_dialog_open():
                logger.info(f"Modal dialog was open", also_console=True)
                healer.close_modal_dialog()
                # Rerun original step again
                BuiltIn().run_keyword("AppiumLibrary.Wait Until Element Is Visible", data.args[0])
                status = healer.rerun_keyword(data)
                result.status = status          
            elif healer.is_locator_broken(result.message):
                broken_locator = BuiltIn().replace_variables(data.args[0])
                fixed_locator = healer.get_fixed_locator(data, result)
                if self.fix_realtime:
                    if fixed_locator:
                        if healer.is_element_visible_with_swiping(fixed_locator):
                            status = healer.rerun_keyword(data, fixed_locator)
                            result.status = status
                            if result.status == "PASS":
                                self.fixed_locators[broken_locator] = fixed_locator
                                self.updated_locators[f"{result.id}"] = {"keyword_name": result.name, "lineno": data.lineno, "source": data.source, "fixed_locator": fixed_locator, "test_name": BuiltIn().replace_variables("${TEST NAME}"), "suite_name": BuiltIn().replace_variables("${SUITE NAME}"), "broken_locator": broken_locator} 


    def _close(self):
        # Write fixed locators to file
        # f = open(str(path.parent) + "\\" + 'fixed_selectors.csv', 'w')
        # f.write(f"File;LineNo;Fixed Locator;\n")
        
        # for key in self.updated_locators:
        #     f.write(f"{self.updated_locators[key].get('source')};{self.updated_locators[key].get('lineno')};{self.updated_locators[key].get('fixed_locator')};\n")
        # f.close()


        from jinja2 import Environment, FileSystemLoader
        import os

        output_path = BuiltIn().replace_variables("${OUTPUT DIR}")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Set up the Jinja2 environment
        env = Environment(loader=FileSystemLoader(current_dir))
        template = env.get_template('template.html')

        data = [value for key, value in self.updated_locators.items()]
        # Render the template with data
        output = template.render(data=data)

        # Save the rendered HTML to a file
        with open(os.path.join(output_path, "fixed_locators.html"), 'w') as f:
            f.write(output)

    def _store_successful_locator_info(self, locator_info):
        self.locator_db.insert(locator_info)