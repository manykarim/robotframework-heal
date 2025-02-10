from json import JSONDecoder
from cssify import cssify
import re
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
import dataclasses
from bs4 import BeautifulSoup
from lxml import etree
from thefuzz import fuzz

@dataclasses.dataclass
class Xpath_Element:
    element_with_attributes: str
    element: str
    attributes: list

# Define the grammar for XPath
xpath_grammar = Grammar(r"""
    xpath = elem_with_attributes*
    elem_with_attributes = elem attributes*
    attributes = lbrackets text rbrackets
    text        = ~r"(?<=\[)[^[\]]*?(?=\])"
    elem = (delimiter axis* tag) / (lparantheses delimiter axis* tag rparantheses)
    axis = ~"[a-z-]+" colon
    tag = ~"[a-zA-Z0-9*]+"
    delimiter = "//" / "/"
    colon = ":"{1,2}
    lbrackets        = "["
    rbrackets        = "]"
    lparantheses = "("
    rparantheses = ")"
""")

# Define a visitor to walk through the parse tree
class XPathVisitor(NodeVisitor):
    def __init__(self):
        self.parts = []

    # def visit_xpath(self, node, visited_children):
    #     self.parts.append(node.text)

    def visit_elem(self, node, visited_children):
        return node.text.strip()

    def visit_attributes(self, node, visited_children):
        return node.text.strip()

    def visit_elem_with_attributes(self, node, visited_children):
        elem, attributes = visited_children
        #self.parts.append(node.text)
        self.parts.append(Xpath_Element(element_with_attributes=node.text, element=elem, attributes=attributes))

    # def visit_tag(self, node, visited_children):
    #     self.parts.append(node.text)

    # def visit_expr(self, node, visited_children):
    #     self.parts.append(node.text)

    # def visit_delimiter(self, node, visited_children):
    #     self.parts.append(node.text)

    def generic_visit(self, node, visited_children):
        return visited_children or node

def split_xpath(xpath):
    tree = xpath_grammar.parse(xpath)
    visitor = XPathVisitor()
    visitor.visit(tree)
    return visitor.parts

def xpath_to_browser(xpath):
    """
    Converts a simplified XPath to a hybrid syntax combining CSS and special markers.
    Supports cases like:
    - Text-based selection with `contains(text(), ...)`
    - Attribute-based selection with `contains(@attribute, ...)`
    - Parent element traversal with `..`

    :param xpath: XPath string to convert
    :return: Equivalent hybrid selector string
    """
    # Remove 'xpath=' prefix if present
    if xpath.startswith("xpath="):
        xpath = xpath[6:]

    # Split the XPath into smaller parts by '//' or '/'
    xpath_parts = split_xpath(xpath)

    converted_parts = []

    for part in xpath_parts:
        if not part or part.element_with_attributes in ['/', '//']:
            continue

        # Try to convert the part to CSS
        try:
            css = cssify(f"{part.element_with_attributes}")
            if ":contains" in css:
                tag, contains = css.split(":contains")            
                text = contains.strip("()")
                if text.startswith("^") and text.endswith("$"):
                    converted_parts.append(f"css={tag}")
                    converted_parts.append(f"text='{text.strip('^$')}'")
                else:
                    converted_parts.append(f"css={tag}")
                    converted_parts.append(f"text={text.strip()}")                    
            else:
                converted_parts.append(f"css={css}")

        except Exception as e:
            if isinstance(part.attributes, list) and len(part.attributes) == 1:
                nth = re.findall(r'\[(\d+)\]', part.attributes[0])
                if nth:
                    tag = cssify(f'{part.element.strip("()")}')
                    converted_parts.append(f"css={tag}")
                    converted_parts.append(f"nth={int(nth[0])-1}") 
                else:
                    # Explicit fallback for any error
                    converted_parts.append(f"xpath={part.element_with_attributes}")
            else:
                converted_parts.append(f"xpath={part.element_with_attributes}")

    return " >> ".join(converted_parts)


def get_tag(tag_name, tags):
    for tag in tags:
        if tag.startswith(tag_name):
            return tag
    return None

