import pytest
from SelfHealing.visual_healing import VisualHealer
from unittest.mock import patch
import cv2
import base64
from unittest.mock import Mock


mock_data = Mock()
mock_result = Mock()

@pytest.mark.skip(reason="Visual Recognition not good enough")
@patch('robot.libraries.BuiltIn.BuiltIn.replace_variables')
def test_check_waiting(mock_replace_variables, testdata_dir):
    keyword = "Click"
    args = ["locator('button').locator('text=\"Continue\"')"]
    error_message=  f"""
    	TimeoutError: locator.click: Timeout 5000ms exceeded.
    Call log:
  - waiting for locator('button').locator('text="Continue"')
    - locator resolved to <span id="signInButtonText">Continue</span>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not visible
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is not visible
    - retrying click action
      - waiting 100ms
    10 × waiting for element to be visible, enabled and stable
       - element is not visible
     - retrying click action
       - waiting 500ms
    """
    mock_result.args = args
    mock_result.name = keyword
    mock_data.args = args
    mock_data.name = keyword
    mock_result.message = error_message
    mock_replace_variables.return_value = args[0]

    image = cv2.imread(f"{testdata_dir}/loading_001.png")
    # Convert to base64
    image_base64 = cv2.imencode('.png', image)[1]
    base64_image = base64.b64encode(image_base64).decode('utf-8')

    healer = VisualHealer()
    response = healer.is_application_still_loading(data=mock_data, result=mock_result, image_as_base64=base64_image)
    assert bool(response["result"]) == True


@pytest.mark.skip(reason="Visual Recognition not good enough")
@patch('robot.libraries.BuiltIn.BuiltIn.replace_variables')
def test_check_ready(mock_replace_variables, testdata_dir):
    keyword = "Fill Text"
    args = ["email"]
    error_message=  f"""
    TimeoutError: locator.fill: Timeout 5000ms exceeded.
    Call log:
  - waiting for locator('locator('input').locator('text=\"email\"')')
    """
    mock_result.args = args
    mock_result.name = keyword
    mock_data.args = args
    mock_data.name = keyword
    mock_result.message = error_message
    mock_replace_variables.return_value = args[0]

    image = cv2.imread(f"{testdata_dir}/ready_002.png")
    # Convert to base64
    image_base64 = cv2.imencode('.png', image)[1]
    base64_image = base64.b64encode(image_base64).decode('utf-8')

    healer = VisualHealer()


    response = healer.is_application_still_loading(data=mock_data, result=mock_result, image_as_base64=base64_image)
    assert bool(response["result"]) == False

def test_permission_dialog(testdata_dir):
    image = cv2.imread(f"{testdata_dir}/permission_dialog_001.png")
    # Convert to base64
    image_base64 = cv2.imencode('.png', image)[1]
    base64_image = base64.b64encode(image_base64).decode('utf-8')

    healer = VisualHealer()
    result = healer.is_modal_dialog_open(base64_image)
    assert bool(result) == True

  
def test_no_permission_dialog(testdata_dir):
  image = cv2.imread(f"{testdata_dir}/ready_002.png")
  # Convert to base64
  image_base64 = cv2.imencode('.png', image)[1]
  base64_image = base64.b64encode(image_base64).decode('utf-8')

  healer = VisualHealer()
  result = healer.is_modal_dialog_open(base64_image)
  assert bool(result) == False