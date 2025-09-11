from fastapi import FastAPI, Request, Header, Response, BackgroundTasks
import re
import string
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, CallbackQuery
from datetime import datetime, timedelta, timezone
from fastapi.responses import HTMLResponse
from typing import Dict, List
import telegram
import random
import string
import traceback
import json
from urllib.parse import urlparse, parse_qs, urlencode, quote
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from fastapi.templating import Jinja2Templates
import string
import noj as noj
import Fastbot as f
from openai import OpenAI
import aioboto3
from io import BytesIO
import qrcode
from PIL import Image, ImageDraw, ImageFont
import f_validate as f_val
import stripe
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
debugging = False #set to true to print all print statements for debugging

# Token (Define all API tokens/credentials here) ___________
uri = "mongodb+srv://ticketit.jej2z.mongodb.net/?authSource=%24external&authMechanism=MONGODB-X509&retryWrites=true&w=majority&appName=TicketIT"
bot = None
stripe.api_key = os.environ['stripe_key']
ai_key = os.environ["OPENAI_API_KEY"]

app = FastAPI()
mongo = MongoClient(uri,
                     tls=True,
                     tlsCertificateKeyFile='nm_db.pem')
ticketit_db = mongo['Ticketit']
users = ticketit_db['Users']
tickets = ticketit_db['Tickets']
boughttickets = ticketit_db['Bought_Tickets']
clients = ticketit_db['Clients']
statistics = ticketit_db['Statistics']

templates = Jinja2Templates(directory="templates")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Validate(BaseModel):
    response: bool
    context: dict

# Pre-defined telegram function: ________
async def update_info_payload(chat_id, event_id, key, pair):
    users.update_one({"sid.telegram": chat_id}, {"$set": {f"client_customer_relation.{event_id}.info_payload.{key}": pair}})

async def info_payload_reset(chat_id, event_id):
    users.update_one({"sid.telegram": chat_id}, {"$set": {f"client_customer_relation.{event_id}.info_payload": {}}})

async def send_text(chat_id, message_text):
    reply_markup = ReplyKeyboardRemove()
    await bot.send_message(chat_id, message_text, parse_mode=telegram.constants.ParseMode.HTML, disable_web_page_preview=True, reply_markup=reply_markup)

async def send_text_with_back(chat_id, message_text, context = {}, o1 = [], o2 = []):
    state = context.get('state', None)
    options = ["⏪"]
    options_data = ["previous"]

    if state != 'confirmation':
        if len(o1) > 0:
            await send_options_buttons(chat_id, message_text, o1 + options, o2 + options_data)
        else:
            await send_options_buttons(chat_id, message_text, options, options_data)
    else:
        if len(o1) > 0:
            await send_options_buttons(chat_id, message_text, o1, o2)
        else:
            await send_text(chat_id, message_text)

async def delete_message(chat_id, message_id):
    await bot.delete_message(chat_id=chat_id, message_id=message_id)

async def update_state_client(chat_id, event_id, conversation, stage):
    users.update_one(
        {"sid.telegram": chat_id},
        {"$set": {f"client_customer_relation.{event_id}.state": [conversation, stage]}}
    )

async def send_options_buttons(chat_id, text, options, options_data):
    buttons = []
    #options and options_data needs to be the same length
    x = 0
    for option in options:
        buttons.append([InlineKeyboardButton(text=option, callback_data=options_data[x])])
        x += 1
    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.HTML, disable_web_page_preview=True)

async def send_text_with_url(chat_id, text, url, url_text):
    buttons = [[InlineKeyboardButton(text=url_text, url=url)]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.HTML, disable_web_page_preview=True) 

async def send_image_with_caption(chat_id, image_url, caption):
    await bot.send_photo(chat_id=chat_id, photo=image_url, caption=caption, parse_mode=telegram.constants.ParseMode.HTML)

async def printer(message, debug):
    if debug == True:
        print(message)
    return {"status": "ok"}

async def reset_all(context:dict):
    chat_id = context['chat_id']
    event_id = context['event_id']

    object = {
    "info_payload": {},
    "state": ["/start", 0],
    "validator": ["any", []],
    "payload_collector": None,
    }   
    users.update_one({'sid.telegram': chat_id}, {'$set': {f'client_customer_relation.{event_id}': object}})
    users.update_one({'sid.telegram': chat_id}, {'$set': {'profile.flag': False}})
    await expire_stripe_checkout_session_from_session_id(chat_id, event_id)
    return True

# Pre-declared TicketIT functions: ________
def TextToDate(prompt):
    client = OpenAI(api_key = ai_key)
    custom_functions = [
        {
            "type": "function",
            "function": {
                'name': 'Extract_Date_Components',
                'description': 'Extracts day, month, and year from a user inputted date in (MM DD YYYY) format',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'day': {
                            'type': 'string',
                            'description': 'The day of the month in numeric form'
                        },
                        'month': {
                            'type': 'string',
                            'description': 'The month in numeric form'
                        },
                        'year': {
                            'type': 'string',
                            'description': 'The year'
                        }
                    },
                    "required": ["day", "month", "year"]
                }
            }
        }
    ]
    try:
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': prompt}],
            tools=custom_functions,
            tool_choice="auto",
        )
        arguments_json = response.choices[0].message.tool_calls[0].function.arguments
        output = json.loads(arguments_json)
        

        try:
            day = int(output['day'])
            month = int(output['month'])
            year = int(output['year'])

            datetimeObject = datetime.strptime(f"{year}-{month:02d}-{day:02d}", "%Y-%m-%d")
            return {'status': True, 'day': day, 'month': month, 'year': year, 'datetimeObject': datetimeObject}
        except Exception as e:
            print(e)
            return {'status': False, 'reason': "Invalid date format. Please enter the date in (DD MMM YYYY) format (e.g. 1 Jan 2022)", 'datetimeObect': None}
    
    except Exception as e:
        return {'status': False, 'reason': "Invalid date format. Please enter the date in (DD MMM YYYY) format (e.g. 1 Jan 2022)"}