def extract_json_objects(text, decoder=JSONDecoder()):
    """Find JSON objects in text, and yield the decoded JSON data

    Does not attempt to look for JSON arrays, text, or other JSON types outside
    of a parent JSON object.

    """
    pos = 0
    while True:
        match = text.find('{', pos)
        if match == -1:
            break
        try:
            result, index = decoder.raw_decode(text[match:])
            yield result
            pos = match + index
        except ValueError:
            pos = match + 1


def find_item_with_key(d, target_key, path=None):
    if path is None:
        path = []
    for key, value in d.items():
        if key == target_key:
            return path + [key]
        elif isinstance(value, dict):
            result = find_item_with_key(value, target_key, path + [key])
            if result:
                return result
    return None

def get_subtree(d, path):
    subtree = d
    for key in path:
        subtree = subtree[key]
    return subtree

def get_siblings(d, path):
    if len(path) == 1:
        return d
    parent_path = path[:-1]
    parent = get_subtree(d, parent_path)
    return parent

def merge_dicts(a, b):
    for key in b:
        if key in a and isinstance(a[key], dict) and isinstance(b[key], dict):
            merge_dicts(a[key], b[key])
        else:
            a[key] = b[key]

def filter_dict(d, target_keys):
    if isinstance(target_keys, str):
        target_keys = [target_keys]

    filtered_dict = {}
    for target_key in target_keys:
        path = find_item_with_key(d, target_key)
        if not path:
            continue

        current_level = filtered_dict
        for key in path[:-1]:
            if key not in current_level:
                current_level[key] = {}
            current_level = current_level[key]

        item_key = path[-1]
        parent = get_siblings(d, path)
        current_level[item_key] = parent[item_key]

    return filtered_dict

def compare_dict(d1, d2):
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    shared_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o : (d1[o], d2[o]) for o in shared_keys if d1[o] != d2[o]}
    same = set(o for o in shared_keys if d1[o] == d2[o])
    
    # Calculate similarity score
    total_changes = len(added) + len(removed) + len(modified)
    total_elements = total_changes + len(same)
    similarity_score = len(same) / total_elements if total_elements > 0 else 0
    
    return added, removed, modified, same, similarity_score


def get_xpath_selector(tag=None, id=None, class_=None, text=None, source=None):
    from lxml import etree

    if source is None:
        raise ValueError("Source HTML must be provided")
    
    tree = etree.HTML(source)
    xpath_query = ".//"
    
    if tag:
        xpath_query += tag
    else:
        xpath_query += "*"
    
    conditions = []
    
    if id:
        conditions.append(f"@id='{id}'")
    if class_:
        conditions.append(f"contains(concat(' ', normalize-space(@class), ' '), ' {class_} ')")
    if text:
        conditions.append(f"text()='{text}'")
    
    if conditions:
        xpath_query += "[" + " and ".join(conditions) + "]"
    
    element_tree = etree.ElementTree(tree)
    elements = tree.xpath(xpath_query)
    xpaths = [element_tree.getpath(element) for element in elements]
    
    return xpaths


def clean_text_for_selector(text):
    """Sanitize text for use in a CSS selector."""
    return re.sub(r'\s+', ' ', text.strip())

def get_selector_count(soup, selector):
    try:
        elements = soup.select(selector)
        return len(elements)
    except Exception:
        return 0

def is_selector_unique(soup, selector):
    """Check if the CSS selector matches only one element."""
    try:
        elements = soup.select(selector)
        return len(elements) == 1
    except Exception:
        return False

def is_selector_multiple(soup, selector):
    """Check if the CSS selector matches multiple elements."""
    try:
        elements = soup.select(selector)
        return len(elements) > 1
    except Exception:
        return False

