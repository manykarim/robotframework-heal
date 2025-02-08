from robot.libraries.BuiltIn import BuiltIn
from robot.api import logger
import json
from bs4 import BeautifulSoup
import re
from .llm_client import LLM_TEXT_MODEL, LLM_LOCATOR_MODEL, litellm, completion
from .utils import extract_json_objects, filter_dict, compare_dict, xpath_to_browser, get_xpath_selector, get_simplified_dom_tree, generate_unique_css_selector, generate_unique_xpath_selector, is_leaf_or_lowest, has_parent_dialog_without_open, has_child_dialog_without_open, has_direct_text, is_headline, is_div_in_li, is_p, filter_locator_list_with_fuzz
import xmltodict
from .locator_db import LocatorDetailsDB
from tinydb import Query
from cssify import cssify
import pprint
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

PARALLEL = True

class BrowserHealer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BrowserHealer, cls).__new__(cls)
        return cls._instance

    def __init__(self, instance=None, **kwargs):
        self.browser=instance
        self.use_locator_db = kwargs.get('use_locator_db', False)
        self.use_llm_for_locator_proposals = kwargs.get('use_llm_for_locator_proposals', True)
        self.read_clickable_info = kwargs.get('read_clickable_info', True)
    
    def is_locator_broken(self, message) -> bool:
         return ('waiting for' in message or 'Element is not an' in message) and (not 'waiting for element to be' in message)
    
    def is_element_not_ready(self, message) -> bool:
        return 'element is not visible' in message or 'waiting for element to be' in message

    def is_modal_dialog_open(self) -> bool:
        soup = BeautifulSoup(self.browser.get_page_source(), 'html.parser')

        # Find all elements with 'display: none'
        dialogs = soup.find_all('dialog', {"open": True})

        if len(dialogs) > 0:
            return True
        else:
            return False

    def is_page_loading(self) -> bool:
        # return document.readyState == 'complete'
        is_loading_script = """ () => {      
        return document.readyState != 'complete';
        }
        """
        is_loading = self.browser.evaluate_javascript(None, is_loading_script)
        return bool(is_loading)

    def is_page_ready(self) -> bool:
        # return document.readyState == 'complete'
        is_ready_script = """ () => {      
        return document.readyState == 'complete';
        }
        """
        is_loading = self.browser.evaluate_javascript(None, is_ready_script)
        return bool(is_loading)

    def wait_until_page_is_ready(self, timeout=20):
        BuiltIn().wait_until_keyword_succeeds(timeout, "1s", "Browser.Wait For Load State", "load", "1s" )

    def close_modal_dialog(self):
        soup = BeautifulSoup(self.browser.get_page_source(), 'html.parser')
        dialog = soup.find('dialog', {"open": True})
        
        prompt_content = {
            'page_source': str(dialog)
        }

        schema = {
            "fixed_locator": "The fixed css or xpath locator. Starts with xpath= or css="
        }

        messages = []

        messages.append({
                'role': 'system',
                'content': (
            "You are a xpath and css selector tool that shall close a dialog."
            "You will analyze the `page_source` and find a short and unique xpath or css selector to close the dialog."
            "Most likely a button or a link needs to be clicked"
            "Respond only in valid json that looks like this: {'fixed_locator': <a fixed xpath or css locator>}"         
            "When the 'fixed_locator' is an xpath, always add a xpath= prefix to the locator."
            "When the 'fixed_locator' is an css selector, always add a css= prefix to the locator."
            f"Use the following schema: ```json{json.dumps(schema)}```."
            )

                })
        
        messages.append({
            'role': 'user',
            'content': (
                f"'page_source': ```{str(dialog)}```\n"
            )
        })

        locator_has_been_fixed = False
        retry_count = 0
        while not locator_has_been_fixed:
            retry_count += 1
            if retry_count > 5:
                break          
           
            response = litellm.completion(
                model = LLM_TEXT_MODEL,
                messages = messages,
                temperature = 0.1,
                top_k = 1, 
                response_format =  { "type": "json_object" }
            )
            solution_text = response['choices'][0]['message']['content']

            try:
                solution_dict = list(extract_json_objects(solution_text))[0]
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
                    solution_dict = list(extract_json_objects(solution_text))[0]
                except IndexError as e:
                    logger.debug(f"Failed to decode JSON after fixing: {e}")
                    locator_has_been_fixed = False
                    continue
            except Exception as e:
                logger.debug(f"Unexpected error: {e}")
                locator_has_been_fixed = False
                continue
                
            try:
                fixed_locator = str(solution_dict['fixed_locator'])
            except:
                locator_has_been_fixed = False
                continue

            # Search for xpath= or css= in the solution_text
            if fixed_locator.startswith('xpath'):
                # Remove xpath= from the string and store it as a variable
                new_locator = re.sub('xpath.', '', fixed_locator)
                retry_selector = "xpath=" + new_locator
            elif fixed_locator.startswith('/'):
                new_locator = fixed_locator
                retry_selector = "xpath=" + new_locator
            elif fixed_locator.startswith('css'):
                # Remove css= from the string and store it as a variable
                new_locator = re.sub('css.', '', fixed_locator)
                retry_selector = "css=" + new_locator 
            else:
                retry_selector = fixed_locator

            try:
                if self.browser.get_element_count(retry_selector) == 1:
                    locator_has_been_fixed = True
                    logger.info(f"Locator to close dialog has been found: {retry_selector}", also_console=True)
                    self.browser.click(retry_selector)
            except:
                locator_has_been_fixed = False
        if locator_has_been_fixed:
            return fixed_locator
        else:
            return None


    def get_fixed_locator(self, data, result) -> str:
        try:
            old_log_level = BuiltIn().set_log_level("NONE")
        except Exception as e:
            logger.info(f"Error when setting log level: {e}")

        output_dir = BuiltIn().get_variable_value('${OUTPUT_DIR}')
        testsuite = BuiltIn().get_variable_value('${SUITE NAME}')
                
        

        script = """() =>
        {
        function getFullInnerHTML(node = document.documentElement) {
            // Function to process each node and retrieve its HTML including Shadow DOM
            function processNode(node) {
                let html = "";

                // Check if the node is an element
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // If the node has a Shadow DOM, recursively process its shadow DOM
                    if (node.shadowRoot) {
                        html += `<${node.tagName.toLowerCase()}${getAttributes(node)}>`;
                        html += processNode(node.shadowRoot);
                        html += `</${node.tagName.toLowerCase()}>`;
                    } else {
                        // Process children if no Shadow DOM is present
                        html += `<${node.tagName.toLowerCase()}${getAttributes(node)}>`;
                        for (let child of node.childNodes) {
                            html += processNode(child);
                        }
                        html += `</${node.tagName.toLowerCase()}>`;
                    }
                } else if (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
                    // Process ShadowRoot (document fragments)
                    for (let child of node.childNodes) {
                        html += processNode(child);
                    }
                } else if (node.nodeType === Node.TEXT_NODE) {
                    // Add text content for text nodes
                    html += node.textContent;
                }
                return html;
            }

            // Helper function to get attributes of an element
            function getAttributes(node) {
                if (node.attributes && node.attributes.length > 0) {
                    return Array.from(node.attributes)
                        .map(attr => ` ${attr.name}="${attr.value}"`)
                        .join("");
                }
                return "";
            }

            // Start processing from the root node
            return processNode(node);
        }

        // Get the full inner HTML including all Shadow DOMs
        const fullHTML = getFullInnerHTML();
        return fullHTML;
            }
        """

        shadowdom_script ="""{
                let html = document.documentElement.outerHTML
                for (e of Array.from(document.documentElement.querySelectorAll('*')).filter(el => el.shadowRoot)) {e.shadowRoot.innerHTML}
                }"""
        
        shadowdom_exist_script = """ () => {      
        return Array.from(document.querySelectorAll('*')).some(el => el.shadowRoot);
        }
        """

        try:
            shadowdom_exists = self.browser.evaluate_javascript(None, shadowdom_exist_script)
            if shadowdom_exists:
                soup = BeautifulSoup(
                self.browser.evaluate_javascript(None, 
                script),
                'html.parser'
            )
            else:
                soup = BeautifulSoup(self.browser.get_page_source(), 'html.parser')
        except:
            soup = BeautifulSoup(self.browser.get_page_source(), 'html.parser')

        source = get_simplified_dom_tree(str(soup.body))

        failed_locator = BuiltIn().replace_variables(str(result.args[0]))
        
        if self.use_llm_for_locator_proposals:
            fixed_locator_list = self.get_locator_proposals_from_llm(data, result, source)
        else:
            fixed_locator_list = self.get_locator_proposals_from_parser(data, result, source)
        
        fixed_locators_with_info = []

        fixed_locators_with_similarity = []


        if self.use_locator_db:
            locator_db = LocatorDetailsDB().db
            for fixed_locator in fixed_locator_list:
                try:
                    retry_selector = get_locator_with_prefix(fixed_locator.strip())
                    
                    if self.browser.get_element_count(retry_selector) == 1:

                        try:
                            retry_locator_info = self.get_locator_info(retry_selector)
                            original_locator_info = locator_db.search(Query().locator == failed_locator & Query().testsuite == testsuite)[-1]
                            added, removed, modified, same, similarity = compare_dict(original_locator_info, retry_locator_info)
                        except:
                            similarity = 0.01
                        fixed_locators_with_similarity.append((retry_selector, similarity))
                except:
                    continue

            try:
                BuiltIn().set_log_level(old_log_level)
            except Exception as e:
                logger.info(f"Error when setting log level: {e}")


            fixed_locators_with_similarity.sort(key=lambda x: x[1], reverse=True)
            for fixed_locator in fixed_locators_with_similarity:
                retry_selector = fixed_locator[0]
                locator_has_been_fixed = True
                return retry_selector

        
        
        
        else:
            


            index = 0
            

            while index < len(fixed_locator_list):
                try:
                    retry_selector = get_locator_with_prefix(fixed_locator_list[index].strip())
                    if self.browser.get_element_count(retry_selector) == 0:
                        retry_selector = retry_selector.replace("button", "*")
                    if self.browser.get_element_count(retry_selector) == 1:
                        states = self.browser.get_element_states(retry_selector)
                        if 'visible' in states:
                            retry_locator_info = self.get_locator_info(retry_selector, read_clickable_info=self.read_clickable_info)
                            retry_locator_info = {key: value for key, value in retry_locator_info.items() if key not in ["testsuite"]}
                            fixed_locators_with_info.append({"index": int(index), "fixed_locator": retry_selector, "additional_info": retry_locator_info})
                    elif self.browser.get_element_count(retry_selector) > 1:
                        if self.browser.get_element_count(f"{retry_selector}:visible") == 1:
                            retry_selector = f"{retry_selector}:visible >> nth=0"
                            retry_locator_info = self.get_locator_info(retry_selector, read_clickable_info=self.read_clickable_info)
                            retry_locator_info = {key: value for key, value in retry_locator_info.items() if key not in ["testsuite"]}
                            fixed_locators_with_info.append({"index": int(index), "fixed_locator": retry_selector, "additional_info": retry_locator_info})
                        # for element in self.browser.get_elements(retry_selector):
                        #     fixed_locator_list.append(str(element))
                except:
                    pass
                index += 1

            if len(fixed_locators_with_info) > 50:
                fixed_locators_with_info = filter_locator_list_with_fuzz(fixed_locators_with_info, failed_locator)

            try:
                BuiltIn().set_log_level(old_log_level)
            except Exception as e:
                logger.info(f"Error when setting log level: {e}")


            logger.info(f"Pre-filtered locator candidates with info: {pprint.pformat(fixed_locators_with_info)}", also_console=False)

            messages = []

            messages.append({
                'role': 'system',
                'content': (
                    "You are a xpath and css selector self-healing tool for Robot Framework."
                    "You will select exactly one fixed_locator from a list of Locator Proposals."
                    "Respond using the following json schema: {'index': 'index of locator', 'fixed_locator': 'locator1'}"
                )

                })


            match data.name:
                    case "Fill Text" | "Type Text" | "Press Keys" | "Fill Secret" | "Type Secret" | "Clear Text":                
                        messages.append({
                            'role': 'user',
                            'content': (
                                f"fixed_locators with `input` or `textarea` elements and that are similar to failed_locator=`{failed_locator}` have a priority."
                                "Always return the unchanged fixed_locator."
                            )
                            })
                    
                    case "Click" | "Click With Options":
                        messages.append({
                            'role': 'user',
                            'content': (
                                f"fixed_locators with tagName `button`,`checkbox`, `a`, `li` or `input` elements and that are similar to failed_locator=`{failed_locator}` have a priority."
                                "Check for `clickable: True` property."
                                "Always return the unchanged fixed_locator."
                            )
                            })
                        if self.read_clickable_info:
                            fixed_locators_with_info = [x for x in fixed_locators_with_info if x['additional_info']['clickable']==True]

                    case "Select Options By" | "Deselect Options":
                        messages.append({
                            'role': 'user',
                            'content': (
                                f"fixed_locators with `select` elements have a priority"
                                "Always return the unchanged fixed_locator."
                            )
                            })
                    case "Check Checkbox" | "Uncheck Checkbox":
                        messages.append({
                            'role': 'user',
                            'content': (
                                f"fixed_locators with  `checkbox`, `button` and `input` elements and that are similar to failed_locator=`{failed_locator}` have a priority."
                                "Always return the unchanged fixed_locator."
                            )
                            })

                    case "Get Text":
                        messages.append({
                            'role': 'user',
                            'content': (
                                f"fixed_locators with `label` or `span` elements and that are similar to failed_locator=`{failed_locator}` have a priority"
                                "Always return the unchanged fixed_locator."
                            )
                            })



            messages.append({
                'role': 'user',
                'content': (
                            f"Broken Locator : `{failed_locator}`\n"
                            f"Keyword : `{data.name}`\n"
                            f"** Locators Proposals **\n"
                            f"```{json.dumps(fixed_locators_with_info)}```\n"
                            f"Analyse the `additional_info` for each `fixed_locator` to select the `fixed_locator` which most likely matches to failed_locator=`{failed_locator}`.\n" 
                            f"Priority for matching: innerText > previousSibling.innerText > nextSibling.innerText > parentElement.innerText\n"
                            f"Also consider fixed_locators, where the items from additional_info only match partially. "
                            )
            })

            response = litellm.completion(
                model = LLM_TEXT_MODEL,
                messages = messages,
                temperature = 0.1,
                top_k = 10,
                response_format =  { "type": "json_object" }
            )
            solution_text = response['choices'][0]['message']['content']

            logger.info(f"2nd LLM response with sorted candidates: {solution_text}", also_console=False)

            sorted_retry_locators = list(extract_json_objects(solution_text))[0]
            if isinstance(sorted_retry_locators, dict):
                if 'index' in sorted_retry_locators:
                    try:
                        retry_locator = next(item["fixed_locator"] for item in fixed_locators_with_info if int(item['index']) == int(sorted_retry_locators['index']))
                    except:
                        retry_locator = sorted_retry_locators["fixed_locator"]
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
            return_value = BuiltIn().run_keyword(data.name, *data.args)
            BuiltIn().run_keyword("Take Screenshot")
            return return_value
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            raise

    def get_element_count_for_locator(self, locator) -> int:
        return self.browser.get_element_count(locator)

    def has_locator(self, result) -> bool:
        if ("PageContent" in result.tags):
            return True
        else: 
            return False

    def get_locator_info(self, locator, read_clickable_info = False):
        locator_info = {}
        locator_info["locator"] = locator
        property_list = ["tagName", "childElementCount", "parentElement.tagName", "previousSibling.tagName", "nextSibling.tagName"]
        inner_text_property = "innerText"
        additional_text_property_list = [ "parentElement.innerText", "previousSibling.innerText", "nextSibling.innerText"]
        # property_list = ["tagName", "innerText", "childElementCount", "parentElement.tagName", "parentElement.innerText"]
        allowed_attributes = ['id', 'class', 'value', 'name', 'type', 'placeholder', 'role', 'innerText']
        attribute_list = self.browser.get_attribute_names(locator)
        for attribute in allowed_attributes:
            if attribute in attribute_list:
                value = self.get_attribute_value(locator, attribute)
                if value:
                    locator_info[attribute] = value
        for property in property_list:
            value = self.get_property_value(locator, property)
            if value:
                locator_info[property]=value
        inner_text = self.get_property_value(locator, inner_text_property)
        if inner_text:
            locator_info["innerText"]=inner_text
        else:
            for property in additional_text_property_list:
                value = self.get_property_value(locator, property)
                if value:
                    locator_info[property]=value
        testsuite = BuiltIn().get_variable_value("${SUITE NAME}")
        locator_info["testsuite"] = testsuite

        if read_clickable_info:

            clickable_tags = ['BUTTON', 'A', 'INPUT', 'SELECT']
            if locator_info["tagName"] in clickable_tags:
                locator_info["clickable"]= True
            else:
                if self.does_cursor_pointer_style_exist(locator) or self.does_checked_property_exist(locator) or self.does_clickable_control_property_exist(locator) or self.does_value_property_exist(locator):
                    locator_info["clickable"]= True
                else:
                    locator_info["clickable"]= False


        return locator_info

    def does_cursor_pointer_style_exist(self, locator):
        try:
            cursor_style = self.browser.get_style(locator, "cursor")
            return cursor_style == "pointer"
        except:
            return False
            
    def does_value_property_exist(self, locator):
        try:
            return self.browser.evaluate_javascript(locator, f"(elem) => elem.{'value'}") == 'on' or self.browser.evaluate_javascript(locator, f"(elem) => elem.{'value'}") == 'off'
        except:
            return False

    def does_checked_property_exist(self, locator):
        try:
            return self.browser.evaluate_javascript(locator, f"(elem) => elem.{'checked'}") != ''            
        except:
            return False

    def does_clickable_control_property_exist(self, locator):
        try:
            tag = self.browser.evaluate_javascript(locator, f"(elem) => elem.{'control.tagName'}")
            if tag == 'BUTTON' or tag == 'A':
                return True
            elif tag == 'INPUT':
                type = self.browser.evaluate_javascript(locator, f"(elem) => elem.{'control.type'}")
                if type == "button" or type == "radio" or type == "checkbox" or type == "search" or type == "reset" or type == "submit":
                    return True
            return False
        except:
            return False

    def get_property_value(self, locator, property):
        try:
            return self.browser.evaluate_javascript(locator, f"(elem) => elem.{property}")
        except:
            return None
        
    def get_attribute_value(self, locator, attribute):
        try:
            return self.browser.get_attribute(locator, attribute)
        except:
            return None
        
    def get_locator_proposals_from_llm(self, data, result, source):

        failed_locator = BuiltIn().replace_variables(str(result.args[0]))

        schema = {
            "fixed_locator": "The fixed css or xpath locator. Starts with xpath= or css="
        }

        locator_has_been_fixed = False
        retry_count = 0
        error_message = result.message



        messages = []
        
        SYS_PROMPT= (
            "You are a xpath and css selector self-healing tool.\n"
            "You will provide a fixed_locator for a failed_locator.\n"
            "The User prompt will contain data for 'error_message' , 'failed_locator', 'keyword' and 'page_source'.\n"
            "You will analyze the `page_source` and the `error_message` and find the eight best alternative fixed_locators for the failed_locator.\n"
            "Keywords like 'Fill Text', 'Enter Text' or 'Press Keys'  are always related to 'input' or 'textarea' elements.\n"
            "Keywords like 'Click' are often  related to 'button','checkbox', 'a' or 'input' elements.\n"
            "Keywords like 'Select' or 'Deselect' are often related to 'select' elements.\n"
            "Keywords like 'Check' or 'Uncheck' are often related to 'checkbox' elements.\n"
            "When the 'fixed_locator' is an xpath, always add a xpath= prefix to the locator.\n"
            "When the 'fixed_locator' is an css selector, always add a css= prefix to the locator.\n"
            "Respond using the following json schema: {'fixed_locators': ['locator1', 'locator2', 'locator3', ... ]}.\n"
            "Example: {'fixed_locators': ['css=input[id='my_id']', 'xpath=//*[contains(text(),'Login')]', 'xpath=//label[contains(text(),'Speeding')]/..//input', 'xpath=//*[contains(@class, 'submitBtn')]', 'css=button.class1.class2']}\n"
        )


        messages.append({
            'role': 'system',
            'content': SYS_PROMPT
            })
        
        messages.append({
            'role': 'user',
            'content': (
                        f"error_message: `{error_message}`\n"
                        f"failed_locator: `{failed_locator}`\n"
                        f"keyword : `{data.name}`\n"
                        f"arguments `{data.args}`\n"
                        f"page_source: ```{source}```"
                        )
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
                    response = litellm.completion(
                        model = LLM_TEXT_MODEL,
                        messages = messages,
                        temperature = 0.1,
                        top_k = 10,
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
        soup = BeautifulSoup(source, 'html.parser')

        locators = []

        match data.name:
                case "Fill Text" | "Type Text" | "Press Keys" | "Fill Secret" | "Type Secret" | "Clear Text":                
                    element_types = ['textarea', 'input' ]
                    elements = soup.find_all(element_types)
                case "Click" | "Click With Options":
                    element_types = ['a', 'button', 'checkbox', 'link', 'input', 'label', 'li', has_direct_text]
                    elements = soup.find_all(element_types)
                case "Select Options By" | "Deselect Options":
                    element_types = ['select']
                    elements = soup.find_all(element_types)
                case "Check Checkbox" | "Uncheck Checkbox":
                    element_types = ['input', 'button', 'checkbox']
                    elements = soup.find_all(element_types)
                case "Get Text":
                    element_types = ['label', 'div', 'span', has_direct_text]
                    elements = soup.find_all(element_types)


        if PARALLEL:
    # *** Parallel Processing ***

            with ProcessPoolExecutor() as executor:
                # Submit tasks to the executor
                futures = [executor.submit(get_locators_for_element_type, item, str(soup)) for item in element_types]
                
                # Collect the results as they complete
                for future in as_completed(futures):
                    if future.result():
                        locators += future.result()

        else:
            # Filter elements to include only leaves or lowest elements of their type
            filtered_elements = [elem for elem in elements if ((is_leaf_or_lowest(elem) or has_direct_text(elem)) and (not has_parent_dialog_without_open(elem)) and (not has_child_dialog_without_open(elem)) and (not is_headline(elem)) and (not is_div_in_li(elem)) and (not is_p(elem)))]

            
            # Generate and display unique selectors
            for elem in filtered_elements:
                with open("locator_stats.csv", "a") as f:
                    f.write(f"{str(elem).replace('\n', '')};")
                start = time.time()
                locator = get_locator(elem, soup)
                if locator:
                    locators.append(locator)
                stop = time.time()
                total = stop - start
                if locator:
                    with open("locator_stats.csv", "a") as f:
                        f.write(f"{locator};{total}\n")
                else:
                    with open("locator_stats.csv", "a") as f:
                        f.write(f"No Locator found;{total}\n")





        return locators


def get_locator_with_prefix(locator):
        # Search for xpath= or css= in the solution_text
    # output_dir = BuiltIn().get_variable_value('${OUTPUT_DIR}')
    # with open(f"{output_dir}/locator_proposals.csv", 'a') as f:
    #     f.write(f"{locator}")

    if locator:
        if locator.startswith('xpath'):
            try:
                locator_with_prefix = xpath_to_browser(locator)
            except:        
                if 'text()' not in locator:
                    new_locator = re.sub('xpath.', '', locator)
                    try:
                        new_locator = cssify(new_locator)
                        locator_with_prefix = "css=" + new_locator
                    except:
                        locator_with_prefix = "xpath=" + new_locator
                else:
                    new_locator = re.sub('xpath.', '', locator)
                    locator_with_prefix = "xpath=" + new_locator
        elif locator.startswith('/'):
            try:
                locator_with_prefix = xpath_to_browser(locator)
            except:        
                if 'text()' not in locator:
                    new_locator = re.sub('xpath.', '', locator)
                    try:
                        new_locator = cssify(new_locator)
                        locator_with_prefix = "css=" + new_locator
                    except:
                        locator_with_prefix = "xpath=" + new_locator
                else:
                    new_locator = re.sub('xpath.', '', locator)
                    locator_with_prefix = "xpath=" + new_locator
        elif locator.startswith('css'):
            # Remove css= from the string and store it as a variable
            new_locator = re.sub('css.', '', locator)
            locator_with_prefix = "css=" + new_locator 
        else:
            locator_with_prefix = locator
        locator_with_prefix = locator_with_prefix.replace(":contains", ":has-text")
        locator_with_prefix = locator_with_prefix.replace(":-soup-contains-own", ":text")
        locator_with_prefix = locator_with_prefix.replace(":-soup-contains", ":has-text")
        
        # with open(f"{output_dir}/locator_proposals.csv", 'a') as f:
        #     f.write(f"{locator_with_prefix}")
        
        return locator_with_prefix
    else:
        return None

def get_locators_for_element_type(element_type, source):
    soup = BeautifulSoup(
                source,
                'html.parser'
            )
    elements = soup.find_all(element_type)
    filtered_elements = [elem for elem in elements if ((is_leaf_or_lowest(elem) or has_direct_text(elem)) and (not has_parent_dialog_without_open(elem)) and (not has_child_dialog_without_open(elem)) and (not is_headline(elem)) and (not is_div_in_li(elem)) and (not is_p(elem)))]

    locators = []
    # Generate and display unique selectors
    for elem in filtered_elements:
        locator = get_locator(elem, soup)
        if locator:
            locators.append(locator)
    return locators

def get_locator(elem, soup):
    selector = generate_unique_css_selector(elem, soup)
    if selector:
        return "css=" + selector
    # else:
    #     selector = generate_unique_xpath_selector(elem, soup)
    #     if selector:
    #         return "xpath=" + selector
    return None
 