async def generateTicket(uuid: str, ticketnumber: int, name: str, filename: str, eventname: str) -> str:
    
    session = aioboto3.Session()

    async with session.client(
        'lambda',
        aws_access_key_id=os.environ['ACCESS_KEY_LAMBDA'],
        aws_secret_access_key=os.environ['SECRET_KEY_LAMBDA'],
        region_name=os.environ['REGION_LAMBDA']
    ) as lambdaFn:
        
        event = {
            "uuid": uuid,
            "ticket_number": ticketnumber,
            "name": name,
            "eventName": eventname,
            "filename": filename,
        }
        
        print(event)

        response = await lambdaFn.invoke(
            FunctionName='TicketITQrGen',
            InvocationType='RequestResponse',  # Use 'Event' for true async execution
            Payload=json.dumps(event)
        )

        response_payload = json.loads(await response['Payload'].read())
        if response['StatusCode'] == 400:
            raise Exception("Paremeters input into lambda function are incorrect")
        print(response_payload)
        return response_payload['body']['qr_url']

async def process_payment_async(amount, stripe_id, bookingID, context: dict):
    user = context['user']
    chat_id = context['chat_id']
    info_payload = context['info_payload']
    event_id = context['event_id']
    ticket_name = context['info_payload']['collecttickettype'] # 'Phase 1', 'Phase 2', 'Early Bird'
    eventname = context['client']['events'][event_id]['event_name']
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    urlArray = []
    # Now, take all the information needed from the info_payload and add it to the transactions attribute in the client document
    transaction = {
        'timestamp': timestamp,
        'stripe_id': stripe_id,
        'client_id' : context['client_id'],
        'event_id': event_id,
        'ticket_type': ticket_name,
        'qty': int(info_payload['finalqty']),
        'payment_method': 'paynow',
        'amount': amount,
        'tickets': []
    }
    # Depending on the qty, time to generate the tickets and it's relevant attributes

    for i in range(int(info_payload['finalqty'])):
        QR_Ref = f"{''.join(random.choices(string.ascii_uppercase, k=8))}" #this is how we link a transaction to a ticket
        QR_secret = f"{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        try: 
            url = await generateTicket(QR_secret, i + 1, ticket_name, QR_Ref, eventname)
        except Exception as e:
            print(f"Error generating QR code: {e}")
            return {"status": "400", "reason": "An error occurred while generating the QR code. Please try again later"}
        
        ticket_metainfo = {
            's3': url,
            'QR_secret': QR_secret,
            'ticketID': QR_Ref,
            'ticket_ref_tag' : f"{context['client_id']}.{event_id}.{ticket_name}", #ticket_id is for internal use. It is a unique identifier for each ticket - '0001.0001.earlybird' for example
            'inside': False,
        }
        urlArray.append({QR_Ref:url}) #creating an array of ticketid : url pairs to make sendTickets faster and only send tix for this event. To invoke this faster method, set type to 2 in sendTickets parameter
        boughttickets.insert_one(ticket_metainfo) #insert into the bought tickets collection that expires after event date
        transaction['tickets'].append({QR_Ref:url})
    users.update_one({'_id': context['user']['_id']}, {"$set": {f"transactions.{bookingID}": transaction}}) 
    context['user']['transactions'][bookingID] = transaction

    tickets.update_one(
        {"event_id": event_id, "ticket_name": ticket_name},
        {"$inc": {"qty.paynow": int(transaction['qty']), "qty.quota": -int(transaction['qty'])}}
    )
    context['urlArray'] = urlArray
    await f.sendTickets(event_id, context, type=2)
    return transaction

async def sendTickets(eventid, context, type=1): #sends all active tickets to user for a certain event_id (type 1) or booking id (type 2)
        chat_id = context['chat_id']
        user_transactions = context['user']['transactions']

        if type == 2: #if type 2, url can be obtained directly from context['urlArray']
            print(context['urlArray'])
            for items in context['urlArray']:
                for ticketid, url in items.items():
                    await f.send_image_with_caption(chat_id, url, f"<b>Ticket ID:</b> {ticketid}")
            return
                
        for transaction, value in user_transactions.items():# Send the tickets to the user. This is for type 1, where the user wants to see all tickets for an event in /viewtickets
            if value['event_id'] == eventid:
                for item in value['tickets']:
                    for ticketid, url in item.items():
                        await f.send_image_with_caption(chat_id, url, f"<b>Ticket ID:</b> {ticketid}")