def generate_unique_css_selector(element, soup, check_parents = True, check_siblings = True, check_children = True, check_text = True, only_return_unique_selectors=True, text_exclusions=[]):
    steps = []
    text_steps = []
    
    element_contains_text = False

    tag_selector = f"{element.name}"
    steps.append(tag_selector)  
  
    # Step 2: ID
    if element.get('id'):
        id_selector = f"#{element['id']}"
        if is_selector_unique(soup, f"{element.name}{id_selector}"):
            return f"{element.name}{id_selector}"
        steps.append(id_selector)
            
    if element.get('name'):
        name_selector = f'[name="{element["name"]}"]'
        if is_selector_unique(soup, f"{element.name}{name_selector}"):
            return f"{element.name}{name_selector}"
        steps.append(name_selector)

    if element.get('type'):
        type_selector = f'[type="{element["type"]}"]'
        if is_selector_unique(soup, f"{element.name}{type_selector}"):
            return f"{element.name}{type_selector}"
        steps.append(type_selector)

    if element.get('placeholder'):
        placeholder_selector = f'[placeholder="{element["placeholder"]}"]'
        if is_selector_unique(soup, f"{element.name}{placeholder_selector}"):
            return f"{element.name}{placeholder_selector}"
        steps.append(placeholder_selector)

    if element.get('role'):
        role_selector = f'[role="{element["role"]}"]'
        if is_selector_unique(soup, f"{element.name}{role_selector}"):
            return f"{element.name}{role_selector}"
        steps.append(role_selector)

    # if check_text:
    #     # Step 4: Text Content
    #     if element.text.strip():
    #         for text in element.stripped_strings:
    #             sanitized_text = clean_text_for_selector(text)
    #             text_selector = f':-soup-contains("{sanitized_text}")'
    #             if is_selector_unique(soup, f"{element.name}{text_selector}"):
    #                 return f"{element.name}{text_selector}"
    #             elif is_selector_unique(soup, f"{element.name}{text_selector}"):
    #                 return f"{element.name}{text_selector}"
 
    # Step 3: Class
    if element.get('class'):
        filtered_classes = [x for x in element['class'] if "hidden" not in x]
        class_list = []
        class_selector = None
        for single_class in filtered_classes:
            class_list.append(single_class)
            class_selector = "." + ".".join(class_list)
            if is_selector_unique(soup, f"{element.name}{class_selector}"):
                return f"{element.name}{class_selector}"
        if class_selector:
            steps.append(class_selector)


    if check_text:
        text_selectors = []
        selector_count = 0
        # Step 4: Text Content
        if element.text.strip():
            element_contains_text = True
            if element.string and element.string not in text_exclusions:
                sanitized_text = clean_text_for_selector(element.string)
                text_selector = f':-soup-contains-own("{sanitized_text}")'
                selector_count = get_selector_count(soup, f"{''.join(steps)}{text_selector}")
                if selector_count == 1:
                    return f"{''.join(steps)}{text_selector}"
                elif selector_count >1:
                    text_steps.append(text_selector)
            if not element.string or selector_count==0:
                for text in element.stripped_strings:
                    if text not in text_exclusions:
                        sanitized_text = clean_text_for_selector(text)
                        text_selector = f':-soup-contains("{sanitized_text}")'
                        # if is_selector_unique(soup, f"{element.name}{text_selector}"):
                        #     return f"{element.name}{text_selector}"
                        text_selectors.append(text_selector)

                        selector_count = get_selector_count(soup, f"{''.join(steps)}{''.join(text_selectors)}")
                        if selector_count == 1:
                            return f"{''.join(steps)}{''.join(text_selectors)}"
                        elif selector_count >1:
                            text_steps.append(text_selector)
                        elif selector_count == 0:
                            break

    # Special check for items inside li/ul
    if element.find_parent("li"):
        if element.find_parent("ul"):
            ul_parent_selector = generate_unique_css_selector(element.find_parent("ul"), soup, check_parents=True, check_siblings=False, check_text=False, only_return_unique_selectors=False)
            li_parent_selector = generate_unique_css_selector(element.find_parent("li"), soup, check_parents=False, check_siblings=False, check_text=False, only_return_unique_selectors=False)
            ul_li_selector = f"{ul_parent_selector} > {li_parent_selector} {''.join(steps)}"
            if is_selector_unique(soup, ul_li_selector):
                return ul_li_selector 
    elif element.find_parent("ul"):
            ul_parent_selector = generate_unique_css_selector(element.find_parent("ul"), soup, check_parents=True, check_siblings=False, check_text=False, only_return_unique_selectors=False)
            ul_selector = f"{ul_parent_selector} > {''.join(steps)}"
            if is_selector_unique(soup, ul_selector):
                return ul_selector 


    if check_siblings:
        # Step 7: Sibling Relationships
        siblings = element.find_previous_siblings()
        for sibling in siblings:
            if element_contains_text:
                previous_sibling_selector = generate_unique_css_selector(sibling, soup, check_siblings=False, check_parents=False, check_children=False, only_return_unique_selectors=False, text_exclusions=list(element.stripped_strings))
            else:
                previous_sibling_selector = generate_unique_css_selector(sibling, soup, check_siblings=False, check_parents=False, check_children=False, only_return_unique_selectors=False)
            if previous_sibling_selector:
                if is_selector_unique(soup, f"{previous_sibling_selector} + {''.join(steps)}"):
                    return f"{previous_sibling_selector} + {''.join(steps)}"
                if is_selector_unique(soup, f"{previous_sibling_selector} + {''.join(steps)}{''.join(text_steps)}"):
                    return f"{previous_sibling_selector} + {''.join(steps)}{''.join(text_steps)}"
                

        siblings = element.find_next_siblings()
        for sibling in siblings:
            next_sibling_selector = generate_unique_css_selector(sibling, soup, check_siblings=False, check_parents=False, check_children=False, only_return_unique_selectors=False)
            if next_sibling_selector:
                sibling_selector = f"{''.join(steps)}:has(+ {next_sibling_selector})"
                if is_selector_unique(soup, sibling_selector):
                    return sibling_selector
    
    if check_parents:
        parent_level = 0
        max_level = 10
        # Step 5: Parent and Sibling Relationships
        parent_selectors = []
        for parent in element.parents:
            if parent and not has_child_dialog_without_open(parent) and parent.name != "[document]":
                parent_level += 1
                if parent_level <= max_level:
                    if element_contains_text:
                        parent_selector = generate_unique_css_selector(parent, soup, check_children=False, check_siblings=True, check_parents=False, check_text=True, only_return_unique_selectors=False, text_exclusions=list(element.stripped_strings))
                    else:
                        parent_selector = generate_unique_css_selector(parent, soup, check_children=False, check_siblings=True, check_parents=False, check_text=True, only_return_unique_selectors=False)
                    if parent_selector:
                        parent_selectors.append(parent_selector)
                        parent_child_selector = f"{' > '.join(reversed(parent_selectors))} > {''.join(steps)}"
                        current_parent_child_selector = f"{parent_selector} {''.join(steps)}"
                        if is_selector_unique(soup, current_parent_child_selector):
                            return current_parent_child_selector                        
                        elif is_selector_unique(soup, parent_child_selector):
                            return parent_child_selector



    if only_return_unique_selectors:
        if is_selector_unique(soup, ''.join(steps)):
            return ''.join(steps)
        else:
            parent = element.find_parent()
            siblings = parent.find_all(element.name)
            if len(siblings) > 1:
                index = siblings.index(element) + 1
                return f"{''.join(steps)}:nth-of-type({index})"
    else:
        return ''.join(steps)

