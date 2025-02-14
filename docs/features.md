# Features

## CSS/XPATH Generator

Enable via `use_llm_for_locator_proposals`=`false`

An internal CSS/XPATH generator will generate a list of unique locator proposals for all relevant elements of a DOM Tree.  
Relevant elements are decided based on the used Keyword.  
For example, for a keyword `Fill Text`, the  `input` and `textarea` elements are more relevant.  
For a keyword `Click`, the `button` , `a` and other `clickable` elements are more relevant.

The generated locators are unique and based on attributes like `class`, `id`, `placeholder` , `type` and `name`.
Also `text` values and next/previous `siblings` as well as `parent` elements are used to support the unique identification.

## AI Supported Self-Healing

Enable via `use_llm_for_locator_proposals`=`true`

DOM Tree will be sent to a LLM, which will identify a list of locator proposals based on the failed locator.
Locators will depend on the type of LLM.

LLMs can be selected via environment variables:  

* `LLM_TEXT_MODEL` (model used for picking final locator from proposal list)
* `LLM_LOCATOR_MODEL` (model for generating locator proposals from DOM tree)

## Collect additional information for locator proposals

## Locator Database

Enable via  

* `collect_locator_info`: Boolean flag to enable or disable the collection of locator information. Default is false.
* `use_locator_db`: Boolean flag to enable or disable the use of a locator database for selection of fixed locator. Default is false.
* `locator_db_file`: Specifies the filename for the locator database. Default is "locator_db.json".

During a successful test run, additional details for each working locator can be collected and stored into a TinyDB database by setting `collect_locator_info` to `true`.

The locator database is just a `.json` file and the location and name can be set via `locator_db_file`.

During a test run in which locators shall be healed, the previously collected details in the TinyDB can be used to make better decision for the healed locator.  
That behavior can be enabled by setting `use_locator_db` to `True`.

## Shadow DOM

## DOM Tree reduction

* `fix`: Specifies the mode of operation, set to "realtime" for real-time healing. Default is "realtime".
* `collect_locator_info`: Boolean flag to enable or disable the collection of locator information. Default is false.
* `use_locator_db`: Boolean flag to enable or disable the use of a locator database. Default is false.
* `use_llm_for_locator_proposals`: Boolean flag to enable or disable the use of a language model for generating locator proposals. If true, locator proposals will be identified from DOM Tree via LLM. If set to false, locator proposals are generated via CSS/XPATH generator. Default is false.
* `heal_assertions`: Boolean flag to enable or disable the healing of assertions. Default is false. (not implemented yet)
* `locator_db_file`: Specifies the filename for the locator database. Default is "locator_db.json".