async def create_checkout_session(ticket_name: str, cost_of_tickets: float, convenience_fee: float, user_id: str, qty: int, event_id: str, telegram_token: str, bookingID :str, payment_methods = ['card'], discount = 0.0):
    if discount > 0:
        try: 
            coupon = stripe.Coupon.create(
                amount_off=int(discount * 100), #need to test if this works when discount is 0
                currency='sgd',
                duration='once',
                max_redemptions=1,
            )
            coupon = coupon.id
        except Exception as e:
            print(f"Error creating coupon: {e}")

        try:
            session = stripe.checkout.Session.create(
            payment_method_types = payment_methods,
            line_items=[
                {
                    'price_data': {
                        'currency': 'sgd',
                        'product_data': {
                            'name': ticket_name,
                        },
                        'unit_amount': int(cost_of_tickets * 100),  
                    },
                    'quantity': qty,
                },
                {
                    'price_data': {
                        'currency': 'sgd',
                        'product_data': {
                            'name': 'Convenience Fee',
                        },
                        'unit_amount': int(convenience_fee * 100),
                    },
                    'quantity': 1,
                } 
            ],
            discounts=[
                {
                    'coupon': coupon,
                },
            ],
            mode='payment',
            client_reference_id = user_id,
            success_url='https://ladesi-4f55f363a71e.herokuapp.com/payment_confirmation', #will change this to a proper url
            metadata={
                'event_id': event_id,
                'telegram_token': telegram_token,
                'bookingID' : bookingID
            },
            payment_intent_data = {
                'setup_future_usage' : 'on_session',
            } 
            )
            return session.url, session.id
        except Exception as e:
            print(f"Error creating checkout session: {e}")
            return None
    else:
        try:
            session = stripe.checkout.Session.create(
            payment_method_types = payment_methods,
            line_items=[
                {
                    'price_data': {
                        'currency': 'sgd',
                        'product_data': {
                            'name': ticket_name,
                        },
                        'unit_amount': int(cost_of_tickets * 100),  
                    },
                    'quantity': qty,
                },
                {
                    'price_data': {
                        'currency': 'sgd',
                        'product_data': {
                            'name': 'Convenience Fee',
                        },
                        'unit_amount': int(convenience_fee * 100),
                    },
                    'quantity': 1,
                } 
            ],
            mode='payment',
            client_reference_id = user_id,
            success_url='https://ladesi-4f55f363a71e.herokuapp.com/payment_confirmation', #will change this to a proper url
            metadata={
                'event_id': event_id,
                'telegram_token': telegram_token,
                'bookingID': bookingID
            },
            payment_intent_data = {
                'setup_future_usage' : 'on_session',
            } 
            )
            return session.url, session.id
        except Exception as e:
            print(f"Error creating checkout session: {e}")
            return None

async def expire_stripe_checkout_session_from_session_id(chat_id: int, event_id: str):
    user = users.find_one( {"sid.telegram":chat_id} )
    if user is None:
        raise Exception(f"User not found to delete session for event id {event_id}")
    session_id = user['client_customer_relation'][event_id].get('stripe_session_id', None)
    if session_id is None:
        await f.printer("No session id found", debugging)
        return True
    try:
        await f.printer(f"Expiring session id: {session_id}", debugging)
        stripe.checkout.Session.expire(session_id)
        return True
    except Exception as e:
        return str(e)
        
#noj abstractions: ________
async def handle_state(context): #ideally nothing here should directly refer to noj - only context to keep this function super plug and play
    chat_id = context['chat_id']
    current_state = context['state'] #genesis, awaiting_code, code_auth
    conversation_flow = context['conversation_flow'] # /start, /register
    conversation_stage = context['conversation_stage'] # 0, 1, 2
    handling_fn = context['handling_fn']
    payload_collector = context.get('payload_collector', None)
    state = context['state']
    profile = context['user']['profile'] 
    profile_retrieval_permission = context['user']['profile']['profile_retrieval_permission'] #this is a boolean value that determines if the user has given permission to retrieve their profile

    #previous check -> validation -> payload collection -> handling_fn -> update_state_client

    if context['user_input'] == "previous" and conversation_stage > 0:# Purpose is to go back to the previous state if back option is provided
        await update_state_client(chat_id, context['event_id'], conversation_flow, conversation_stage - 1) #this state should be able to handle the incoming user input
        previous_state = context['conversation_array'][conversation_stage - 2]#this state should be the executable state for which the user wants to change thier input for
        previous_state_fn = await get_handlingfn(f, previous_state)
        await set_payload_collecter(context, previous_state)

        #altering context to go back to previous state. These are the only values tahat need to be changed. Faster than regenerating context
        context['state'] = previous_state
        context['handling_fn'] = previous_state_fn
        context['conversation_stage'] = conversation_stage - 2
        await printer(previous_state_fn, debugging)
        await printer(previous_state, debugging)
        await previous_state_fn(context)
        return {"status": "ok"}
    
    if profile_retrieval_permission == True:
        await printer("Profile retrieval permission granted", debugging)
        await printer("Profil keys are as follows: ", debugging)
        for key in profile.keys():
            await printer(key, debugging)
        if state in profile.keys():
            await printer(f"profile retrieved for {state} ", debugging)
            await update_info_payload(chat_id, context['event_id'], state, profile[state])
            try:
                await incrementEventStats('new/repeat', context['client_id'], context['event_id'], [f"stateFunnel.{state}"])
            except Exception as e:
                await printer(f"Error incrementing event stats for {state}: {e}", debugging)
            await skipstate(context)
            return {"status": "ok"}
        else:
            await printer(f"Profile not retrieved for {state} ", debugging)

    validation_function = getattr(f_val, context['user']['client_customer_relation'][context['event_id']]['validator'][0])  #retireve the correct validation_function from f_validate.py

    try:
        validation_response = await validation_function(context) #this is where the validation happens
    except Exception as e:
        await printer(f"Error in validation function / process: {e}", debugging)
        validation_response = Validate(response=False, context=context)

    if validation_response.response == False: #if the validation fails, the user is prompted to try again.
        custom_error = noj.noj['states'][payload_collector].get('custom_error', "Please enter a valid input!") #we can use payload collector to get the right custom message because the current state would be the next state!
        await send_text(chat_id, custom_error)                                                                 #this works becasue payload collector and validator are always in sync and is listening to the input for the previous state.
        return {"status": "ok"}
    else:
        context = validation_response.context
        await reset_validator(context)
    
    if payload_collector is not None:
        await update_info_payload(chat_id, context['event_id'], payload_collector, context['user_input'])
        context['info_payload'][payload_collector] = context['user_input'] #this will allow us to immediately use the previous value in the current state

    await set_payload_collecter(context, current_state) #always calls set_payload_collecter to store the input of the user on the next state
    await printer(f"Handling function {handling_fn}: started", debugging)

    try: 
        fn_response = await handling_fn(context)
        if current_state in context['client']['events'][context['event_id']]['bot_custom'].get('progress_bar', []):
            await incrementEventStats('new/repeat', context['client_id'], context['event_id'], [f"stateFunnel.{current_state}"])
    except Exception as e:
        await printer(f"Error in handling function / process: {e}", debugging)
        fn_response = False

    await printer(f"Handling function {handling_fn}: executed", debugging)

    if fn_response == False:
        return {"status": "ok"}

    if conversation_stage == len(context['conversation_array']) - 1:
        await reset_all(context)
    else:
        await update_state_client(chat_id, context['event_id'], conversation_flow, conversation_stage + 1)
    
    return {"status": "ok"}