def clean_text_for_xpath(text):
    """Sanitize text for use in an XPath expression."""
    return re.sub(r'\s+', ' ', text.strip())

def get_xpath_count(soup, xpath):
    try:
        # Parse the HTML content using lxml
        tree = etree.HTML(str(soup))
        # Use the XPath to find matching elements
        elements = tree.xpath(xpath)
        # Return True if exactly one element matches
        return len(elements)
    except Exception as e:
        print(f"Error in get_xpath_count: {e}\nXpath: {xpath}")
        return 0

def is_xpath_unique(soup, xpath):
    """Check if the XPath selector matches only one element."""
    try:
        if soup.is_xml:
            tree = etree.XML(str(soup.hierarchy))
        else:
            tree = etree.HTML(str(soup))
    except Exception as e:
        print(f"Error in is_xpath_unique: {e}\nXpath: {xpath}")
        return False
    try:
        # Use the XPath to find matching elements
        elements = tree.xpath(xpath)
        # Return True if exactly one element matches
        return len(elements) == 1
    except Exception as e:
        print(f"Error in is_xpath_unique: {e}\nXpath: {xpath}")
        return False

def is_xpath_multiple(soup, xpath):
    """Check if the XPath selector matches multiple elements."""
    try:
        # Parse the HTML content using lxml
        tree = etree.HTML(str(soup))
    except:
        try:
            tree = etree.HTML(str(soup.hierarchy))
        except Exception as e:
            print(f"Error in is_xpath_unique: {e}\nXpath: {xpath}")
            return False
    try:
        # Use the XPath to find matching elements
        elements = tree.xpath(xpath)
        # Return True if more than one element matches
        return len(elements) > 1
    except Exception as e:
        print(f"Error in is_xpath_multiple: {e}")
        return False

