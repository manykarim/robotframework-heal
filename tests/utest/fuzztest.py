from thefuzz import fuzz, process

dict_list = [
    {
        "index": 0,
        "fixed_locator": "css=a:has(+ p.c10-font-id)",
        "additional_info": {
            "locator": "css=a:has(+ p.c10-font-id)",
            "class": "btn btn--primary booking-tool-login__login-btn",
            "tagName": "A",
            "innerText": "Login",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "LoginnnNo account yet? Register now",
        },
    },
    {
        "index": 1,
        "fixed_locator": 'css=a:text("Register now")',
        "additional_info": {
            "locator": 'css=a:text("Register now")',
            "class": "link",
            "tagName": "A",
            "innerText": "Register now",
            "parentElement.tagName": "P",
            "parentElement.innerText": "No account yet? Register now",
        },
    },
    {
        "index": 3,
        "fixed_locator": 'css=p.rte-section.c1-font-id:has-text("Do you already have a contract and use our digital services? Login here and benefit from our most recent upgrade to") + p.rte-section.c1-font-id > strong.c3-font-id > a',
        "additional_info": {
            "locator": 'css=p.rte-section.c1-font-id:has-text("Do you already have a contract and use our digital services? Login here and benefit from our most recent upgrade to") + p.rte-section.c1-font-id > strong.c3-font-id > a',
            "class": "rte-link link",
            "tagName": "A",
            "innerText": "Login",
            "parentElement.tagName": "STRONG",
            "parentElement.innerText": "Login",
        },
    },
    {
        "index": 4,
        "fixed_locator": 'css=p.rte-section.c1-font-id:has-text("You have a contract with us and have not yet heard about the benefits of registering at") + p.rte-section.c1-font-id > strong.c3-font-id > a',
        "additional_info": {
            "locator": 'css=p.rte-section.c1-font-id:has-text("You have a contract with us and have not yet heard about the benefits of registering at") + p.rte-section.c1-font-id > strong.c3-font-id > a',
            "class": "rte-link link",
            "tagName": "A",
            "innerText": "Register",
            "parentElement.tagName": "STRONG",
            "parentElement.innerText": "Register",
        },
    },
    {
        "index": 5,
        "fixed_locator": 'css=a:text("Get started")',
        "additional_info": {
            "locator": 'css=a:text("Get started")',
            "class": "rte-link link",
            "tagName": "A",
            "innerText": "Get started",
            "parentElement.tagName": "STRONG",
            "parentElement.innerText": "Get started",
        },
    },
    {
        "index": 6,
        "fixed_locator": 'css=a:text("Connect Benefits and Key Features (PDF, 211.54 KB)")',
        "additional_info": {
            "locator": 'css=a:text("Connect Benefits and Key Features (PDF, 211.54 KB)")',
            "class": "reset-link c6-font-id icon-button",
            "tagName": "A",
            "innerText": " Connect Benefits and Key Features (PDF, 211.54 KB)",
            "childElementCount": 1,
            "parentElement.tagName": "LI",
            "parentElement.innerText": " Connect Benefits and Key Features (PDF, 211.54 KB)",
        },
    },
    {
        "index": 7,
        "fixed_locator": "css=a:has(+ div.teaser__content)",
        "additional_info": {
            "locator": "css=a:has(+ div.teaser__content)",
            "class": "teaser__picture-segment",
            "tagName": "A",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Digital Services Hub, Land TransportnnAdvanced eServicesnnEnjoy the benefits of all your services on one platform.nnAdvanced eServicesnContinue ",
        },
    },
    {
        "index": 8,
        "fixed_locator": "css=a#standard-teaser-1-bzyf4o60qo35yknsw1fomupnh",
        "additional_info": {
            "locator": "css=a#standard-teaser-1-bzyf4o60qo35yknsw1fomupnh",
            "id": "standard-teaser-1-bzyf4o60qo35yknsw1fomupnh",
            "class": "reset-link",
            "tagName": "A",
            "innerText": "Advanced eServicesnnEnjoy the benefits of all your services on one platform.",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Digital Services Hub, Land TransportnnAdvanced eServicesnnEnjoy the benefits of all your services on one platform.nnAdvanced eServicesnContinue ",
        },
    },
    {
        "index": 9,
        "fixed_locator": 'css=a:has-text("Advanced eServices"):has-text("Continue")',
        "additional_info": {
            "locator": 'css=a:has-text("Advanced eServices"):has-text("Continue")',
            "class": "link link--primary arrow-link ",
            "tagName": "A",
            "innerText": "Advanced eServicesnContinue ",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Digital Services Hub, Land TransportnnAdvanced eServicesnnEnjoy the benefits of all your services on one platform.nnAdvanced eServicesnContinue ",
        },
    },
    {
        "index": 10,
        "fixed_locator": 'css=label.transport-mode-radio.booking-tool__tab.c3-font-id.is-mobile:has-text("Land")',
        "additional_info": {
            "locator": 'css=label.transport-mode-radio.booking-tool__tab.c3-font-id.is-mobile:has-text("Land")',
            "class": "transport-mode-radio booking-tool__tab c3-font-id is-mobile",
            "tagName": "LABEL",
            "innerText": "Land",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "LandnAirnOcean",
        },
    },
    {
        "index": 11,
        "fixed_locator": 'css=label.transport-mode-radio.booking-tool__tab.c3-font-id.is-mobile:has-text("Air")',
        "additional_info": {
            "locator": 'css=label.transport-mode-radio.booking-tool__tab.c3-font-id.is-mobile:has-text("Air")',
            "class": "transport-mode-radio booking-tool__tab c3-font-id is-mobile",
            "tagName": "LABEL",
            "innerText": "Air",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "LandnAirnOcean",
        },
    },
    {
        "index": 12,
        "fixed_locator": "css=label.transport-mode-radio.booking-tool__tab.c3-font-id.is-mobile.active-transport-mode",
        "additional_info": {
            "locator": "css=label.transport-mode-radio.booking-tool__tab.c3-font-id.is-mobile.active-transport-mode",
            "class": "transport-mode-radio booking-tool__tab c3-font-id is-mobile active-transport-mode booking-tool__tab--active",
            "tagName": "LABEL",
            "innerText": "Ocean",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "LandnAirnOcean",
        },
    },
    {
        "index": 13,
        "fixed_locator": "css=label.location-switch.switch",
        "additional_info": {
            "locator": "css=label.location-switch.switch",
            "class": "location-switch switch",
            "tagName": "LABEL",
            "innerText": "Pickup Required",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Pickup Required",
        },
    },
    {
        "index": 14,
        "fixed_locator": "css=label.location-switch.toggle",
        "additional_info": {
            "locator": "css=label.location-switch.toggle",
            "class": "location-switch toggle",
            "tagName": "LABEL",
            "innerText": "Delivered to Recipient",
            "childElementCount": 2,
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Delivered to Recipient",
        },
    },
    {
        "index": 15,
        "fixed_locator": 'css=div.feature-stage__feature-wrapper.feature-wrapper--secondary > form[role="search"].tracking-form.tracking-form--secondary.paper.js-tracking-form > p.c3-font-id + fieldset.tracking-form__fields > label.control.tracking-form__input:has-text("ID Number")',
        "additional_info": {
            "locator": 'css=div.feature-stage__feature-wrapper.feature-wrapper--secondary > form[role="search"].tracking-form.tracking-form--secondary.paper.js-tracking-form > p.c3-font-id + fieldset.tracking-form__fields > label.control.tracking-form__input:has-text("ID Number")',
            "class": "control tracking-form__input",
            "tagName": "LABEL",
            "innerText": "ID Number",
            "childElementCount": 2,
            "parentElement.tagName": "FIELDSET",
            "parentElement.innerText": "ID NumbernTrack",
        },
    },
    {
        "index": 16,
        "fixed_locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("All-in-one platform")',
        "additional_info": {
            "locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("All-in-one platform")',
            "class": "tablist-menu__item js-tablist-menu__item",
            "role": "menuitem",
            "tagName": "LI",
            "innerText": "All-in-one platform",
            "childElementCount": 1,
            "parentElement.tagName": "MENU",
            "parentElement.innerText": "All-in-one platformnEasy-to-use interfacen24/7 servicenPersonalized dashboardnAll your shipments at a glancenQuick access to all services",
        },
    },
    {
        "index": 17,
        "fixed_locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("Easy-to-use interface")',
        "additional_info": {
            "locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("Easy-to-use interface")',
            "class": "tablist-menu__item js-tablist-menu__item",
            "role": "menuitem",
            "tagName": "LI",
            "innerText": "Easy-to-use interface",
            "childElementCount": 1,
            "parentElement.tagName": "MENU",
            "parentElement.innerText": "All-in-one platformnEasy-to-use interfacen24/7 servicenPersonalized dashboardnAll your shipments at a glancenQuick access to all services",
        },
    },
    {
        "index": 18,
        "fixed_locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("24/7 service")',
        "additional_info": {
            "locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("24/7 service")',
            "class": "tablist-menu__item js-tablist-menu__item",
            "role": "menuitem",
            "tagName": "LI",
            "innerText": "24/7 service",
            "childElementCount": 1,
            "parentElement.tagName": "MENU",
            "parentElement.innerText": "All-in-one platformnEasy-to-use interfacen24/7 servicenPersonalized dashboardnAll your shipments at a glancenQuick access to all services",
        },
    },
    {
        "index": 19,
        "fixed_locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("Personalized dashboard")',
        "additional_info": {
            "locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item:has-text("Personalized dashboard")',
            "class": "tablist-menu__item js-tablist-menu__item",
            "role": "menuitem",
            "tagName": "LI",
            "innerText": "Personalized dashboard",
            "childElementCount": 1,
            "parentElement.tagName": "MENU",
            "parentElement.innerText": "All-in-one platformnEasy-to-use interfacen24/7 servicenPersonalized dashboardnAll your shipments at a glancenQuick access to all services",
        },
    },
    {
        "index": 20,
        "fixed_locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item.tablist-menu__item--scrolled-out:has-text("All your shipments at a glance")',
        "additional_info": {
            "locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item.tablist-menu__item--scrolled-out:has-text("All your shipments at a glance")',
            "class": "tablist-menu__item js-tablist-menu__item tablist-menu__item--scrolled-out",
            "role": "menuitem",
            "tagName": "LI",
            "innerText": "All your shipments at a glance",
            "childElementCount": 1,
            "parentElement.tagName": "MENU",
            "parentElement.innerText": "All-in-one platformnEasy-to-use interfacen24/7 servicenPersonalized dashboardnAll your shipments at a glancenQuick access to all services",
        },
    },
    {
        "index": 21,
        "fixed_locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item.tablist-menu__item--scrolled-out:has-text("Quick access to all services")',
        "additional_info": {
            "locator": 'css=li[role="menuitem"].tablist-menu__item.js-tablist-menu__item.tablist-menu__item--scrolled-out:has-text("Quick access to all services")',
            "class": "tablist-menu__item js-tablist-menu__item tablist-menu__item--scrolled-out",
            "role": "menuitem",
            "tagName": "LI",
            "innerText": "Quick access to all services",
            "childElementCount": 1,
            "parentElement.tagName": "MENU",
            "parentElement.innerText": "All-in-one platformnEasy-to-use interfacen24/7 servicenPersonalized dashboardnAll your shipments at a glancenQuick access to all services",
        },
    },
    {
        "index": 22,
        "fixed_locator": "css=li.download-module__item",
        "additional_info": {
            "locator": "css=li.download-module__item",
            "class": "download-module__item",
            "tagName": "LI",
            "innerText": " Connect Benefits and Key Features (PDF, 211.54 KB)",
            "childElementCount": 1,
            "parentElement.tagName": "UL",
            "parentElement.innerText": " Connect Benefits and Key Features (PDF, 211.54 KB)",
        },
    },
    {
        "index": 26,
        "fixed_locator": 'css=input[type="checkbox"].switch__input:has(+ div.switch__label:text("Pickup Required"))',
        "additional_info": {
            "locator": 'css=input[type="checkbox"].switch__input:has(+ div.switch__label:text("Pickup Required"))',
            "class": "switch__input",
            "type": "checkbox",
            "tagName": "INPUT",
            "parentElement.tagName": "LABEL",
            "parentElement.innerText": "Pickup Required",
        },
    },
    {
        "index": 28,
        "fixed_locator": 'css=location-selection.hydrated:has(+ location-selection.hydrated:has-text("To")) > div.location-selection-wrapper.is-mobile > div:has-text("Pickup Required") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5:has-text("Select Location") + div.address-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-7 > address-selection.hydrated > div.control > input#address-input[type="text"][placeholder="Provide Seaport Name"].inputfield.control__input.connect-landing-widget-input',
        "additional_info": {
            "locator": 'css=location-selection.hydrated:has(+ location-selection.hydrated:has-text("To")) > div.location-selection-wrapper.is-mobile > div:has-text("Pickup Required") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5:has-text("Select Location") + div.address-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-7 > address-selection.hydrated > div.control > input#address-input[type="text"][placeholder="Provide Seaport Name"].inputfield.control__input.connect-landing-widget-input',
            "id": "address-input",
            "class": "inputfield control__input connect-landing-widget-input",
            "type": "text",
            "placeholder": "Provide Seaport Name",
            "tagName": "INPUT",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Provide Seaport Name",
        },
    },
    {
        "index": 29,
        "fixed_locator": 'css=input[type="checkbox"].switch__input:has(+ div.switch__label:text("Delivered to Recipient"))',
        "additional_info": {
            "locator": 'css=input[type="checkbox"].switch__input:has(+ div.switch__label:text("Delivered to Recipient"))',
            "class": "switch__input",
            "type": "checkbox",
            "tagName": "INPUT",
            "parentElement.tagName": "LABEL",
            "parentElement.innerText": "Delivered to Recipient",
        },
    },
    {
        "index": 31,
        "fixed_locator": 'css=location-selection.hydrated:has-text("From") + location-selection.hydrated > div.location-selection-wrapper.is-mobile > div:has-text("Delivered to Recipient") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5:has-text("Select Location") + div.address-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-7 > address-selection.hydrated > div.control > input#address-input[type="text"][placeholder="Provide Seaport Name"].inputfield.control__input.connect-landing-widget-input',
        "additional_info": {
            "locator": 'css=location-selection.hydrated:has-text("From") + location-selection.hydrated > div.location-selection-wrapper.is-mobile > div:has-text("Delivered to Recipient") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5:has-text("Select Location") + div.address-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-7 > address-selection.hydrated > div.control > input#address-input[type="text"][placeholder="Provide Seaport Name"].inputfield.control__input.connect-landing-widget-input',
            "id": "address-input",
            "class": "inputfield control__input connect-landing-widget-input",
            "type": "text",
            "placeholder": "Provide Seaport Name",
            "tagName": "INPUT",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Provide Seaport Name",
        },
    },
    {
        "index": 32,
        "fixed_locator": 'css=div.feature-stage__feature-wrapper.feature-wrapper--secondary > form[role="search"].tracking-form.tracking-form--secondary.paper.js-tracking-form > p.c3-font-id + fieldset.tracking-form__fields > label.control.tracking-form__input > input[name="refNumber"][type="text"][placeholder="ID Number"].control__input.inputfield',
        "additional_info": {
            "locator": 'css=div.feature-stage__feature-wrapper.feature-wrapper--secondary > form[role="search"].tracking-form.tracking-form--secondary.paper.js-tracking-form > p.c3-font-id + fieldset.tracking-form__fields > label.control.tracking-form__input > input[name="refNumber"][type="text"][placeholder="ID Number"].control__input.inputfield',
            "class": "control__input inputfield",
            "name": "refNumber",
            "type": "text",
            "placeholder": "ID Number",
            "tagName": "INPUT",
            "parentElement.tagName": "LABEL",
            "parentElement.innerText": "ID Number",
        },
    },
    {
        "index": 33,
        "fixed_locator": 'css=location-selection.hydrated:has(+ location-selection.hydrated:has-text("To")) > div.location-selection-wrapper.is-mobile > div:has-text("Pickup Required") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5 > country-selection.hydrated > div.control > div.dropdown-listbox.dropdown-listbox--single > div.dropdown-listbox__placeholder.control__label + div.dropdown-listbox__sizer > div.dropdown-listbox__backdrop > div.dropdown-listbox__select > div.dropdown-listbox__head > div.dropdown-listbox__select-content + button[type="button"].dropdown-listbox__dropdown-button.connect-landing-widget-arrow-button',
        "additional_info": {
            "locator": 'css=location-selection.hydrated:has(+ location-selection.hydrated:has-text("To")) > div.location-selection-wrapper.is-mobile > div:has-text("Pickup Required") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5 > country-selection.hydrated > div.control > div.dropdown-listbox.dropdown-listbox--single > div.dropdown-listbox__placeholder.control__label + div.dropdown-listbox__sizer > div.dropdown-listbox__backdrop > div.dropdown-listbox__select > div.dropdown-listbox__head > div.dropdown-listbox__select-content + button[type="button"].dropdown-listbox__dropdown-button.connect-landing-widget-arrow-button',
            "class": "dropdown-listbox__dropdown-button connect-landing-widget-arrow-button",
            "type": "button",
            "tagName": "BUTTON",
            "childElementCount": 1,
            "parentElement.tagName": "DIV",
        },
    },
    {
        "index": 35,
        "fixed_locator": 'css=location-selection.hydrated:has-text("From") + location-selection.hydrated > div.location-selection-wrapper.is-mobile > div:has-text("Delivered to Recipient") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5 > country-selection.hydrated > div.control > div.dropdown-listbox.dropdown-listbox--single > div.dropdown-listbox__placeholder.control__label + div.dropdown-listbox__sizer > div.dropdown-listbox__backdrop > div.dropdown-listbox__select > div.dropdown-listbox__head > div.dropdown-listbox__select-content + button[type="button"].dropdown-listbox__dropdown-button.connect-landing-widget-arrow-button',
        "additional_info": {
            "locator": 'css=location-selection.hydrated:has-text("From") + location-selection.hydrated > div.location-selection-wrapper.is-mobile > div:has-text("Delivered to Recipient") + div.locations.form-grid > div.country-selection.form-grid__item.form-grid__item--xs-12.form-grid__item--m-5 > country-selection.hydrated > div.control > div.dropdown-listbox.dropdown-listbox--single > div.dropdown-listbox__placeholder.control__label + div.dropdown-listbox__sizer > div.dropdown-listbox__backdrop > div.dropdown-listbox__select > div.dropdown-listbox__head > div.dropdown-listbox__select-content + button[type="button"].dropdown-listbox__dropdown-button.connect-landing-widget-arrow-button',
            "class": "dropdown-listbox__dropdown-button connect-landing-widget-arrow-button",
            "type": "button",
            "tagName": "BUTTON",
            "childElementCount": 1,
            "parentElement.tagName": "DIV",
        },
    },
    {
        "index": 37,
        "fixed_locator": 'css=button.btn.btn--primary:text("Get a spot offer")',
        "additional_info": {
            "locator": 'css=button.btn.btn--primary:text("Get a spot offer")',
            "class": "btn btn--primary",
            "tagName": "BUTTON",
            "innerText": "Get a spot offer",
            "parentElement.tagName": "DIV",
            "parentElement.innerText": "Get a spot offer",
        },
    },
    {
        "index": 38,
        "fixed_locator": 'css=div.feature-stage__feature-wrapper.feature-wrapper--secondary > form[role="search"].tracking-form.tracking-form--secondary.paper.js-tracking-form > p.c3-font-id + fieldset.tracking-form__fields > label.control.tracking-form__input:has-text("ID Number") + button.tracking-form__button.btn.btn--primary',
        "additional_info": {
            "locator": 'css=div.feature-stage__feature-wrapper.feature-wrapper--secondary > form[role="search"].tracking-form.tracking-form--secondary.paper.js-tracking-form > p.c3-font-id + fieldset.tracking-form__fields > label.control.tracking-form__input:has-text("ID Number") + button.tracking-form__button.btn.btn--primary',
            "class": "tracking-form__button btn btn--primary",
            "tagName": "BUTTON",
            "innerText": "Track",
            "parentElement.tagName": "FIELDSET",
            "parentElement.innerText": "ID NumbernTrack",
        },
    },
    {
        "index": 39,
        "fixed_locator": "css=button#tablist-tab-850280-850276",
        "additional_info": {
            "locator": "css=button#tablist-tab-850280-850276",
            "id": "tablist-tab-850280-850276",
            "class": "js-tablist__tab tablist__tab c3-font-id tablist__tab--selected",
            "role": "tab",
            "tagName": "BUTTON",
            "innerText": "All-in-one platform",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "All-in-one platform",
        },
    },
    {
        "index": 40,
        "fixed_locator": "css=button#tablist-tab-850280-850282",
        "additional_info": {
            "locator": "css=button#tablist-tab-850280-850282",
            "id": "tablist-tab-850280-850282",
            "class": "js-tablist__tab tablist__tab ",
            "role": "tab",
            "tagName": "BUTTON",
            "innerText": "Easy-to-use interface",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "Easy-to-use interface",
        },
    },
    {
        "index": 41,
        "fixed_locator": "css=button#tablist-tab-850280-850278",
        "additional_info": {
            "locator": "css=button#tablist-tab-850280-850278",
            "id": "tablist-tab-850280-850278",
            "class": "js-tablist__tab tablist__tab ",
            "role": "tab",
            "tagName": "BUTTON",
            "innerText": "24/7 service",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "24/7 service",
        },
    },
    {
        "index": 42,
        "fixed_locator": "css=button#tablist-tab-850280-850284",
        "additional_info": {
            "locator": "css=button#tablist-tab-850280-850284",
            "id": "tablist-tab-850280-850284",
            "class": "js-tablist__tab tablist__tab ",
            "role": "tab",
            "tagName": "BUTTON",
            "innerText": "Personalized dashboard",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "Personalized dashboard",
        },
    },
    {
        "index": 43,
        "fixed_locator": "css=button#tablist-tab-850280-850286",
        "additional_info": {
            "locator": "css=button#tablist-tab-850280-850286",
            "id": "tablist-tab-850280-850286",
            "class": "js-tablist__tab tablist__tab ",
            "role": "tab",
            "tagName": "BUTTON",
            "innerText": "All your shipments at a glance",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "All your shipments at a glance",
        },
    },
    {
        "index": 44,
        "fixed_locator": "css=button#tablist-tab-850280-850288",
        "additional_info": {
            "locator": "css=button#tablist-tab-850280-850288",
            "id": "tablist-tab-850280-850288",
            "class": "js-tablist__tab tablist__tab ",
            "role": "tab",
            "tagName": "BUTTON",
            "innerText": "Quick access to all services",
            "parentElement.tagName": "LI",
            "parentElement.innerText": "Quick access to all services",
        },
    },
]

def filter_dict_list_with_fuzz(dict_list, defined_value, threshold = 50):
    filtered_items = []
    
    for item in dict_list:
        for key, value in item["additional_info"].items():
            if isinstance(value, str):
                score = fuzz.ratio(value, defined_value)
                if score > threshold:
                    filtered_items.append(item)
                    break  # No need to check other keys if one already matches
    return filtered_items

defined_value = "Ocean"

# Filter items based on similarity in "innerText"
# filtered_items = [
#     item for item in dict_list
#     if "innerText" in item["additional_info"] and fuzz.ratio(item["additional_info"]["innerText"], defined_value) > 50
# ]


filtered_items = filter_dict_list_with_fuzz(dict_list, defined_value)

print(filtered_items)

