{
    "_id": "AJHSDMXUSKSDGHSLCYSH", #16 char random generated ID
    "sid": {
        "telegram": chat_id #chat_id from the user telegram. an object is used here to eventually allow for other platforms
    },
    "client_customer_relation": {
        "client_id": {
            "events": {
                "event_id": {
                    "transactions": [
                        {
                            "booking_id": "DJAKDEBS",
                            "payment_processor_id": "",
                            "ticket_type": "",
                            "quantity": "",
                            "payment_method": "",
                            "amount": "",
                            "processing_fee": "",
                            "promotions": [],
                            "tickets": [
                                {
                                    "data": "",
                                    "qr_secret": "",
                                    "qr_ref": "",
                                    "validity": false
                                }
                            ]
                        }
                    ]
                }
            },
            "info_payload": {},
            "state": ["/start", 0]
        }
    },
    "profile": {
        "name": "Nihaal Manaf",
        "age": 21,
        "country": "Singapore",
        "gender": "Male"
    }
}

{
  "_id": { "$oid": "6759697aad8b1b678c993710" },
  "client_id": "0001",
  "client_telegram_token": "7387009399:AAGcRsrD0p2PnjhxYflL1ZdNwUmc4MJxw9E",
  "events": {
    "event_id": "0001",
    "event_state_flow": [
      "collecttickettype",
      "collectname",
      "collectphonenumber",
      "collectgender",
      "collecthearfrom",
      "confirmation",
      "collectticketqty",
      "paymentpending",
      "paymentsuccess"
    ],
    "bot_custom": {
      "genesis": "/start goes here",
      "info": "/info message goes here",
      "collecttickettype": "collect tickettype message goes here. include ticket qty [this portion will be programmatically added]"
    },
    "event_details": {
      "tickets": [
        {
          "name": "Phase 1",
          "qty": {
            "quota": 300,
            "paynow": 0,
            "creditcard": 10
          },
          "price": 49.99,
          "currency": "SGD"
        },
        {
          "name": "Phase 2",
          "qty": {
            "quota": 300,
            "paynow": 0,
            "creditcard": 0
          },
          "price": 89.99,
          "currency": "SGD"
        }
      ],
      "max_per_transaction": 10
    }
  },
  "client_contact": {},
  "scanner_password": "",
  "statistics": {}
}

{"_id":{"$oid":"6759697aad8b1b678c993710"},"client_id":"0001","client_telegram_token":"7387009399:AAGcRsrD0p2PnjhxYflL1ZdNwUmc4MJxw9E","events":{"event_id":"0001","event_state_flow":["collecttickettype","collectname","collectphonenumber","collectgender","collecthearfrom","confirmation","collectticketqty","paymentpending","paymentsuccess"],"bot_custom":{"genesis":"/start goes here","info":"/info message goes here","collecttickettype":"collect tickettype message goes here. include ticket qty [this portion will be programmtically added]"},"event_details":{"tickets":""}},"client_contact":{},"scanner_password":"","statistics":{"no_of_users":{"$numberInt":"0"},"no_of_tickets_sold":{"$numberInt":"0"},"avg_duration":{"$numberInt":"0"},"customers_no_data":{"$numberInt":"0"},"customers_with_data":{"$numberInt":"0"}}}