def generate_unique_xpath_selector(element, soup, check_parents = True, check_siblings = True, check_children = True, check_text = True, only_return_unique_selectors=True):
    """Generate a unique XPath for the given element."""
    if element is None:
        return ""

    # Step 1: Tag
    steps = []
    tag_xpath = f"{element.name}"
    steps.append(tag_xpath)

    if element.get("content-desc"):
        content_desc_xpath = f"[@content-desc='{element['content-desc']}']"
        content_desc_xpath_with_prefix = f"//{element.name}{content_desc_xpath}"
        if is_xpath_unique(soup, content_desc_xpath_with_prefix):
            return content_desc_xpath_with_prefix
        if is_xpath_multiple(soup, content_desc_xpath_with_prefix):
            steps.append(content_desc_xpath)


    if element.get("resource-id"):
        content_desc_xpath = f"[@resource-id='{element['resource-id']}']"
        content_desc_xpath_with_prefix = f"//{element.name}{content_desc_xpath}"
        if is_xpath_unique(soup, content_desc_xpath_with_prefix):
            return content_desc_xpath_with_prefix
        if is_xpath_multiple(soup, content_desc_xpath_with_prefix):
            steps.append(content_desc_xpath)

    if check_text:
        # Step 4: Text Content
            if element.text.strip():
                for text in element.stripped_strings:
                    sanitized_text = clean_text_for_xpath(text)
                    if '"' in sanitized_text:
                        text_xpath = f"[contains(text(), '{sanitized_text}')]"
                    elif "'" in sanitized_text:
                        text_xpath = f'[contains(text(), "{sanitized_text}")]'
                    else:
                        text_xpath = f"[contains(text(), '{sanitized_text}')]"
                    if is_xpath_unique(soup, f"//{element.name}{text_xpath}"):
                        return f"//{element.name}{text_xpath}"

            elif element.get("text"):
                sanitized_text = clean_text_for_xpath(element["text"])
                if '"' in sanitized_text:
                    text_xpath = f"[contains(@text, '{sanitized_text}')]"
                elif "'" in sanitized_text:
                    text_xpath = f'[contains(@text, "{sanitized_text}")]'
                else:
                    text_xpath = f"[contains(@text, '{sanitized_text}')]"
                if is_xpath_unique(soup, f"//{element.name}{text_xpath}"):
                    return f"//{element.name}{text_xpath}"
    # Step 2: ID
    if element.get("id"):
        id_xpath = f"[@id='{element['id']}']"
        id_xpath_with_prefix = f"//{element.name}{id_xpath}"
        if is_xpath_unique(soup, id_xpath_with_prefix):
            return id_xpath_with_prefix
        if is_xpath_multiple(soup, id_xpath_with_prefix):
            steps.append(id_xpath)


    if element.get("name"):
        name_xpath = f"[@name='{element['name']}']"
        name_xpath_with_prefix = f"//{element.name}{name_xpath}"
        if is_xpath_unique(soup, name_xpath_with_prefix):
            return name_xpath_with_prefix
        if is_xpath_multiple(soup, name_xpath_with_prefix):
            steps.append(name_xpath)


    if element.get("type"):
        type_xpath = f"[@type='{element['type']}']"
        type_xpath_with_prefix = f"//{element.name}{type_xpath}"
        if is_xpath_unique(soup, type_xpath_with_prefix):
            return type_xpath_with_prefix
        if is_xpath_multiple(soup, type_xpath_with_prefix):
            steps.append(type_xpath)

    if element.get("placeholder"):
        placeholder_xpath = f"[@placeholder='{element['placeholder']}']"
        placeholder_xpath_with_prefix = f"//{element.name}{placeholder_xpath}"
        if is_xpath_unique(soup, placeholder_xpath_with_prefix):
            return placeholder_xpath_with_prefix
        if is_xpath_multiple(soup, placeholder_xpath_with_prefix):
            steps.append(placeholder_xpath)

    if element.get("role"):
        role_xpath = f"[@role='{element['role']}']"
        role_xpath_with_prefix = f"//{element.name}{role_xpath}"
        if is_xpath_unique(soup, role_xpath_with_prefix):
            return role_xpath_with_prefix
        if is_xpath_multiple(soup, role_xpath_with_prefix):
            steps.append(role_xpath)

    # Step 3: Class
    if element.get("class"):
        # Build an XPath condition for all classes using "and"
        if isinstance(element['class'], list):
            filtered_classes = [x for x in element['class'] if "hidden" not in x]
            class_conditions = " and ".join([f"contains(@class, '{cls}')" for cls in filtered_classes])
            class_xpath = f"[{class_conditions}]"
        if isinstance(element['class'], str):
            class_xpath = f"[@class='{element['class']}']"
        class_xpath_with_prefix = f"//{element.name}{class_xpath}"
        if is_xpath_unique(soup, class_xpath_with_prefix):
            return class_xpath_with_prefix
        if is_xpath_multiple(soup, class_xpath_with_prefix):
            steps.append(class_xpath)

    if check_text:
        # Step 4: Text Content

        if element.text.strip():
            for text in element.stripped_strings:
                element_contains_text = True
                sanitized_text = clean_text_for_xpath(text)
                if '"' in sanitized_text:
                    text_xpath = f"[contains(text(), '{sanitized_text}')]"
                elif "'" in sanitized_text:
                    text_xpath = f'[contains(text(), "{sanitized_text}")]'
                else:
                    text_xpath = f"[contains(text(), '{sanitized_text}')]"
                if is_xpath_unique(soup, f"//{element.name}{text_xpath}"):
                    return f"//{element.name}{text_xpath}"
                elif is_xpath_unique(soup, f"//*{text_xpath}"):
                    return f"//*{text_xpath}"
                elif is_xpath_multiple(soup, f"//{element.name}{text_xpath}"):
                    steps.append(text_xpath)
                elif is_xpath_multiple(soup, f"//*{text_xpath}"):
                    steps.append(f"//*{text_xpath}")

        elif element.get("text"):
            element_contains_text = True
            sanitized_text = clean_text_for_xpath(element["text"])
            if '"' in sanitized_text:
                text_xpath = f"[contains(@text, '{sanitized_text}')]"
            elif "'" in sanitized_text:
                text_xpath = f'[contains(@text, "{sanitized_text}")]'
            else:
                text_xpath = f"[contains(@text, '{sanitized_text}')]"
            if is_xpath_unique(soup, f"//{element.name}{text_xpath}"):
                return f"//{element.name}{text_xpath}"
            elif is_xpath_multiple(soup, f"//{element.name}{text_xpath}"):
                steps.append(text_xpath)

    if is_xpath_unique(soup, f'//{"".join(steps)}'):
        return f'//{"".join(steps)}'
    
    if check_parents:
        # Step 5: Parent Relationships
        parent = element.parent
        if parent:
            parent_xpath = generate_unique_xpath_selector(parent, soup)
            if parent_xpath:
                index = parent.find_all(element.name).index(element) + 1
                parent_child_xpath = f"{parent_xpath}/{element.name}[{index}]"
                if is_xpath_unique(soup, parent_child_xpath):
                    return parent_child_xpath

    if check_siblings:
        # Step 6: Sibling Relationships
        siblings = element.find_previous_siblings(element.name)
        for sibling in siblings:
            previous_sibling_selector = generate_unique_xpath_selector(sibling, soup, check_siblings=False, check_parents=False, check_children=False)
            if previous_sibling_selector:
                sibling_selector = f"{previous_sibling_selector}/following-sibling::{''.join(steps)}"
                if is_xpath_unique(soup, sibling_selector):
                    return sibling_selector
        
        siblings = element.find_next_siblings()
        for sibling in siblings:
            next_sibling_selector = generate_unique_xpath_selector(sibling, soup, check_siblings=False, check_parents=False, check_children=False)
            if next_sibling_selector:
                sibling_selector = f"{next_sibling_selector}/preceding-sibling::{''.join(steps)}"
                if is_xpath_unique(soup, sibling_selector):
                    return sibling_selector
                
    if check_parents:
        parent_level = 0
        max_level = 10
        # Step 5: Parent and Sibling Relationships
        parent_selectors = []
        for parent in element.parents:
            if parent and not has_child_dialog_without_open(parent) and parent.name != "[document]":
                parent_level += 1
                if parent_level <= max_level:

                    parent_selector = generate_unique_xpath_selector(parent, soup, check_children=False, check_siblings=True, check_parents=False, check_text=True, only_return_unique_selectors=False)
                    if parent_selector:
                        parent_selectors.append(parent_selector)
                        parent_child_selector = f"{'/'.join(reversed(parent_selectors))}/{''.join(steps)}"
                        current_parent_child_selector = f"{parent_selector}//{''.join(steps)}"
                        if is_selector_unique(soup, current_parent_child_selector):
                            return current_parent_child_selector                        
                        elif is_selector_unique(soup, parent_child_selector):
                            return parent_child_selector

    # if check_children:
    #     # Step 7: Child Relationships
    #     children = element.find_all(recursive=False)
    #     for child in children:
    #         child_text = clean_text_for_xpath(child.text)
    #         if child_text:
    #             if '"' in child_text:
    #                 child_text_xpath = f"{element.name}/{child.name}[contains(text(), '{child_text}')]"
    #             elif "'" in child_text:
    #                 child_text_xpath = f'{element.name}/{child.name}[contains(text(), "{child_text}")]'
    #             else:
    #                 child_text_xpath = f"{element.name}/{child.name}[contains(text(), '{child_text}')]"
                
    #             if is_xpath_unique(soup, child_text_xpath):
    #                 return child_text_xpath

    if only_return_unique_selectors:
        if is_xpath_unique(soup, f'//{"".join(steps)}'):
        # Combine steps into a final XPath
            return f'//{"".join(steps)}'
    else:
        if is_xpath_unique(soup, f'//{"".join(steps)}') or is_xpath_multiple(soup, f'//{"".join(steps)}'):
            return f'//{"".join(steps)}'

