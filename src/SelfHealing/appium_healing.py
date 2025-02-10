from robot.libraries.BuiltIn import BuiltIn
from robot.api import logger
import json
from bs4 import BeautifulSoup
import re
from uuid import uuid4
from .llm_client import LLM_TEXT_MODEL, completion
from .utils import extract_json_objects, filter_dict, compare_dict, xpath_to_browser, get_xpath_selector, get_simplified_dom_tree, generate_unique_css_selector, generate_unique_xpath_selector, is_leaf_or_lowest, has_parent_dialog_without_open, has_child_dialog_without_open, has_direct_text, is_headline, is_div_in_li, is_p, filter_locator_list_with_fuzz
from .locator_db import LocatorDetailsDB
from tinydb import Query
from cssify import cssify
import pprint
from time import sleep
from lxml import etree
try:
    from appium.webdriver.common.appiumby import AppiumBy
except ImportError:
    _has_appium = False
else:
    _has_appium = True


class AppiumHealer:
    _instance = None
    locators = {}
    dom_tree = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AppiumHealer, cls).__new__(cls)
        return cls._instance

    def __init__(self, instance=None, **kwargs):
        if instance:
            self.appium=instance._current_application()
        self.use_locator_db = kwargs.get('use_locator_db', False)
        self.use_llm_for_locator_proposals = kwargs.get('use_llm_for_locator_proposals', True)
        self.parse_full_page = kwargs.get('parse_full_page', False)


    def set_appium_instance(self, instance):
        self.appium = instance._current_application()

    def is_locator_broken(self, message) -> bool:
         return ('did not match any elements' in message)
    
    def is_element_not_ready(self, message) -> bool:
        pass

    def is_modal_dialog_open(self) -> bool:
        if self.is_permission_popup_open():
            return True
        return False

    def close_modal_dialog(self) -> bool:
        if self.is_permission_popup_open():
            self.confirm_permission_popup()
        pass

    def is_permission_popup_open(self) -> bool:
        try:
            if len(self.appium.find_elements(AppiumBy.XPATH, "//*[contains(@resource-id,'dialog_container')]")) == 1:
                return True
        except:
            pass
        return False

    def confirm_permission_popup(self) -> bool:

        buttons = ['ALLOW', 'TURN', 'CONFIRM', 'OK', 'OKAY']
        for button in buttons:
            try:
                elem = self.appium.find_element(AppiumBy.XPATH, f"//*[contains(@text, '{button}')] ")
                elem.click()
                break
            except:
                pass
        logger.error(f"Popup Dialog could not be closed")

        
    def get_fixed_locator(self, data, result) -> str:
        output_dir = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        testsuite = BuiltIn().get_variable_value('${SUITE NAME}')
        