async def get_handlingfn(library, state):
    await printer(f"getting handling function for {state}", debugging)
    handling_fn = noj.noj['states'].get(state, 'custom_fn')
    if handling_fn != 'custom_fn':
        handling_fn = handling_fn.get('handling_fn', 'custom_fn')
    return getattr(library, handling_fn)

async def generate_context(chat_id: int, client:dict, user_input: string, user: dict, library:object):
    await printer('generating context', True)
    active_event = client['active_event']
    cf = user['client_customer_relation'][active_event]['state'][0] #conversation flow = cf ex. /start, /buy
    cs = user['client_customer_relation'][active_event]['state'][1] #conversation stage = cs ex. 0, 1, 2
    conversation_array = user['client_customer_relation'][active_event]['info_payload'].get('conversation_array', ['genesis']) #conversation array for the current conversation
    state = conversation_array[cs] #current state of user - genesis, awaiting_code, code_auth

    if debugging == True:
        print(f"Active event id upon input is: {active_event}")
        print(f"State upon input is: {state}")
        print(f"Conversation stage upon input is: {cs}")
        print(f"Conversation flow upon input is: {cf}")

    context = {
        'chat_id': chat_id, #10 digit number
        'client_id': client['client_id'], 
        'event_id': active_event,
        'user_input': user_input,
        'info_payload': user['client_customer_relation'][active_event]['info_payload'],#full info payload of user from user db
        'state': state, #current state of user - genesis, awaiting_code, code_auth
        'conversation_flow' : cf, # /start, /register
        'conversation_stage' : cs, # 0, 1, 2
        'handling_fn': await get_handlingfn(library, state), #function to handle state
        'user': user, #full user db object in case
        'client': client, #full client db object in case
        'payload_collector': user['client_customer_relation'][active_event].get('payload_collector', None), #payload collector for the next state
        'conversation_array': conversation_array #full conversation array for the current conversation
    }
    await printer("end of context generation", debugging)
    return context
    
async def state_manager(context): #this is a headache. I shouldnt have to find user again here. slows down the process. will fix this later.
    chat_id = context['chat_id']
    user_input = context['user_input']
    state = context['state']
    client = context['client']
    user = context['user']
    cs = context['conversation_stage']
    state = context['state']
    
    if state == "genesis": #special state becuase this routes to other states
        if user_input not in noj.noj['conversations']: #exception handling goes here
            await send_text(chat_id, "Please enter a valid command!")
            return {"status": "ok"}
        else: #if user input is a conversation, routing occurs here
            await f.printer(f'conversation detected: {user_input}', debugging)
            await update_state_client(chat_id, context['event_id'], user_input, 0) #sets the conversation accordingly
            # user = users.find_one({'sid.telegram': chat_id})
            # context = await generate_context(chat_id, context['client'], user_input, user, f) #context needs to be regenerated because of change in state and conversation
            
            user['client_customer_relation'][context['event_id']]['state'] = [context['user_input'], 0]

            if user_input == "/buy":
                state = client['events'][context['event_id']]['event_state_flow'][cs] #can use cs or 0 here
                conversation_array = client['events'][context['event_id']]['event_state_flow']
            else:
                state = noj.noj['conversation_flows'][user_input][0]
                await f.printer(f"the conversation array is: {noj.noj['conversation_flows'][user_input]}", debugging)
                conversation_array = noj.noj['conversation_flows'][user_input]

            context['conversation_array'] = conversation_array
            context['state'] = state
            context['handling_fn'] = await get_handlingfn(f, state)
            await f.printer(f"handling function : {context['handling_fn']}", debugging)
            context['conversation_flow'] = user_input
            
            await update_info_payload(chat_id, context['event_id'], "conversation_array", conversation_array)
            await handle_state(context)
    else:
        if state not in noj.noj['states']:
            await f.printer(f'custom state detected: {state}', debugging)
            handling_fn = context['client']['events'][context['event_id']]['bot_custom']['custom_states'][state].get('handling_fn', 'custom_fn')
            await f.printer(f'custom handling function run: {handling_fn}', debugging)
            handle_fn = await get_handlingfn(f, handling_fn)
            await f.printer(f'fn attribute: {handle_fn}', debugging)
            context['handling_fn'] = handle_fn
        await handle_state(context) #runs the handling fn and updates the state
 
    return {"status": "ok"}

async def set_payload_collecter(context, state):
    users.update_one({"sid.telegram": context['chat_id']}, {"$set": {f"client_customer_relation.{context['event_id']}.payload_collector": state}})

async def empty_payload_collector(context):
    users.update_one({"sid.telegram": context['chat_id']}, {"$set": {f"client_customer_relation.{context['event_id']}.payload_collector": None}})

async def set_validator(context:dict, type:string, values:list):
    users.update_one({"sid.telegram": context['chat_id']}, {"$set": {f"client_customer_relation.{context['event_id']}.validator": [type, values]}})
    #abstraction here is [type, values], type is a string and values is a dependancy array

async def reset_validator(context:dict):
    users.update_one({"sid.telegram": context['chat_id']}, {"$set": {f"client_customer_relation.{context['event_id']}.validator": ["any", []]}})