def has_display_none(tag):
    style = tag.get('style', '')
    return 'display: none' in style


def get_simplified_dom_tree(source):
    soup = BeautifulSoup(source, 'html.parser')

    # Remove all <script> tags
    for elem in soup.find_all('script'):
        elem.decompose()


    # Remove all <script> tags
    for elem in soup.find_all('svg'):
        elem.decompose()

    for elem in soup.find_all('source'):
        elem.decompose()

    for elem in soup.find_all('animatetransform'):
        elem.decompose()

    # for elem in soup.find_all('footer'):
    #     elem.decompose()

    for elem in soup.find_all('template'):
        elem.decompose()

    for elem in soup.find_all('head'):
        elem.decompose()

    for elem in soup.find_all('nav'):
        elem.decompose()

    # Find all elements with 'display: none'
    hidden_elements = soup.find_all(has_display_none)
    # Remove these elements
    for element in hidden_elements:
        element.decompose()

    # Find all elements with 'display: none'
    hidden_elements = soup.find_all(attrs={"type": "hidden"})
    # Remove these elements
    for element in hidden_elements:
        element.decompose()


#        source = soup.prettify()

    # Desperate: Delete all class from DIV elements to save space
    # for div_tag in soup.find_all('div'):
    #     del div_tag['class']
    
    # for span_tag in soup.find_all('span'):
    #     del span_tag['class']

    for a_tag in soup.find_all('a'):
        del a_tag['href']
        del a_tag['class']
        
    for tag in soup.find_all(style=True):
        del tag['style']

    for section_tag in soup.find_all('section'):
        del section_tag['class']

    for picture_tag in soup.find_all('picture'):
        del picture_tag['class']

    # for li_tag in soup.find_all('li'):
    #     del li_tag['class']

    for img_tag in soup.find_all('img'):
        del img_tag['class']
        del img_tag['alt']
        del img_tag['src']

    attributes_to_keep = ['id', 'class', 'value', 'name', 'type', 'placeholder', 'role']
    for tag in soup.find_all(True):  # True finds all tags
        for attr in list(tag.attrs):  # list() to avoid runtime error
            if attr not in attributes_to_keep:
                del tag[attr]

    return str(soup.body)


