import re
from pydantic import BaseModel
import Fastbot as f
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
from openai import OpenAI
import os

uri = "mongodb+srv://ticketit.jej2z.mongodb.net/?authSource=%24external&authMechanism=MONGODB-X509&retryWrites=true&w=majority&appName=TicketIT"
mongo = MongoClient(uri,
                     tls=True,
                     tlsCertificateKeyFile='nm_db.pem')

ticketit_db = mongo['Ticketit']
users = ticketit_db['Users']
clients = ticketit_db['Clients']
tickets = ticketit_db['Tickets']

debugging = False

class Validate(BaseModel):
    response: bool
    context: dict

async def any(context: dict):
    return Validate(response=True, context=context)

async def value(context: dict):
    user_input = context['user_input'] # compare user input to value in validator object in mongodb
    validate_values = context['user']['client_customer_relation'][context['event_id']]['validator'][1]

    if str(user_input) in validate_values:
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)
    
async def ticketqty(context: dict):
    user_input = context['user_input'] # compare user input to value in validator object in mongodb
    validate_values = context['user']['client_customer_relation'][context['event_id']]['validator'][1]
    upperBound = int(validate_values[0])

    if int(user_input) <= upperBound and int(user_input) > 0:
        await f.update_info_payload(context['chat_id'], context['event_id'], 'finalqty', user_input)
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)

async def phonenumber(context: dict):
    pattern = re.compile(r'^\+?1?\d{8,15}$')
    if pattern.match(context['user_input']):
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)
    
async def email(context: dict):
    pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    if pattern.match(context['user_input']):
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)
    
async def name(context: dict):
    pattern = re.compile(r'^[a-zA-Z ]+$')
    if pattern.match(context['user_input']):
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)
    
async def state(context: dict):
    validate_state = context['user']['client_customer_relation'][context['event_id']]['validator'][1]
    if validate_state == True:
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)
    
async def saveProfile(context: dict):
    userinput = context['user_input']
    if userinput == "proceed":
        if context['user']['profile'] is None:
            await f.send_text(context['chat_id'], "Profile saved successfully!")
        users.update_one({'sid.telegram': context['chat_id']}, {'$set': {'profile.profile_retrieval_permission': True}})
        await f.update_profile(context)
        return Validate(response=True, context = context)
    elif userinput == "no":
        await f.send_text(context['chat_id'], "Somebody has trust issues ...")
        return Validate(response=True, context=context)
    else:
        return Validate(response=False, context=context)
    
async def voucher(context:dict):
    await f.printer("Voucher validation begins here", debugging)
    voucher_input = context['user_input']
    await f.printer(f"The voucher input is: {voucher_input}", debugging)
    vouchers = context['client']['events'][context['event_id']]['vouchers'] #this is a list of vouchers for the event
    await f.printer(f"The vouchers available are: {vouchers}", debugging)
    voucher = vouchers.get(voucher_input, None) #this selects teh correct voucher from the list
    await f.printer(f"The object of the voucher selected is: {voucher}", debugging)
    if voucher_input == "pass":
        return Validate(response=True, context=context)
    elif voucher_input not in vouchers:
        print("voucher not in vouchers")
        return Validate(response=False, context = context)
    else:
        utc_time = datetime.now(timezone.utc)
        start_time = voucher['voucher_start'].replace(tzinfo=timezone.utc)
        end_time = voucher['voucher_end'].replace(tzinfo=timezone.utc)
        
        if utc_time >= start_time and utc_time <= end_time:
            await f.send_text(context['chat_id'], voucher['msg'])
            clients.update_one({"client_id": context['client_id'], "vouchers": voucher_input}, {"$inc": {"qty": -1}})
            users.update_one({"sid.telegram": context['chat_id']}, {"$push": {f"client_customer_relation.{context['event_id']}.claimedVouchers": voucher_input}})
            await f.incrementEventStats('any/repeat', context['client_id'], context['event_id'], [f"vouchers.{voucher_input}", 'voucherUnused'])
            return Validate(response=True, context=context)
        else:
            return Validate(response=False, context=context)
        
async def dob(context: dict):
    dob = context['user_input']
    try:
        parsedDob = f.TextToDate(dob) #contains status, day, month, and year along with it's corresponding datetime object
    except Exception as e:
        await f.printer("Text to date conversion went wrong", debugging)
        return Validate(response=False, context=context)

    await f.printer(parsedDob, debugging)

    if parsedDob['status'] == False:
        return Validate(response=False, context=context)
    else:
        await f.printer("Text converted to datetimeobject successfully", debugging) 
        context['user_input'] = parsedDob['datetimeObject']
        return Validate(response=True, context=context)
    