#        source = self.appium.page_source
        if self.parse_full_page:
            soup_list = self.get_full_dom()
        else:
            soup_list = self.get_current_dom()

        failed_locator = BuiltIn().replace_variables(str(result.args[0]))
        fixed_locator_list = []
        fixed_locators_with_info = []
        index = 0

        for soup in soup_list:
            if self.use_llm_for_locator_proposals:
                fixed_locator_list += self.get_locator_proposals_from_llm(data, result, str(soup.hierarchy))
            else:
                fixed_locator_list += self.get_locator_proposals_from_parser(data, result, str(soup.hierarchy))
        
            

            print(f"{fixed_locator_list}")

            existing_locators = {d['fixed_locator'] for d in fixed_locators_with_info}
            
            fixed_locator_list = [item for item in fixed_locator_list if item not in existing_locators]
            for retry_selector in fixed_locator_list:
                try:
                    retry_locator_info = self.get_locator_info(str(soup.hierarchy), retry_selector)
                    fixed_locators_with_info.append({"index": int(index), "fixed_locator": retry_selector, "additional_info": retry_locator_info})
                except:
                    pass
                index += 1

        print(f"{fixed_locators_with_info}")


        logger.info(f"Pre-filtered locator candidates with info: {pprint.pformat(fixed_locators_with_info)}", also_console=False)

        messages = []

        messages.append({
            'role': 'system',
            'content': (
                "You are a xpath locator self-healing tool for Robot Framework.\n"
                "You will select exactly one fixed_locator and index from a list of Locators Proposals.\n"
                "Always return the unchanged fixed_locator.\n"
                'Respond using the following json schema: {"index": "index of fixed_locator", "fixed_locator": "selected fixed_locator"}'
            )

            })

        messages.append({
            'role': 'user',
            'content': (
                        f"Broken Locator : `{failed_locator}`\n"
                        f"Keyword : `{data.name}`\n"

                        f"Analyse the `additional_info` for each `fixed_locator` to select the `fixed_locator` which most likely matches to failed_locator=`{failed_locator}`.\n" 

                        f"** Locators Proposals **\n"
                        f"```{json.dumps(fixed_locators_with_info)}```"
                        )

        })

        response = completion(
            model = LLM_TEXT_MODEL,
            messages = messages,
            temperature = 0.1,
            response_format =  { "type": "json_object" }
        )
        solution_text = response['choices'][0]['message']['content']

        logger.info(f"2nd LLM response with sorted candidates: {solution_text}", also_console=False)

        sorted_retry_locators = list(extract_json_objects(solution_text))[0]
        if isinstance(sorted_retry_locators, dict):
            if 'index' in sorted_retry_locators:
                retry_locator = next(item["fixed_locator"] for item in fixed_locators_with_info if int(item['index']) == int(sorted_retry_locators['index']))
                return retry_locator
            elif 'fixed_locators' in sorted_retry_locators:
                retry_locator = sorted_retry_locators["fixed_locators"]
            elif 'fixed_locator' in sorted_retry_locators:
                retry_locator = sorted_retry_locators["fixed_locator"]
            
            if isinstance(retry_locator, list):
                retry_locator = retry_locator[0]
            if isinstance(retry_locator, str):
                return  retry_locator
            
        return None

    def rerun_keyword(self, data, fixed_locator = None) -> str:
        if fixed_locator:
            data.args = list(data.args)
            data.args[0] = fixed_locator
        try:
            logger.info(f"Re-trying Keyword '{data.name}' with arguments '{data.args}'.", also_console=True)
            BuiltIn().run_keyword(data.name, *data.args)
            BuiltIn().run_keyword("Capture Page Screenshot")
            return "PASS"
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            return "FAIL"


    def is_scrollable(self):
        dom_list = []

        driver = self.appium
        initial_dom = driver.page_source
        
        # Perform a swipe to check if more elements are available
        driver.swipe(500, 1500, 500, 500, 1000)
        sleep(1)
        new_dom = driver.page_source
        
        return new_dom != initial_dom

    def get_locator_info(self, source, locator):
        tree = etree.XML(str(source))
        # Use the XPath to find matching elements
        element = tree.xpath(locator)[0]
        locator_info = {}
        locator_info["locator"] = locator
        attribute_list = ["package", "content-desc", "index", "hint", "bounds", "text", "clickable", "checkable", "scrollable", "class"]
        
        for attribute in attribute_list:
            try:
                value = element.get(attribute)
            except:
                value = None
            if value:
                locator_info[attribute]=value
        testsuite = BuiltIn().get_variable_value("${SUITE NAME}")
        locator_info["testsuite"] = testsuite
        return locator_info

    def get_current_dom(self):
        dom_list = []
        driver = self.appium
        initial_dom = driver.page_source
        dom_list.append(BeautifulSoup(initial_dom, 'xml'))
        return dom_list

    def get_full_dom(self):
        dom_list = []
        locators = []
        driver = self.appium

        initial_dom = driver.page_source
        dom_list.append(BeautifulSoup(initial_dom, 'xml'))

        deviceSize = driver.get_window_size()
        screenWidth = deviceSize['width']
        screenHeight = deviceSize['height']
        startx = screenWidth/2
        endx = screenWidth/2
        starty = screenHeight*8/9
        endy = screenHeight/9

        # Perform a swipe to check if more elements are available
        # driver.swipe(500, 1500, 500, 500, 1000)
        driver.swipe(startx, starty, endx, endy, 1000)
        new_dom = driver.page_source
        
        # If the DOM changes after the swipe, continue swiping
        while new_dom != initial_dom:
            dom_list.append(BeautifulSoup(new_dom, 'xml'))
            initial_dom = new_dom
            driver.swipe(startx, starty, endx, endy, 1000)
            new_dom = driver.page_source

        # Swipe to top again

        startx2 = screenWidth/2
        endx2 = screenWidth/2
        starty2 = screenHeight*2/9
        endy2 = screenHeight*8/9

        driver.swipe(startx2, starty2, endx2, endy2, 1000)
        new_dom = driver.page_source
        while new_dom != initial_dom:
            initial_dom = new_dom
            driver.swipe(startx2, starty2, endx2, endy2, 1000)
            new_dom = driver.page_source

        #full_dom_tree = self.merge_dom_trees(dom_list)
    
        return dom_list

    def is_element_visible_with_swiping(self, locator):

        driver = self.appium
        if len(self.appium.find_elements(AppiumBy.XPATH, locator)) == 1:
            return True

        initial_dom = driver.page_source

        deviceSize = driver.get_window_size()
        screenWidth = deviceSize['width']
        screenHeight = deviceSize['height']
        startx = screenWidth/2
        endx = screenWidth/2
        starty = screenHeight*8/9
        endy = screenHeight/9

        driver.swipe(startx, starty, endx, endy, 1000)
        new_dom = driver.page_source

        while new_dom != initial_dom:
            if len(self.appium.find_elements(AppiumBy.XPATH, locator)) == 1:
                return True
            initial_dom = new_dom
            driver.swipe(startx, starty, endx, endy, 1000)
            sleep(1)
            new_dom = driver.page_source
        
        startx2 = screenWidth/2
        endx2 = screenWidth/2
        starty2 = screenHeight*2/9
        endy2 = screenHeight*8/9

        driver.swipe(startx2, starty2, endx2, endy2, 1000)
        new_dom = driver.page_source
        while new_dom != initial_dom:
            initial_dom = new_dom
            driver.swipe(startx2, starty2, endx2, endy2, 1000)
            new_dom = driver.page_source

        return False
        

    def merge_dom_trees(self, dom_list):
        # Parse the first DOM tree
        full_tree = BeautifulSoup(dom_list[0], 'xml')
        
        def add_elements(soup, elements):
            for element in elements:
                if not any(existing_element == element for existing_element in soup.find_all(element.name)):
                    soup.append(element)
        
        for dom in dom_list[1:]:
            new_tree = BeautifulSoup(dom, 'xml')
            add_elements(full_tree, new_tree.find_all())
        
        return full_tree

    def get_locator_proposals_from_llm(self, data, result, source):

        failed_locator = BuiltIn().replace_variables(str(result.args[0]))

        schema = {
            "fixed_locator": "The fixed xpath locator."
        }

        locator_has_been_fixed = False
        retry_count = 0
        error_message = result.message

        prompt_content = {
                'error_message': error_message,
                'failed_locator': failed_locator,
                'keyword': data.name,
                'page_source': source
                }

        messages = []
        
        android_widgets = [
            'android.widget.Button',
            'android.widget.EditText',
            'android.widget.TextView',
            'android.widget.ImageView',
            'android.widget.CheckBox',
            'android.widget.RadioButton',
            'android.widget.ToggleButton',
            'android.widget.ProgressBar',
            'android.widget.SeekBar',
            'android.widget.Spinner',
            # 'android.widget.ListView',
            # 'android.widget.GridView',
            # 'android.widget.ScrollView',
            'android.widget.Switch',
            'android.widget.RatingBar'
        ]

        SYS_PROMPT= (
                "You are a xpath locator self-healing tool."
                "You will provide a fixed_locator for a failed_locator."
                "The User prompt will contain data for 'error_message' , 'failed_locator', 'keyword' and 'page_source'."
                "You will analyze the `page_source` and the `error_message` and find the eight best alternative fixed_locators for the failed_locator."
                f"Only elements of class {android_widgets} are candidates"
                "Keywords to fill or enter text  are always related to `android.widget.EditText` elements."
                "Keywords like `Click` are often  related to 'android.widget.Button','android.widget.CheckBox', 'android.widget.ToggleButton', 'android.widget.RadioButton' or 'android.widget.TextView' elements."
                'Respond using the following json schema: {"fixed_locators": ["locator1", "locator2", "locator3", ... ]}.'
                'Example: {"fixed_locators": ["css=input[id=\'my_id\']", "//*[contains(@text,\'Login\')]", "//*[@resource-id=\'android:id/content\')", "//android.widget.EditText[@content-desc=\'password\')"}'
            )

        messages.append({
            'role': 'system',
            'content': SYS_PROMPT
            })

        messages.append({
            'role': 'user',
            'content': json.dumps(prompt_content),
        })

        
        while not locator_has_been_fixed:
            retry_count += 1
            if retry_count > 3:
                break          

            llm_max_retries = 3
            llm_attempts = 0
            llm_success = False

            while llm_attempts < llm_max_retries and not llm_success:
                try:
                    response = completion(
                        model = LLM_TEXT_MODEL,
                        messages = messages,
                        temperature = 0.1,
                        response_format =  { "type": "json_object" }
                    )

                    llm_success = True
                except Exception as e:
                    llm_attempts += 1
                    print(f"Attempt {llm_attempts} failed: {e}")

            solution_text = response['choices'][0]['message']['content']
            
            # messages.append({
            #     "role": "assistant",
            #     "content": solution_text
            # })

            # f = open(output_dir + "\\" + id + '_solution.txt', 'w')
            # f.write(solution_text)
            # f.close()

            logger.info(f"1st LLM response: {pprint.pformat(solution_text)}\n", also_console=False)

            try:
                fixed_locator_dict = list(extract_json_objects(solution_text))[0]
            except IndexError as e:
                logger.debug(f"JSON decode error: {e}")
                # Attempt to fix common JSON formatting issues
                solution_text = solution_text.replace("}}", "}")
                solution_text = solution_text.replace("{{", "{")
                pattern = r'```(.*?)```'
                match = re.search(pattern, solution_text, re.DOTALL)
                if match:
                    solution_text = match.group(1)
                try:
                    fixed_locator_dict = list(extract_json_objects(solution_text))[0]
                except IndexError as e:
                    logger.debug(f"Failed to decode JSON after fixing: {e}")
                    locator_has_been_fixed = False
                    continue
            except Exception as e:
                logger.debug(f"Unexpected error: {e}")
                locator_has_been_fixed = False
                continue
                
            try:
                fixed_locator_list = fixed_locator_dict['fixed_locators']
                return fixed_locator_list
            except:
                locator_has_been_fixed = False
                continue

    def get_locator_proposals_from_parser(self, data, result, source):
        soup = BeautifulSoup(source, 'xml')
        locators = []
        android_widgets = [
            'android.widget.Button',
            'android.widget.EditText',
            'android.widget.TextView',
            'android.widget.ImageView',
            'android.widget.CheckBox',
            'android.widget.RadioButton',
            'android.widget.ToggleButton',
            'android.widget.ProgressBar',
            'android.widget.SeekBar',
            'android.widget.Spinner',
            # 'android.widget.ListView',
            # 'android.widget.GridView',
            # 'android.widget.ScrollView',
            'android.widget.Switch',
            'android.widget.RatingBar'
        ]
        elements = soup.find_all(android_widgets)


        for elem in elements:
            if self.locators.get(str(elem)):
                locator = self.locators.get(str(elem))
                locators.append(locator)
            else:
                locator = get_locator(elem, soup)
                if locator:
                    locators.append(locator)
                    self.locators[f"{str(elem)}"] = locator
        
        return locators


def get_locator(elem, soup):
    selector = generate_unique_xpath_selector(elem, soup)
    if selector:
        return selector
    return None