# Function to check if an element is a leaf or the lowest of its type in a branch
def is_leaf_or_lowest(element):
    # Check if the element has no child elements (leaf)
    if not element.find():
        return True

    # Check if the element is the lowest of its type in this branch
    tag_name = element.name
    if not element.find_all(tag_name):
        return True

    return False

def has_parent_dialog_without_open(element):
    """Check if any parent of the given element is a <dialog> without the 'open' attribute."""
    try:
        dialog = [x for x in element.parents if x.name == "dialog"]
        for d in dialog:
            if not d.has_attr('open'):
                    return True
        return False
    except:
        return True

def has_child_dialog_without_open(element):
    """Check if any parent of the given element is a <dialog> without the 'open' attribute."""
    try:
        dialog = [x for x in element.children if x.name == "dialog"]
        for d in dialog:
            if not d.has_attr('open'):
                    return True
        return False
    except:
        return True
    
def get_first_parent_with_text(element):
    """
    This function takes a BeautifulSoup element and returns the first parent element
    that contains text content.
    """
    parent = element.parent
    while parent is not None:
        if parent.get_text(strip=True):
            return parent
        parent = parent.parent
    return None

 # Function to check if an element directly contains text
def has_direct_text(tag):
    # Check if the tag has any direct text (not in its children)
    return tag.string and tag.string.strip() and not tag.find()