async def update_profile(context:dict):
    collectable_states = ['collectname', 'collectphonenumber', 'collectemail', 'collectgender', 'collectdob', 'collectrelationshipstatus'] #here are the values that which we want to collect as part of our profile
    chat_id = context['chat_id']
    for key, value in context['info_payload'].items():
        if key in collectable_states:
            users.update_one(
                {"sid.telegram": chat_id},
                {"$set": {f"profile.{key}": value}}
            )

async def print_progress_bar(context:dict):
    progress_bar_full = context['client']['events'][context['event_id']]['bot_custom'].get('progress_bar', None) 
    current_state = context.get('state', None) 

    if progress_bar_full is None or current_state == 'confirmation' or current_state not in progress_bar_full:
        return ""

    total_qns = len(progress_bar_full)
    current_qn = progress_bar_full.index(current_state) + 1
    
    bar = "█" * current_qn + "░" * (total_qns - current_qn)
    progress_bar = f"<i>Question {current_qn} of {total_qns} [{bar}]</i>\n\n" 
    return progress_bar

async def generate_cfm_summary(context:dict):
    dtToText = lambda dt: dt.strftime("%d %B %Y") #converts datetime to text
    cfm = "Here are your details:\n\n"
    info_payload = context['info_payload']
    custom_state = context['client']['events'][context['event_id']]['bot_custom'].get('custom_states', None)
    for key, value in info_payload.items():
        if key.startswith("collect"): #only displays states with collect. keep note of this
            state = noj.noj['states'].get(key, None)
            if state is None:
                field_name = custom_state[key].get('Field_name', 'Missing Field')
            else:
                field_name = state['Field_name']
            if type(value) == datetime:
                value = dtToText(value)
            cfm = cfm + f"{field_name}: {value}" + "\n"
    cfm = cfm + "\nPlease confirm if the details are correct!"
    return cfm

async def skipstate(context:dict):
    chat_id = context['chat_id']
    conversation_flow = context['conversation_flow']
    conversation_stage = context['conversation_stage']
    print(conversation_stage)
    await update_state_client(chat_id, context['event_id'], conversation_flow, conversation_stage + 1)
    user = users.find_one({'sid.telegram': chat_id})
    context = await generate_context(chat_id, context['client'], context['user_input'], user, f)
    await handle_state(context)
    return True

#Statistics Abstracted Functions: ________
async def incrementEventStats(identiy: str, clientID: str, eventID: str, keys: list):
    try:
        increment_dict = {key: 1 for key in keys}
        statistics.update_one({"client_id": clientID, "event_id": eventID}, {"$inc": increment_dict})
        print("incremented stats")
    except Exception as e:
        print(str(e))
        return str(e)
    return {"status": "ok"}

async def appendEventStats(identity:str, clientID: str, eventID: str, keys: list, user: str):
    try:
        statistics.update_one({"client_id": clientID, "event_id": eventID}, {"$addToSet": {key: user for key in keys}})
    except Exception as e:
        print(str(e))
        return str(e)
    return {"status": "ok"}

async def decrementEventStats(clientID: str, eventID: str, keys: list):
    try:
        increment_dict = {key: -1 for key in keys}
        statistics.update_one({"clientID": clientID, "eventID": eventID}, {"$inc": increment_dict})
    except Exception as e:
        print(str(e))
        return str(e)
    return {"status": "ok"}

async def removeEventStats(clientID: str, eventID: str, keys: list, user: str):
    try:
        statistics.update_one({"clientID": clientID, "eventID": eventID}, {"$pull": {key: user for key in keys}})
    except Exception as e:
        print(str(e))
        return str(e)
    return {"status": "ok"}

#noj handling functions: ________
async def genesis(context: dict):
    chat_id = context['chat_id']
    aboutme_text = context['client']['events'][context['event_id']]['bot_custom']['genesis'] #pulls the custom message from the client db
    event_name = context['client']['events'][context['event_id']].get('event_name', 'Event Name goes here') 
    event = context['client']['events'][context['event_id']]['event_start']
    if isinstance(event, datetime):
        date_str = event.strftime("%d %B %Y")  # Format the date part
        time_str = event.strftime("%I:%M %p")  # Format the time part
    settings = f"""
⏱️ <b>Time: {time_str}</b>
📅 <b>Date: {date_str}</b>
📍 <b>Location: {context['client']['events'][context['event_id']]['event_location']}</b>
    """
    returnmsg = f"Welcome to the <b>Official {event_name} Bot</b>!\n{settings}\n<b><u>About Us</u></b>\n{aboutme_text}\n\nClick one of the commands below to get started!"
    await printer(returnmsg, debugging)
    await send_options_buttons(chat_id, returnmsg, ['Buy', 'View Tickets', 'Contact Us'], ['/buy', '/viewtickets', '/contact'])
    return True

async def collecttickettype(context: dict): 
    chat_id = context['chat_id']
    event_id = context['event_id']
    ticket_list = tickets.find({"event_id": event_id})
    tickettypes_names = []
    tickettypes_values = []
    ticket_msg = f"""
    <b>------TICKETS------</b>
    """
    if ticket_list is None:
        await send_text(chat_id, "No tickets found for this event!")
        return False
    
    for ticket in ticket_list:
        ticketstring = f"{ticket['ticket_name']}"
        tickettypes_names.append(ticketstring)
        tickettypes_values.append(ticket['ticket_name'])
        ticket_msg = ticket_msg + f"\n🎟️<b>{ticket['ticket_name']}:</b> ${ticket['price']}"
    
    returnmsg = "Any kind of ticket information goes here. e.g. 5 x Table gets 1 free bottle of champagne!"
    progressbar = await print_progress_bar(context)
    returnmsg = f"{returnmsg}\n\n{ticket_msg}"
    await set_validator(context, "value", tickettypes_values) #to retrieve tickets from new ticket collection based of event_id
    await send_options_buttons(context['chat_id'], progressbar + returnmsg, tickettypes_names, tickettypes_values)
    return True

