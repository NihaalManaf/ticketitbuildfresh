from telegram import Bot, Update
from telegram.ext import *
import openai
from openai import OpenAI
import logging
import time
import sqlite3
import sys
import re
from datetime import datetime
import traceback
from pymongo import MongoClient
import os
from config import *
import tracemalloc


tracemalloc.start()
approved_users = {}
current_member:int = 0

openai.api_key = OPENAI_TOKEN
bot = Bot(TOKEN)
BOT_USERNAME = "@SCDFmyWellnessBot"

mongo = MongoClient(Mongodb_url,
                     tls=True,
                     tlsCertificateKeyFile='smw.pem')

db = mongo['SCDFMyWellness']
end_of_course = db["end_of_course"]
def_pass = db["def_pass"]
temp = db["temp"]
user_accounts = db["user_accounts"]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Welcome to SCDF MyWellness! Please either click on the menu found in the bottom left corner to find more options or just tell us what you need to know!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("To make this bot work, simply tell us how you are feeling or what information you need and we shall see how we can help! \n \nIf you do not have access to the bot, simply tell us the password! If you still cant gain access, please contact your supervisors!")

async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("As this bot is a prototype, features found here may seem quite limited. However, over time you will be able to do so much more such as get alerts regarding key dates for your training!")    

#admin login + functions ----------------------------------------------------------------------------------------------------
    
LOGIN, FUNCTION, DATE, INTAKE, DEF, UPDATES = range(6)
user_data = {}

def NRICparser(user_ics):
    strings = re.split('\n',user_ics)
    user_ics = [s for s in strings if s]
    return user_ics

def addusers(user_ics, date, intake):
    user_ics_a = NRICparser(user_ics)
    cursor_mongo = def_pass.find()
    for document in cursor_mongo:
        defaultpass_mongo = document['_id']['pass']

    for i in range(0,len(user_ics_a)):
        user_documemt = {
            "useric":user_ics_a[i],
            "eslist_date": date,
            "tele_id":"",
            "login_status": False,
            "password": defaultpass_mongo,
            "intake": intake,
            "pass_change": False
        }

        user_accounts.insert_one(user_documemt)
        
    return

def resetpasswords(user_ics):

    user_ics_a = NRICparser(user_ics)

    cursor_mongo = def_pass.find()
    for document in cursor_mongo:
        defaultpass_mongo = document['_id']['pass']

    for i in range(0,len(user_ics_a)):
        filter_mongo = {"useric" : user_ics_a[i]}
        update_data = {"$set": {"password": defaultpass_mongo}}
        user_accounts.update_many(filter_mongo, update_data)
    
    return

def changepass(new_pass):
    update_data = {"$set": {"password": new_pass}}
    def_pass.update_one({}, update_data)
    return


#/admin converstaion ----------------------------------------------------------------------------------------------------
async def admin(update:Update, context):
    await update.message.reply_text("Welcome Admin. Please enter the password to access Admin functions")
    return LOGIN

async def admin_login(update, context):
    user_data['pass'] = update.message.text

    if admin_password not in user_data["pass"]:
        await update.message.reply_text("You have entered an invalid password. Sorry!")
        return ConversationHandler.END
    
    await update.message.reply_text("""
                                    Please select from the following functions
    1. addusers
    2. resetpasswords
    3. changedefault
                                    """)
    
    return FUNCTION

async def admin_function(update, context):
    user_data['function'] = update.message.text.replace(" ", "").lower()

    if user_data["function"] in 'addusers':
        await update.message.reply_text("Enter the date of enlistment for the recruits! Please enter the date in the following format: DD-MM-YYYY ")
        return DATE

    if user_data["function"] in 'resetpasswords':
        await update.message.reply_text("Please ensure you have the NRIC's ready by copying them directly from the excel spreadsheet. Ensure all the NRIC's are in one column and no extra lines have been copied. Type ok to acknowledge. ")
        x= 1
        return INTAKE
    
    if user_data["function"] in 'changedefaults':
        await update.message.reply_text("please enter the new default password. Please take note that the password is case sensitive! ")
        return DEF
    
    await update.message.reply_text("You have not selected a valid function. Please enter the admin password and try again!") 
    return LOGIN

async def admin_date(update, context):
    user_data['date'] = update.message.text.replace(" ", "").lower()
    await update.message.reply_text("Please enter the intake number and type of the recruits in the following format: 171xbrt or 171brt")
    
    return INTAKE

async def admin_intake(update, context):
    user_data['intake'] = update.message.text.replace(" ", "").lower()
    await update.message.reply_text("Now, please enter all the NRIC's of the users. Ensure you directly copy the full column from an excel file and paste it here!")
    return UPDATES

async def admin_def_update(update, context):
    user_data['default'] = update.message.text
    print(user_data["default"])
    changepass(user_data["default"])
    await update.message.reply_text("You have successfully updated the database!")
    return ConversationHandler.END

