import cv2
from .llm_client import LLM_TEXT_MODEL, LLM_VISION_MODEL, completion
from io import BytesIO
import base64
import json
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from .utils import extract_json_objects
try:
    import pyautogui
except (ImportError, KeyError):
    _has_pyautogui = False
else:
    _has_pyautogui= True

class VisualHealer:
    def __init__(self, instance=None, **kwargs):
        self.instance = instance

    def get_screenshot_as_base64(self, image_path=None):
        if image_path:
            image = cv2.imread(image_path)
            # Convert to base64
            im_data = cv2.imencode('.png', image)[1]
            base64_image = base64.b64encode(im_data).decode('utf-8')
        else:
            photo = pyautogui.screenshot()
            output = BytesIO()
            photo.save(output, format='PNG')
            im_data = output.getvalue()
            base64_image = base64.b64encode(im_data).decode()
        return base64_image

    def get_image_description(self, image_as_base64):

        response = completion(
            model = LLM_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                                    {
                                        "type": "text",
                                        "text": "Whats in this image?"
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                        "url": image_as_base64
                                        }
                                    }
                                ]
                }
            ],
            temperature=0.1
        )
        text = response['choices'][0]['message']['content']

        return text
    
    def get_error_explanation(self, data, result, image_as_base64):

        schema = {

                "keyword": {
                    "type": "string",
                    "description": "The Keyword Name"
                    },
                "args": {
                "type": "array",
                "description": "The Keyword Arguments",
                "items": {
                    "type": "string"
                        },
                        }
            }

        messages = []

        prompt_content=( 
                    "You are a tool to verify automated test results from Robot Framework\n"
                    "You will receive the error_message, keyword, arguments and a screenshot\n"
                    "You will analyze the screenshot, the error_message and the identified texts and the check if the error_message makes sense.\n" 
                    "The error message will use the format: Text '<actual result>' should be '<expected result>'\n"
                    
                    f"error_message: {result.message}\n"
                    f"keyword: {data.name}\n"
                    f"arguments: {BuiltIn().replace_variables(str(data.args))}\n"

                    "You will return all identified texts in the screenshot.\n"
                    "You will analyze the screenshot, the error_message and the identified texts and the check if the error_message makes sense.\n" 
                    "If the arguments are incorrect, they need to be adjusted\n"
                    "Consider the <actual result>, when adjusting the keyword arguments."
                    f"If adjustment is needed you will add a headline ***Adjustment*** and respond with the updated keyword and arguments using the following schema: {json.dumps(schema)}\n"
                    "Example: {'keyword': 'Do Something', 'args': ['hello', 'world'] }\n"
                    "Your answer will be short and clear\n"
                )

        messages.append({
                'role': 'user',
                'content': prompt_content,
            })


        response = completion(
            model = LLM_TEXT_MODEL,
            messages = messages,
            images=[f"data:image/png;base64,{image_as_base64}"],
            temperature = 0.5,
        )
        analysis = response['choices'][0]['message']['content']
        logger.info(f"Visual LLM explanation:\n{analysis}\n", also_console=True)

        
        messages = []

        SYS_PROMPT = (
            "You are a tool to verify the automated test results and the proposed adjustment\n"
            "You will receive the error_message, keyword, arguments and an analysis\n"
            "You will check if the proposed adjustment is correct\n"
            f"If adjustment is needed you will add a headline ***Adjustment*** and respond with the updated keyword and arguments using the following schema: {json.dumps(schema)}\n"
            "Example: {'keyword': 'Do Something', 'args': ['hello', 'world'] }\n"
            "Your answer will be short and clear\n"
            )
        messages.append(
             {
                  "role": "system",
                  "content": SYS_PROMPT

             }
        )

        prompt_content = {
            'error_message': result.message,
            'keyword': data.name,
            'arguments': BuiltIn().replace_variables(str(data.args)),
            'analysis': analysis
            }
        
        messages.append({
                'role': 'user',
                'content': json.dumps(prompt_content),
            })

        messages.append({
             "role": "assistant",
             "content": f"Analysis: {analysis}"
        })

        messages.append({
             "role": "user",
             "content": "Check if the analysis is consistent and if the recommended adjustment is correct\n"
                        "Especially check for small differences between the error_message and the updated args/arguments, e.g. spaces, symbols or special characters\n"
                        f"Add a headline ***Adjustment*** and respond with the updated keyword and arguments using the following schema: {json.dumps(schema)}\n"
        })


        response = completion(
            model = LLM_TEXT_MODEL,
            messages = messages,
            temperature = 0.01,
        )
        text = response['choices'][0]['message']['content']
        logger.info(f"LLM verification:\n{text}\n", also_console=True)

        return text
    
    def verify_error_analysis(self, explanation, data, result):
         
        prompt_content = {
            'error_message': result.message,
            'keyword': data.name,
            'args': BuiltIn().replace_variables(str(data.args)), 
            'analysis': explanation
            }
        
        schema = {

                "keyword": {
                    "type": "string",
                    "description": "The Keyword Name"
                    },
                "args": {
                "type": "array",
                "description": "The Keyword Arguments",
                "items": {
                    "type": "string"
                        },
                        }
            }


        SYS_PROMPT = (
            "You are a tool to verify the analysis of automated test results\n"
            "You will receive an error_message, the executed keyword, the keyword arguments and an analysis\n"
            "Check if the analysis is consistent and if the recommended adjustment is correct\n"
            "Especially check for small differences between the error_message and the updated args/arguments, e.g. spaces, symbols or special characters\n"
            f"Add a headline ***Adjustment*** and respond using the following json schema: {'keyword': 'Do Something', 'args': ['hello', 'world']}"
            "Your answer will be short and clear\n"
            )
        messages = []
        messages.append(
             {
                  "role": "system",
                  "content": SYS_PROMPT

             }
        )
       
        messages.append({
                'role': 'user',
                'content': json.dumps(prompt_content),
            })

        response = completion(
            model = LLM_TEXT_MODEL,
            messages = messages,
            temperature = 0.01,
        )
        text = response['choices'][0]['message']['content']

        logger.info(f"LLM verification:\n{text}\n", also_console=True)
        return text

    def is_application_still_loading(self, data, result, image_as_base64):

        SYS_PROMPT = (
            "Your are a test tool that analyses screeshots and checks if the application is currently loading or if the application is ready\n"
            "You will receive the error_message, keyword, arguments and a screenshot\n"
            "Analyse the screenshit\n"
            "If the application is still loading, respond with 'True'. If the application is ready, respond with 'False'\n"
            'Respond only in valid json that looks like this: ```{"result": "True/False", "reason": "An explanation of your decision" "screenshot_description": "A short description of the screenshot"}```\n' 
            # 'Example: {"result": true, "reason": "A spinner is shown, which indicates that the screen is still loading"}\n'
            # 'Example: {"result": true, "reason": "Labels for buttons are missing, which indicates that the screen is still loading"}\n'
            # 'Example: {"result": false, "reason": "All elements are loaded and visible"}\n'
            )

        messages = []
        
        prompt_content = {
            'error_message': result.message,
            'keyword': data.name,
            'arguments': BuiltIn().replace_variables(str(data.args))
            }

        
        # messages.append(
        #      {
        #           "role": "system",
        #           "content": SYS_PROMPT

        #      }
        # )


        messages.append(
                {
                'role': 'user',
                'content': ( 
                    "You are a test tool that analyses screenshots and check if the application is currently loading or if the application is ready\n"
                    
                    f"error_message: {result.message}\n"
                    f"keyword: {data.name}\n"
                    f"arguments: {BuiltIn().replace_variables(str(data.args))}\n"

                    "If the application is still loading, respond with 'True'. If the application is ready, respond with 'False'\n"
                    "If the issue is due to an error in the keyword or argument, respond with 'False'\n"
                    'Respond only in valid json that looks like this: ```{"result": "True/False", "reason": "An explanation of your decision", "image_description": "A short description of the screenshot"}```\n' 
                    
                )
                })

        messages.append(
                {
                'role': 'user',
                'content': '',
                'images': [image_as_base64]
                })
        
        messages.append(
             {
                  "role": "assistant",
                  "content": "```json"

             }
            )

        prompt_content=( 
                    "You are a test tool that analyses screenshots and check if the application is currently loading or if the application is ready\n"
                    
                    f"error_message: {result.message}\n"
                    f"keyword: {data.name}\n"
                    f"arguments: {BuiltIn().replace_variables(str(data.args))}\n"
                    f"screenshot: [img-0]<image>\n"

                    "If the application is still loading, respond with 'True'. If the application is ready, respond with 'False'\n"
                    "If the issue is due to an error in the keyword or argument, respond with 'False'\n"
                    'Respond only in valid json that looks like this: ```{"result": "True/False", "reason": "An explanation of your decision", "image_description": "A short description of the screenshot"}```\n' 
                    
                )

        response = completion(
            model = LLM_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                                    {
                                        "type": "text",
                                        "text": prompt_content
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                        "url": image_as_base64
                                        }
                                    }
                                ]
                }
            ],
            temperature=0.1
        )
        analysis = response['choices'][0]['message']['content']

        logger.info(f"Visual LLM explanation:\n{analysis}\n", also_console=True)

        return list(extract_json_objects(analysis))[0]
    
    def is_modal_dialog_open(self,image_as_base64):

        messages = []

        prompt_content=( 
                    'Check if a popup dialog or a notification dialog is visible in the screenshot\n'
                    'Respond with with {"result": true} (if a dialog is open) or {"result": false} (if no dialog is open)\n'
                    'Only respond with valid json\n'
                )

        messages.append({
            "role": "user",
            "content": prompt_content
                })



        response = completion(
            model = LLM_VISION_MODEL,
            messages = messages,
            images=[f"data:image/png;base64,{image_as_base64}"],
            temperature = 0.5,
         )
        analysis = response['choices'][0]['message']['content']
        logger.info(f"Visual LLM explanation:\n{analysis}\n", also_console=True)

        return list(extract_json_objects(analysis))[0]['result']
        