async def collectname(context: dict):
    progressbar = await print_progress_bar(context)
    msg = context['client']['events'][context['event_id']]['bot_custom'].get('collectname', "what is your name?")
    await send_text_with_back(context['chat_id'], progressbar + msg, context)
    await set_validator(context, "name", []) #leave dependancy array blank because it's not needed. 
    return True                              #In special cases of validation, dependancy can be pulled from db
 
async def collectphonenumber(context):
    progressbar = await print_progress_bar(context)
    client = context['client']
    msg = client['events'][context['event_id']]['bot_custom'].get('collectphonenumber', "what is your phone number?")
    await send_text_with_back(context['chat_id'], progressbar + msg, context, [], [])
    await set_validator(context, "phonenumber", []) #example here, dependancy array can contain country code (like 'sg' or 'uk' to identify type of valid phone numbers)
    return True

async def collectemail(context):
    progressbar = await print_progress_bar(context)
    msg = context['client']['events'][context['event_id']]['bot_custom'].get('collectemail', "what is your email address?")
    await send_text_with_back(context['chat_id'], progressbar + msg, context)
    await set_validator(context, "email", [])
    return True

async def collectgender(context):
    progressbar = await print_progress_bar(context)
    msg = context['client']['events'][context['event_id']]['bot_custom'].get('collectgender', "Please state your gender")
    options = ["Male", "Female", "Other"]
    await send_text_with_back(context['chat_id'], progressbar + msg, context, options, options)
    await set_validator(context, "value", options)
    return True

async def collecthearfrom(context):
    progressbar = await print_progress_bar(context)
    msg = context['client']['events'][context['event_id']]['bot_custom'].get('collecthearfrom', "How did you hear about us?")
    await send_text_with_back(context['chat_id'], progressbar + msg, context)
    return True

async def confirmation(context): #this is an abomination of a state. I will refactor this later
    chat_id = context['chat_id']
    info_payload = context['info_payload'] #contains all fields to show in confirmation

    # sent_cfm_message = context['info_payload'].get('sent_cfm_message', False) #this is to check if the confirmation message has been sent
    # sent_change_options = context['info_payload'].get('sent_change_options', False) #this is to check if the change options have been sent
    # sent_changed_field = context['info_payload'].get('sent_changed_field', False) #this is to check if field has been changed

    user_input = context['user_input']
    custom_state = context['client']['events'][context['event_id']]['bot_custom'].get('custom_states', None)

    message = await generate_cfm_summary(context)
    await send_options_buttons(chat_id, message, ["Looks Good!", "Make a change!"], ["yes", "no"])
    await set_validator(context, 'value', ['yes', 'no'])
    #await update_info_payload(chat_id, context['event_id'], "sent_cfm_message", True)
    return True  
    
    # if sent_cfm_message == True: #this takes place when bot has already sent confirmation message
    #     if user_input.lower() == "yes":
    #         if context['user']['profile']['profile_retrieval_permission'] == False:
    #             await send_options_buttons(chat_id, "Would you like to save your details for a faster checkout for your next event?",['Proceed', "No thanks"], ['proceed', 'no'])
    #             await set_validator(context, 'saveProfile', ['proceed', 'no'])
    #             return True
    #         else: #this else is for the case where user has already given permission to save their profile
    #             await send_text(chat_id, "Thank you for confirming your details!")
    #             await set_validator(context, 'any', [])
    #             users.update_one(
    #                 {"sid.telegram": chat_id},
    #                 {"$unset": {
    #                     f"client_customer_relation.{context['event_id']}.info_payload.sent_cfm_message": "",
    #                     f"client_customer_relation.{context['event_id']}.info_payload.sent_change_options": "",
    #                     f"client_customer_relation.{context['event_id']}.info_payload.sent_changed_field": "",
    #                     f"client_customer_relation.{context['event_id']}.info_payload.field_to_change": ""
    #                 }}
    #             )
    #             await skipstate(context)
    #         return False
    #     elif user_input.lower() == "no": #this else is for the case where user needs to change some information
    #         fields = [key for key in info_payload.keys() if key.startswith("collect")]
    #         fields_to_edit = []
    #         for key, value in info_payload.items():
    #             if key.startswith("collect"):
    #                 state = noj.noj['states'].get(key, None)
    #                 if state is None:
    #                     field_name = custom_state[key].get('Field_name', 'Missing Field')
    #                 else:
    #                     field_name = state['Field_name']
    #                 fields_to_edit.append(field_name)

    #         if sent_change_options == False: #this takes place when bot has not sent the change options yet
    #             await send_options_buttons(chat_id, "Choose the field you would like to edit from the buttons below", fields_to_edit, fields)
    #             await update_info_payload(chat_id, context['event_id'], "sent_change_options", True) #this seems silly but the goal is to let the previous code, send options, to run once
    #             return False
    #         else: #this takes place when bot has sent the change options and is waiting for user input
    #             if sent_changed_field == False: #this takes place when user hasn't replied to the change options witha valid option
    #                 if user_input in fields:
    #                     print(user_input)
    #                     field_to_change_handling_fn = await get_handlingfn(f, user_input)
    #                     print(field_to_change_handling_fn)
    #                     await set_payload_collecter(context, user_input)
    #                     context['payload_collector'] = user_input
    #                     await field_to_change_handling_fn(context)
    #                     await update_info_payload(chat_id, context['event_id'], "field_to_change", user_input)
    #                     await update_info_payload(chat_id, context['event_id'], "sent_changed_field", True)
    #                 else:
    #                     await send_text(chat_id, "Please select from one of the buttons above!")
    #             else:
    #                 validation_function = getattr(f_val, context['user']['client_customer_relation'][context['event_id']]['validator'][0])  #retireve the correct validation_function from f_validate.py
    #                 validation_response = await validation_function(context) #this is where the validation happens
    #                 if validation_response.response == False:
    #                     await send_text(chat_id, validation_response.returnmsg)
    #                     return False
    #                 else:
    #                     field_to_change = info_payload['field_to_change']
    #                     info_payload[field_to_change] = user_input 
    #                     context['info_payload'] = info_payload
    #                     message = await generate_cfm_summary(context)
    #                     await send_options_buttons(chat_id, message, ["Looks Good!", "Make a change!"], ["yes", "no"])
    #                     await reset_validator(context)
    #                     await update_info_payload(chat_id, context['event_id'], info_payload['field_to_change'], user_input) #we can find state to change from payload collector
    #                     users.update_one(
    #                         {"sid.telegram": chat_id},
    #                         {"$set": {
    #                             f"client_customer_relation.{context['event_id']}.info_payload.sent_change_options": False,
    #                             f"client_customer_relation.{context['event_id']}.info_payload.sent_changed_field": False
    #                         }}
    #                     )
    #                     return False  
    #         return False
    #     else:
    #         await send_text(chat_id, "Please select from one of the buttons above!")
    #         return False

