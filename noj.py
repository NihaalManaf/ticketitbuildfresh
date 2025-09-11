noj = {
    "conversations" : ["/start", "/info", '/viewtickets', '/buy', '/contact', '/settings'], #add routing conversation starter here

    "conversation_flows" : { #add conversation flow here by starting with the conversation starter and listing the states in the conversation
        "/start" : ['genesis'],
        "/info" : ['info'],
        "/viewtickets" : ['viewtickets'],
        "/contact" : ['contact'],
        "/settings" : ['settings']
    }, 

    "states" : { #add states here following the format below. The handling_fn name must be the name of the function in the library and preferabbly the state name
        "genesis" : {   
            "Field_name" : None,
            'info_payload_update' : {},
            'handling_fn' : 'genesis',
        },
        "info" : {
            "Field_name" : None,
            'info_payload_update' : {},
            'handling_fn' : 'info',
        },
        "viewtickets" : {
            "Field_name" : None,
            'info_payload_update' : {},
            'handling_fn' : 'viewtickets',
        },
        "custom_route" : {
            "Field_name" : None,
            'info_payload_update' : {},
            'handling_fn' : 'custom_route', 
        },
        "collecttickettype" : {
            "Field_name" : "Ticket Type",
            'info_payload_update' : {},
            'custom_error' : "Please select a valid ticket type!",
            'handling_fn' : 'collecttickettype',
        },
        "collectname" : {
            "Field_name" : "Name", 
            'info_payload_update' : {},
            'custom_error' : "Please enter a valid name!",
            'handling_fn' : 'collectname',
        },
        "collectphonenumber" : {
            "Field_name" : "Phone Number",
            'info_payload_update' : {},
            'custom_error' : "Please enter a valid phone number!",
            'handling_fn' : 'collectphonenumber',
        },
        "collectemail" : {
            "Field_name" : "Email",
            'info_payload_update' : {},
            'custom_error' : "Please enter a valid email address!",
            'handling_fn' : 'collectemail',
        },
        "collectgender" : {
            "Field_name" : "Gender",
            'info_payload_update' : {},
            'custom_error' : "Please select from one of the options provided!",
            'handling_fn' : 'collectgender',
        },
        "collecthearfrom" : {
            "Field_name": "How you heard of us",
            'info_payload_update' : {},
            'custom_error' : "Please enter a valid response!",
            'handling_fn' : 'collecthearfrom',
        },
        "confirmation" : {
            "Field_name" : None,
            'info_payload_update' : {},
            'custom_error' : "Please select from one of the options provided!",
            'handling_fn' : 'confirmation',
        },
        "payment" : {
            "Field_name" : None,
            'info_payload_update' : {},
            'custom_error' : "Please click on the link to make payment or press /cancel to cancel this process!",
            'handling_fn' : 'paymentpending',
        },
        "collectticketqty" : {
            "Field_name" : "Ticket Quantity",
            'info_payload_update' : {},
            'custom_error' : "Please enter a valid ticket quantity!",
            'handling_fn' : 'collectticketqty',
        },
        "retrieveprofile" : {
            "Field_name" : None,
            'info_payload_update' : {},
            'handling_fn' : 'retrieveprofile',
        },
        'contact' : {
            'Field_name' : None,
            'info_payload_update' : {},
            'handling_fn' : 'contact',
        },
        'promocode' : {
            'Field_name' : None,
            'info_payload_update' : {},
            'custom_error' : "This is an invalid/expired voucher code! If you don't have a valid voucher code, press the button above!",
            'handling_fn' : 'promocode',
        },
        'retrieveprofile' : {
            'Field_name' : None,
            'info_payload_update' : {},
            'handling_fn' : 'retrieveprofile',
        },
        'settings' : {
            'Field_name' : None,
            'info_payload_update' : {},
            'handling_fn' : 'settings'
         },
        'saveprofile' : {
            'Field_name' : None,
            'info_payload_update' : {},
            'handling_fn' : 'saveprofile'
        },
        'collectrelationshipstatus' : {
            'Field_name' : 'Relationship Status',
            'info_payload_update' : {},
            'custom_error' : "Lai Lai, don't be shy! Please select from one of the options provided!",
            'handling_fn' : 'collectrelationshipstatus'
            },
        'collectdob' : {
            'Field_name' : 'Date of Birth',
            'info_payload_update' : {},
            'custom_error' :"Invalid date format. Please enter the date in (DD MMM YYYY) format (e.g. 1 Jan 2022)",
            'handling_fn' : 'collectdob'
            },
        'handleEditConfirmation' : {
            'Field_name' : None,
            'info_payload_update' : {},
            'handling_fn' : 'handleEditConfirmation'
            },
    }
}


# all states must be found in in a conversation. A state can be in multiple conversations but a conversation must have at least one state.