def is_headline(tag):
    return tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

def is_div_in_li(tag):
    # Check if the tag is a div
    if tag.name != 'div':
        return False
    
    # Check if the parent of the tag is an li
    parent = tag.find_parent('li')
    return parent is not None

def is_p(tag):
    if tag.name == 'p':
        return True
    else:
        return False

def filter_locator_list_with_fuzz(dict_list, defined_value, threshold = 50):
    filtered_items = []
    
    for item in dict_list:
        for key, value in item["additional_info"].items():
            if isinstance(value, str):
                score = fuzz.ratio(value, defined_value)
                if score > threshold:
                    filtered_items.append(item)
                    break  # No need to check other keys if one already matches
    return filtered_items


def filter_locator_list_with_fuzz_median(dict_list, defined_value):
    """
    Calculate score for all items
    Only return the  items with a score above the median score
    """
    # Calculate scores for all items
    scores = []
    for item in dict_list:
        for key, value in item["additional_info"].items():
            if isinstance(value, str):
                score = fuzz.ratio(value, defined_value)
                scores.append(score)
    
    # Calculate the median score
    median_score = sum(scores) / len(scores)

    # Filter items with a score above the median score
    filtered_items = []
    # iterate over scores and items
    for score, item in zip(scores, dict_list):
        if score > median_score:
            filtered_items.append(item)
    return filtered_items