async def handleEditConfirmation(context:dict):
    user_input = context['user_input']

    if user_input.lower() == "yes":
        print("Details cfmed. Skipping handleEditConfirmation state") 
        await skipstate(context)
        return False
    else:
        await send_text(context['chat_id'], "Refactoring the code to handle change confirmation details. To change your details, press /cancel to restart the booking process.")
        await skipstate(context)
        return False

async def collectticketqty(context: dict):
    chat_id = context['chat_id']
    max_qty = context['client']['events'][context['event_id']]['max_per_user']
    ticket = tickets.find_one({"event_id": context['event_id'], "ticket_name": context['info_payload']['collecttickettype']})
    ticket_quota = ticket['qty']['quota']
    NoOfTickets:int = ticket['NoOfTickets']
    upper_bound = min(max_qty, ticket_quota) #this is simple logic to check the max number of tickets the user can buy

    if NoOfTickets > 1: #this allows us to sell multiple tickets for the same ticket type.
        await update_info_payload(chat_id, context['event_id'], "finalqty", NoOfTickets)
        await update_info_payload(chat_id, context['event_id'], "packageDeal", True)
        await skipstate(context)
        return False

    await f.printer(f"Max qty: {max_qty}", debugging)
    await f.printer(f"Ticket quota: {ticket_quota}", debugging)
    await f.printer("Upper bound is: " + str(upper_bound), debugging)

    await set_validator(context, "ticketqty", [upper_bound])
    await send_text(chat_id, "How many tickets would you like to purchase? \n\nMaximum Tickets Per User: " + str(upper_bound))
    return True

async def paymentpending(context: dict):
    ticket = tickets.find_one({"event_id": context['event_id'], "ticket_name": context['info_payload']['collecttickettype']})
    chat_id = context['chat_id']
    event_id = context['event_id']
    user_input = context['user_input']
    ticket_qty = int(context['info_payload']['finalqty'])
    packageDeal = context['info_payload'].get('packageDeal', False)
    ticket_cost = float(ticket['price'])

    if packageDeal:
        ticket_cost = float(ticket['price']) / ticket_qty

    total_cost = ticket_cost * ticket_qty
    convenience_fee = total_cost * 0.033
    total_cost += convenience_fee
    voucher = context['info_payload'].get('promocode', None)
    bookingID =  f"{''.join(random.choices(string.ascii_uppercase, k=8))}" #this is shared with the customer so we can identify the transaction!
    discount_text = ""
    discount = 0
    print('check')
    if voucher is not None:
        await f.printer("voucher found", debugging)
        voucher_info =  context['client']['events'][event_id]['vouchers'].get(voucher, None)
        if voucher_info is not None:
            await f.printer(voucher_info, debugging), 
            voucher_type = voucher_info['type']
            discount = int(total_cost * voucher_info['value'] / 100 )if voucher_type == 'percentage' else voucher_info['value']
            f.printer(discount, debugging)
            discount_text = f"<b>Discount:</b> ${discount:.2f}\n"

    msg8 = f"<b>💵 Total Cost Breakdown</b>\n\n<b>Cost of {context['info_payload']['finalqty']} tickets:</b> ${ticket_cost * ticket_qty:.2f}\n<b>Processing Fee:</b> ${convenience_fee:.2f}\n{discount_text}\n<b>Total: ${(total_cost - discount):.2f}</b>\n\n❗️You will receieve your tickets once <b>your payment has been processed.</b> Please click on the button below to proceed!\n\nElse, please press /cancel to restart the booking process."
    checkout_session_url, session_id = await create_checkout_session(ticket['ticket_name'],ticket_cost, convenience_fee, context['user']['_id'], ticket_qty, context['event_id'], context['client']['client_telegram_token'], bookingID, discount=discount)
    await f.send_text_with_url(chat_id, msg8, checkout_session_url, "Proceed to Payment 💰")
    await f.update_info_payload(chat_id, event_id, "bookingID", bookingID)
    await f.update_info_payload(chat_id, event_id, "stripe_session_id", session_id)
    await f.update_info_payload(chat_id, event_id, "stripe_session_url", checkout_session_url)
    return False

async def contact(context:dict):
    contact_info = context['client'].get('client_contact', 'missing contact information')
    chat_id = context['chat_id']
    await send_text(chat_id, f"Contact us at {contact_info}")
    return True

async def viewtickets(context:dict):
    chat_id = context['chat_id']
    await send_text(chat_id, "Here are your tickets for your latest event!")
    event_id = context['event_id']
    await f.sendTickets(event_id, context, type=1)
    return True