async def admin_update(update, context):
    user_data['NRICs'] = update.message.text
    print(user_data['function'])
    
    if user_data["function"] in 'addusers':
        addusers(user_data['NRICs'], user_data['date'],user_data['intake'])

    if user_data["function"] in 'resetpasswords':
        resetpasswords(user_data['NRICs'])


    await update.message.reply_text("You have successfully updated the database!")
    return ConversationHandler.END

async def cancel(update, context: CallbackContext):
    await update.message.reply_text("Login Cancelled. Returning to Bot.")
    return ConversationHandler.END


#start of user login ----------------------------------------------------------------------------------------------------------

USERNRIC, USERPASS, UPDATEPASS = range(3)
rec_data = {}

def auth_user_check(NRIC): 

    result_mongo = 0
    cursor_mongo = user_accounts.find({"useric": {"$regex": re.compile(NRIC, re.IGNORECASE)}})

    for document in cursor_mongo:
        result_mongo = document["useric"]

    print("auth user check works")

    if not result_mongo:
        return False
    else:
        return True

def auth_user_pass(NRIC, password):
    x = 0
    criteria = {"useric": {"$regex": re.compile(NRIC, re.IGNORECASE)}}
    cursor_ic = user_accounts.find(criteria)

    for document in cursor_ic:
        pass_change = document["pass_change"]
        user_pass = document["password"]
        print(pass_change)

    if password == user_pass:
        print('approval')
        x = 1

        if pass_change == False:
            x = 2
            
    return x

def login_true(chatid):

    ph = retrieve_nric(chatid)
    
    criteria = {"useric": {"$regex": re.compile(ph, re.IGNORECASE)}}
    up = {"$set": {"pass_change": True, "login_status": True, "tele_id": chatid}}
    user_accounts.update_one(criteria, up)
 
    return

def log_query(intake, query, response):

    formatted_date = datetime.now().strftime("%d%m%y")
    document = {
        "date":formatted_date,
        "intake": intake,
        "query" : query,
        "response" : response
    }

    end_of_course.insert_one(document)

    print("logging query")

    
    return

async def login(update, context):
    await update.message.reply_text("Welcome to SCDF MyWellness! To login, Please enter the last 4 characters of your NRIC. e.g. 384G")
    return USERNRIC

# to add a temp row to allow user login process in temp db
def add_temp(chatid, nric):
    existing_document = temp.find_one({"tele_id": chatid})
    if existing_document is None:
        up = {"tele_id": chatid, "nric": nric}
        temp.insert_one(up)
    return

def retrieve_nric(chatid):
    cursor_mongo = temp.find({"tele_id": chatid})
    
    for document in cursor_mongo:
        nric = document['nric']
        return nric

async def usernric(update, context):
    chat_id = update.message.chat.id
    nric = update.message.text

    if auth_user_check(nric) == True:
        await update.message.reply_text("Please enter your password! If you are unsure of your password, please seek assistance from your supervisor")
        add_temp(chat_id, nric)
        return USERPASS
    
    await update.message.reply_text("You have not been registered in our system. Please seek assistance from your supervisor. To try again, please press /login")
    return ConversationHandler.END

async def userpass(update, context):

    chat_id = update.message.chat.id
    password = update.message.text
    nric = retrieve_nric(chat_id)

    login_check = auth_user_pass(nric,password)

    if login_check == 1:
        await update.message.reply_text("You have successfully logged in!")
        chatid = update.message.chat.id
        login_true(chatid)
        return ConversationHandler.END

    elif login_check == 2:
        await update.message.reply_text("You are logging in for the first time. Please enter a new password! (Password is case sensitive)")
        login_true(chat_id)
        return UPDATEPASS
    
    else:
        await update.message.reply_text("You have input an incorrect password! Please seek assistance from your supervisor. To login again, press /login")
        return ConversationHandler.END
    
async def userupdate(update, context):
    chat_id = update.message.chat.id
    password = update.message.text

    ph = password
    ph2 = retrieve_nric(chat_id)

    criteria = {"useric": {"$regex": re.compile(ph2, re.IGNORECASE)}}
    up = {"$set": {"password":ph}}
    user_accounts.update_one(criteria, up)

    await update.message.reply_text("Your new password has been set and you have logged in! Please continue to use the bot to answer all of your questions!")
    return ConversationHandler.END

    
#Regular message handlers    
def sendMessage(chat_id:int, text:str):
    bot = Bot(token=TOKEN)
    bot.send_message(chat_id=chat_id,text=text)