async def custom_fn(context:dict):
    progressbar = await print_progress_bar(context)
    print(progressbar)
    chat_id = context['chat_id']
    custom_states = context['client']['events'][context['event_id']]['bot_custom']['custom_states']
    print(custom_states)
    custom_state = custom_states.get(context['state'], None) #we will find similar logic throughout the code
    print(custom_state)
    if custom_state is None:
        custom_state = custom_states.get(context['payload_collector'], None)
    custom_txt = custom_state.get('custom_text', "Field Message goes here")  #this is to constantly check if the state is custom or fixed
    buttons = custom_state.get('buttons', None)
    if buttons is None or buttons == []:
        await send_text_with_back(chat_id, progressbar + custom_txt, context)
        await set_validator(context, "any", [])
        return True
    else:
        await send_options_buttons(chat_id, progressbar + custom_txt, buttons, buttons)
        await set_validator(context, "value", buttons)
        return True

async def promocode(context: dict):
    chat_id = context['chat_id']
    user_input = context['user_input']
    await send_options_buttons(chat_id, "Please enter your promo code!", ["I don't have a voucher..."], ["pass"])
    await set_validator(context, "voucher", []) #uses new voucher f_validation method
    return True

async def retrieveprofile(context: dict):
    chat_id = context['chat_id']
    profile = context['user']['profile']
    custom_states = context['client']['events'][context['event_id']]['bot_custom']['custom_states']
    flag = profile['flag']
    user_input = context['user_input']
    msg = 'We have retrieved your info from your profile. Would you like to proceed with this information?\n\n'
    is_old_user = False
    dtToText = lambda dt: dt.strftime("%d %B %Y") #converts datetime to text

    for key, value in profile.items():
        if key.startswith("collect"):
            is_old_user = True
            break

    if not is_old_user:
        await skipstate(context)
        return False

    if flag == False:
        for key, value in profile.items():
            if key == 'profile_retrieval_permission' or key == 'flag':
                continue
            if key in noj.noj['states']:
                if type(value) == datetime:
                    value = dtToText(value)
                msg = msg + f"<b>{noj.noj['states'][key]["Field_name"]}:</b> {value}\n" #we can pull field names for pre defined states from noj
            else:
                msg = msg + f"<b>{custom_states[key]['Field_name']}:</b> {value}\n"
        
        msg = msg + "\nIf you would like to delete your information, please view settings by pressing /settings!"
        await send_options_buttons(chat_id, msg, ["Yes!", "I have different information!"], ["yes", "no"])
        users.update_one({"sid.telegram": chat_id}, {"$set": {"profile.flag": True}})
        await set_validator(context, "value", ["yes", "no"])
        return False
    else:
        if user_input == "yes":
            await send_text(chat_id, "Good man. Prefilling all info now!")
            users.update_one({"sid.telegram": chat_id}, {"$set": {"profile.profile_retrieval_permission": True}})
            await skipstate(context)
            return False
        else:
            await send_text(chat_id, "Somebody likes taking things slow :). No Worries! Let's start from the top!")
            users.update_one({"sid.telegram": chat_id}, {"$set": {"profile.profile_retrieval_permission": False}})
            await skipstate(context)
            return False
    
async def settings(context:dict):
    chat_id = context['chat_id']
    await send_options_buttons(chat_id, "Welcome to settings! Here are the settings loooooser", ['profile', 'notifications'], ['profile', 'notifications'])
    return True

async def saveprofile(context: dict):
    chat_id = context['chat_id']
    user_input = context['user_input']
    profileRetrievalPermission = context['user']['profile']['profile_retrieval_permission']
    flag :bool = context['info_payload'].get('saveprofileFlag', False) #this is a separate flag from profile flag
    profile = context['user']['profile']
    profileFlag = profile['flag']
    clientQuestions = context['client']['events'][context['event_id']]['bot_custom']['progress_bar']
    
    

    if not flag: 
        for i in clientQuestions:
            if i not in profile.keys() and i != 'profile_retrieval_permission' and i != 'flag':
                profileFlag = False

        if not profileFlag:
            await send_options_buttons(chat_id, "Would you like to save your details for a faster checkout for your next event?",['Proceed', "No thanks"], ['proceed', 'no'])
            await set_validator(context, 'saveProfile', ['proceed', 'no'])
            await update_info_payload(chat_id, context['event_id'], "saveprofileFlag", True)
            return False
        
        if profileFlag:
            await skipstate(context)
            return False
    
    if user_input == 'proceed':
        await update_profile(context)
        await send_text(chat_id, "Your profile has been saved!")
        users.update_one({"sid.telegram": chat_id}, {"$set": {"profile.profile_retrieval_permission": True}})
        await skipstate(context)
        return False
    else:
        await send_text(chat_id, "Somebody has trust issues...")
        users.update_one({"sid.telegram": chat_id}, {"$set": {"profile.profile_retrieval_permission": False}})
        await skipstate(context)
        return False

async def collectrelationshipstatus(context: dict):
    chat_id = context['chat_id']
    relationTypes = ['Single and Ready to Mingle', 'Married!', "It's Complicated ..."]
    msg = context['client']['events'][context['event_id']]['bot_custom'].get('collectrelationshipstatus', "We don't mean to pry... but are you availale???")
    await f.send_text_with_back(chat_id, msg, context, relationTypes, relationTypes)
    await f.set_validator(context, "value", relationTypes)
    return True

async def collectdob(context:dict):
    chat_id = context['chat_id']
    msg = context['client']['events'][context['event_id']]['bot_custom'].get('collectdob', "Please enter your date of birth in the following format: 10 October 2002")
    await send_text_with_back(chat_id, msg)
    await f.set_validator(context, "dob", [])
    return True