def get_message(update:Update,processed:str) -> str :

    current_member = update.message.chat.id
    client = OpenAI(api_key=OPENAI_TOKEN)

    if approved_users[current_member] == "":
        thread = client.beta.threads.create()
        approved_users[current_member] = thread.id
        print(thread)

    message = client.beta.threads.messages.create(
        thread_id = approved_users[current_member],
        role="user",
        content= f"{processed}"
    )

    run = client.beta.threads.runs.create(
        thread_id = approved_users[current_member],
        assistant_id = "asst_cxbjvIh6pDIJP7p7uK3Ol3fv"
    )

    while run.status == 'queued' or run.status == 'in_progress':

        run = client.beta.threads.runs.retrieve(
        thread_id= approved_users[current_member],
        run_id = run.id
    )  

    messages = client.beta.threads.messages.list(
        thread_id = approved_users[current_member]
    )

    for messages in messages.data:
        return messages.content[0].text.value

    # response = openai.chat.completions.create(
    #     #assistant_id = "asst_cxbjvIh6pDIJP7p7uK3Ol3fv",
    #     model = "gpt-3.5-turbo",
    #     messages = [
    #     {"role" : "system", "content": f"{content_ai}"},
    #     {"role" : "user", "content" : f"{processed}"} 
    #     ]
    # )
    # assistant_response = response.choices[0].message.content
    # return assistant_response

def check_user_login(chatid):

    rec_dict = {"status": False, "intake": ""}   
    status = False  
    cursor_mongo = user_accounts.find({"tele_id":chatid})

    for document in cursor_mongo:
        status = document['login_status']
        intake = document['intake']

    if status == True: #some error
        approved_users.update({chatid:""})
        rec_dict = {"status":True, "intake": intake}

    return rec_dict  

def handle_response(update:Update, text: str) -> str:

    processed: str = text.lower()
    input_pass = update.message.text
    response = 'Sorry! you have not logged in! Pleae use /login to access the bot!'

    current_member = update.message.chat.id    
    print(approved_users)

    if 'hello' in processed:
        return "Hi! Welcome to SCDF YourWellness"
    
    if 'thanks' in processed:
        return "No Problem! Have a good day!"


    login_info = check_user_login(current_member) 

    if login_info['status'] == False: #Catch for non approved users. #point of entry to AI use
            return "Sorry You don't have access to this bot! Please use /login to login and gain access to this bot!"

 
    response = get_message(update, processed)
    log_query(login_info["intake"], processed, response)
    print(login_info["intake"], processed, response)

    return response
    

async def handle_message(update:Update, context:ContextTypes.DEFAULT_TYPE): #used for debugging?
    message_type: str = update.message.chat.type #type of chat - Group or private
    text: str = update.message.text #any new message in group

    print(f'User({update.message.chat.id}) in  {message_type}: "{text}"')

    if message_type == 'supergroup':
        if BOT_USERNAME in text:
            new_text: str = text.replace(BOT_USERNAME, '').strip()
            response:str = handle_response(update, new_text)
        else:
            return
    else:
        response: str = handle_response(update, text)
        await bot.send_message(chat_id= 1816433534, text=f"Text:{text}             Response:{response}")

    print('Bot:', response) 
    await update.message.reply_text(response)

async def error_handler(update:Update, context:ContextTypes.DEFAULT_TYPE):
    trace = traceback.format_exc()
    print(f'Update {update} caused error {context.error}\nTraceback:\n{trace}')
    await bot.send_message(chat_id= 1816433534, text=f'Update {update} caused error {context.error}\nTraceback:\n{trace}')




if __name__ == "__main__":
    print("Starting bot...")
    app = ApplicationBuilder().token(TOKEN).build()

   #Conversations ----------------------------------------------------------------------------------------------------
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('admin',admin)],
        states={
            LOGIN: [MessageHandler(filters.TEXT, admin_login)],
            FUNCTION: [MessageHandler(filters.TEXT, admin_function)],
            DATE: [MessageHandler(filters.TEXT, admin_date)],
            INTAKE: [MessageHandler(filters.TEXT, admin_intake)],
            DEF: [MessageHandler(filters.TEXT, admin_def_update)],
            UPDATES: [MessageHandler(filters.TEXT, admin_update)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(admin_conv_handler)

    rec_login_handler = ConversationHandler(
        entry_points=[CommandHandler('login',login)],
        states={
            USERNRIC: [MessageHandler(filters.TEXT, usernric)],
            USERPASS: [MessageHandler(filters.TEXT, userpass)],
            UPDATEPASS: [MessageHandler(filters.TEXT, userupdate)],
            
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(rec_login_handler)

    #Commands ----------------------------------------------------------------------------------------------------
    app.add_handler(CommandHandler('start',start_command))
    app.add_handler(CommandHandler('help',help_command))
    app.add_handler(CommandHandler('upcoming',upcoming_command))

    #Messages ----------------------------------------------------------------------------------------------------
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    #Errors ----------------------------------------------------------------------------------------------------
    app.add_error_handler(error_handler)

    print("Polling...")
    app.run_polling(poll_interval=3) 
